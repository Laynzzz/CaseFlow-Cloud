"""Test-only spawned-process probes; never launch against the demo database."""
from contextlib import contextmanager
from datetime import datetime, timezone
import multiprocessing
import os
import re
from uuid import uuid4


BOUNDARIES = {
    "schedule-before-commit", "schedule-after-commit",
    "result-before-commit", "result-after-commit", "after-object-upload",
}


def guard_database():
    if not re.fullmatch(r"caseflow_test_[a-f0-9]{32}", os.getenv("DB_NAME", "")):
        raise ValueError("process probe requires a disposable test database")
    if os.getenv("DB_HOST", "127.0.0.1") != "127.0.0.1" or os.getenv("DB_PORT", "54320") != "54320":
        raise ValueError("process probe requires the loopback test database server")


def child_probe(pipe, boundary, event_json):
    # Imports and connections occur in the fresh interpreter, not through a fork.
    try:
        guard_database()
        from caseflow_worker import jobs, render

        event = jobs.Envelope.model_validate_json(event_json)
        payload = {}

        def checkpoint():
            pipe.send(dict(boundary=boundary, pid=os.getpid(),
                           reached_at=datetime.now(timezone.utc).isoformat(), **payload))
            pipe.recv()  # Parent terminates us here; no graceful transaction exit.

        real_database = jobs.database

        @contextmanager
        def before_commit():
            with real_database() as db:
                yield db
                checkpoint()

        if boundary.startswith("schedule-"):
            if boundary == "schedule-before-commit":
                jobs.database = before_commit
            jobs.schedule(event)
            if boundary == "schedule-after-commit":
                checkpoint()
            return

        jobs.schedule(event)
        job = jobs.claim(uuid4(), lease_seconds=5)
        if job is None:
            raise RuntimeError("isolated job could not be leased")
        payload["job"] = job
        if boundary == "after-object-upload":
            if os.getenv("S3_ENDPOINT", "http://127.0.0.1:8333") != "http://127.0.0.1:8333":
                raise ValueError("process probe requires local object storage")
            artifact = render.execute(job, jobs.input_for(job))
            payload["artifact"] = artifact
            checkpoint()
        else:
            artifact = {"key": "synthetic-process-tests/" + str(uuid4()), "sha256": "b" * 64, "size": 100}
            payload["artifact"] = artifact
            if boundary == "result-before-commit":
                jobs.database = before_commit
            if not jobs.finish(job, artifact):
                raise RuntimeError("isolated completion was not selected")
            if boundary == "result-after-commit":
                checkpoint()
    except Exception as error:
        # Parent only needs the class; never transfer connection strings or secrets.
        pipe.send({"error_type": type(error).__name__, "boundary": boundary})
        raise
    finally:
        pipe.close()


def terminate_at_boundary(boundary, event_json):
    guard_database()
    if boundary not in BOUNDARIES:
        raise ValueError("unknown crash boundary")
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    process = context.Process(target=child_probe, args=(child, boundary, event_json), name="caseflow-crash-probe")
    try:
        process.start()
        child.close()
        if not parent.poll(20):
            raise AssertionError("child did not reach the crash boundary within 20 seconds")
        evidence = parent.recv()
        assert "error_type" not in evidence, evidence.get("error_type")
        assert evidence["boundary"] == boundary and evidence["pid"] == process.pid
        assert process.is_alive(), "child exited before forced termination"
        process.terminate()
        process.join(10)
        assert not process.is_alive(), "child survived forced termination"
        assert process.exitcode not in (None, 0), "normal exit is not crash evidence"
        return dict(evidence, exit_code=process.exitcode, termination="multiprocessing.Process.terminate",
                    terminated_at=datetime.now(timezone.utc).isoformat())
    finally:
        if process.pid is not None:
            if process.is_alive():
                process.kill()
                process.join(5)
            if process.is_alive():
                raise AssertionError("owned test child could not be stopped")
            process.close()
        parent.close()
        child.close()
