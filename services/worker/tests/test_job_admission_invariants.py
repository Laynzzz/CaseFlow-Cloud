"""Admission limits and stale inputs are proved against disposable PostgreSQL databases."""
from uuid import uuid4

import psycopg
import pytest

from caseflow_worker import jobs
from caseflow_worker.settings import database


def test_future_attempt_has_no_durable_receipt_or_job(event):
    with pytest.raises(ValueError, match="FUTURE_ATTEMPT"):
        jobs.schedule(event.model_copy(update={"attempt": 2}))
    with database() as db:
        assert db.execute("SELECT count(*) AS n FROM worker.inbox").fetchone()["n"] == 0
        assert db.execute("SELECT count(*) AS n FROM worker.jobs").fetchone()["n"] == 0


def test_tenant_admission_lock_defers_without_spending_execution(event, isolated_database):
    jobs.schedule(event)
    with psycopg.connect(**isolated_database) as lock:
        lock.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,17))", (str(event.tenantId),))
        assert jobs.claim(uuid4()) is None
        with database() as db:
            assert db.execute("SELECT executions FROM worker.jobs").fetchone()["executions"] == 0
            assert db.execute("SELECT count(*) AS n FROM worker.outbox").fetchone()["n"] == 0
    assert jobs.claim(uuid4())["executions"] == 1


def test_third_tenant_job_waits_until_an_active_job_finishes(event, isolated_database):
    events = [event]
    for _ in range(2):
        new_id = uuid4()
        with psycopg.connect(**isolated_database) as db:
            db.execute("""INSERT INTO core.job_requests(tenant_id,job_id,case_id,kind,input,input_hash,requested_by)
                SELECT tenant_id,%s,case_id,kind,input,input_hash,requested_by FROM core.job_requests
                WHERE job_id=%s""", (new_id, event.jobId))
        events.append(event.model_copy(update={"eventId": uuid4(), "jobId": new_id}))
    for item in events:
        jobs.schedule(item)
    first, second = jobs.claim(uuid4()), jobs.claim(uuid4())
    assert first and second and first["job_id"] != second["job_id"]
    assert jobs.claim(uuid4()) is None
    with database() as db:
        waiting = db.execute("SELECT * FROM worker.jobs WHERE status='QUEUED'").fetchone()
        assert waiting["executions"] == 0 and waiting["lease_owner"] is None
    assert jobs.fail(first, "SYNTHETIC_TERMINAL", permanent=True)
    admitted = jobs.claim(uuid4())
    assert admitted["job_id"] == waiting["job_id"] and admitted["executions"] == 1


def test_execution_limit_selects_one_durable_failure_without_another_lease(event, isolated_database):
    jobs.schedule(event)
    with psycopg.connect(**isolated_database) as db:
        db.execute("UPDATE worker.jobs SET executions=5")
    assert jobs.claim(uuid4()) is None
    assert jobs.claim(uuid4()) is None
    with database() as db:
        row = db.execute("SELECT * FROM worker.jobs").fetchone()
        assert row["status"] == "FAILED" and row["failure_code"] == "EXECUTION_LIMIT"
        assert row["executions"] == 5 and row["lease_owner"] is None
        messages = db.execute("SELECT payload FROM worker.outbox").fetchall()
        assert len(messages) == 1 and messages[0]["payload"]["failureCode"] == "EXECUTION_LIMIT"


def test_old_execution_cannot_read_input_for_a_new_attempt(event, isolated_database):
    jobs.schedule(event)
    job = jobs.claim(uuid4())
    assert jobs.input_for(job) == {"synthetic": True}
    with psycopg.connect(**isolated_database) as db:
        db.execute("UPDATE core.job_requests SET attempt=2")
    with pytest.raises(ValueError, match="STALE_INPUT"):
        jobs.input_for(job)
    with database() as db:
        assert db.execute("SELECT count(*) AS n FROM worker.artifacts").fetchone()["n"] == 0
