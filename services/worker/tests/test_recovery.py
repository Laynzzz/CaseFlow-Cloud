"""Database-backed recovery contracts for worker transaction and Kafka boundaries."""
from contextlib import contextmanager
from uuid import uuid4

import pytest

from caseflow_worker import jobs, runtime
from caseflow_worker.settings import database


def artifact():
    return {
        "key": "synthetic-recovery-tests/" + str(uuid4()),
        "sha256": "b" * 64,
        "size": 100,
    }


class Message:
    def __init__(self, value):
        self._value = value

    def value(self):
        return self._value

    def error(self):
        return None

    def topic(self):
        return "caseflow.jobs.v1"

    def partition(self):
        return 0

    def offset(self):
        return 7


class BoundedStop:
    def __init__(self, maximum_waits=4):
        self.stopped = False
        self.waits = 0
        self.maximum_waits = maximum_waits

    def is_set(self):
        return self.stopped

    def set(self):
        self.stopped = True

    def wait(self, _seconds):
        self.waits += 1
        if self.waits > self.maximum_waits:
            raise AssertionError("runtime exceeded the bounded retry loop")
        return self.stopped


class OneRecordConsumer:
    def __init__(self, message, stop, commit_failures=0):
        self.message = message
        self.stop = stop
        self.commit_failures = commit_failures
        self.polls = 0
        self.commits = 0
        self.closed = False

    def subscribe(self, _topics):
        pass

    def poll(self, _timeout):
        self.polls += 1
        if self.polls > 1:
            raise AssertionError("consumer polled past the unacknowledged record")
        return self.message

    def commit(self, *, message, asynchronous):
        assert message is self.message
        assert asynchronous is False
        self.commits += 1
        if self.commits <= self.commit_failures:
            raise RuntimeError("injected offset commit failure")
        self.stop.set()

    def close(self):
        self.closed = True


def runtime_with(stop):
    worker = runtime.Runtime.__new__(runtime.Runtime)
    worker.stop = stop
    return worker


def rollback_once(real_database, message):
    attempts = 0

    @contextmanager
    def wrapped():
        nonlocal attempts
        attempts += 1
        with real_database() as db:
            yield db
            if attempts == 1:
                raise RuntimeError(message)

    return wrapped


def test_schedule_rolls_back_receipt_and_job_before_replay(event, monkeypatch):
    real_database = jobs.database
    monkeypatch.setattr(jobs, "database", rollback_once(real_database, "injected scheduling rollback"))

    with pytest.raises(RuntimeError, match="injected scheduling rollback"):
        jobs.schedule(event)
    with database() as db:
        assert db.execute("SELECT count(*) AS n FROM worker.inbox").fetchone()["n"] == 0
        assert db.execute("SELECT count(*) AS n FROM worker.jobs").fetchone()["n"] == 0

    monkeypatch.setattr(jobs, "database", real_database)
    assert jobs.schedule(event)
    with database() as db:
        assert db.execute("SELECT count(*) AS n FROM worker.inbox").fetchone()["n"] == 1
        assert db.execute("SELECT count(*) AS n FROM worker.jobs").fetchone()["n"] == 1


def test_finish_rolls_back_result_status_and_event_before_replay(event, monkeypatch):
    jobs.schedule(event)
    job = jobs.claim(uuid4())
    real_emit = jobs.emit

    def injected_emit(*_args, **_kwargs):
        raise RuntimeError("injected completion emit failure")

    monkeypatch.setattr(jobs, "emit", injected_emit)
    with pytest.raises(RuntimeError, match="injected completion emit failure"):
        jobs.finish(job, artifact())
    with database() as db:
        assert db.execute("SELECT status FROM worker.jobs").fetchone()["status"] == "RUNNING"
        assert db.execute("SELECT count(*) AS n FROM worker.artifacts").fetchone()["n"] == 0
        assert db.execute(
            "SELECT count(*) AS n FROM worker.outbox WHERE payload->>'status'='SUCCEEDED'"
        ).fetchone()["n"] == 0

    monkeypatch.setattr(jobs, "emit", real_emit)
    assert jobs.finish(job, artifact())
    with database() as db:
        assert db.execute("SELECT status FROM worker.jobs").fetchone()["status"] == "SUCCEEDED"
        assert db.execute("SELECT count(*) AS n FROM worker.artifacts").fetchone()["n"] == 1
        assert db.execute(
            "SELECT count(*) AS n FROM worker.outbox WHERE payload->>'status'='SUCCEEDED'"
        ).fetchone()["n"] == 1


def test_consumer_retries_schedule_before_acknowledging_record(event, monkeypatch):
    stop = BoundedStop()
    consumer = OneRecordConsumer(Message(event.model_dump_json().encode()), stop)
    worker = runtime_with(stop)
    schedule_calls = 0
    real_schedule = jobs.schedule

    def recording_schedule(envelope):
        nonlocal schedule_calls
        schedule_calls += 1
        return real_schedule(envelope)

    monkeypatch.setattr(runtime, "Consumer", lambda _config: consumer)
    monkeypatch.setattr(jobs, "database", rollback_once(jobs.database, "injected scheduling rollback"))
    monkeypatch.setattr(jobs, "schedule", recording_schedule)
    worker.consume()

    assert schedule_calls == 2
    assert consumer.polls == 1
    assert consumer.commits == 1
    with database() as db:
        assert db.execute("SELECT count(*) AS n FROM worker.inbox").fetchone()["n"] == 1
        assert db.execute("SELECT count(*) AS n FROM worker.jobs").fetchone()["n"] == 1


def test_consumer_retries_same_record_when_offset_commit_fails(event, monkeypatch):
    stop = BoundedStop()
    consumer = OneRecordConsumer(Message(event.model_dump_json().encode()), stop, commit_failures=1)
    worker = runtime_with(stop)
    schedule_calls = 0
    real_schedule = jobs.schedule

    def recording_schedule(envelope):
        nonlocal schedule_calls
        schedule_calls += 1
        return real_schedule(envelope)

    monkeypatch.setattr(runtime, "Consumer", lambda _config: consumer)
    monkeypatch.setattr(jobs, "schedule", recording_schedule)
    worker.consume()

    assert schedule_calls == 2
    assert consumer.polls == 1
    assert consumer.commits == 2
    with database() as db:
        assert db.execute("SELECT count(*) AS n FROM worker.inbox").fetchone()["n"] == 1
        assert db.execute("SELECT count(*) AS n FROM worker.jobs").fetchone()["n"] == 1


def test_malformed_message_is_acknowledged_only_after_dead_letter_send(monkeypatch):
    body = b'{"secret":"synthetic source body"'
    stop = BoundedStop()
    consumer = OneRecordConsumer(Message(body), stop)
    worker = runtime_with(stop)
    sends = []

    def send(_topic, _key, payload):
        sends.append(payload)
        if len(sends) == 1:
            raise RuntimeError("injected dead-letter acknowledgement failure")

    worker.send = send
    monkeypatch.setattr(runtime, "Consumer", lambda _config: consumer)
    worker.consume()

    assert consumer.polls == 1
    assert consumer.commits == 1
    expected = {
        "reason": "INVALID_REQUEST_ENVELOPE_OR_REFERENCE",
        "sha256": "1b8fe1b6ffac9bb2e3ab202be033860f21ed90b6650c449a93e7ed12f793568d",
        "topic": "caseflow.jobs.v1",
        "partition": 0,
        "offset": 7,
    }
    assert sends == [expected, expected]


def test_publisher_repeats_same_event_after_ack_before_database_commit(event, monkeypatch):
    jobs.schedule(event)
    jobs.claim(uuid4())
    with database() as db:
        row = db.execute(
            "SELECT event_id FROM worker.outbox WHERE published_at IS NULL ORDER BY created_at LIMIT 1"
        ).fetchone()
    event_id = row["event_id"]
    stop = BoundedStop()
    worker = runtime_with(stop)
    sent_event_ids = []

    def send(_topic, _key, payload):
        sent_event_ids.append(payload["eventId"])
        if len(sent_event_ids) == 2:
            stop.set()

    worker.send = send
    monkeypatch.setattr(
        runtime,
        "database",
        rollback_once(runtime.database, "injected after acknowledgement before database commit"),
    )
    worker.publish()

    assert sent_event_ids == [str(event_id), str(event_id)]
    with database() as db:
        published = db.execute(
            "SELECT published_at FROM worker.outbox WHERE event_id=%s", (event_id,)
        ).fetchone()
        assert published["published_at"] is not None
