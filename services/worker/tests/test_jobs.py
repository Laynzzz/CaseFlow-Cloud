from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import psycopg
import pytest
from caseflow_worker import jobs
from caseflow_worker.settings import database


def artifact():
    return dict(key="synthetic-tests/"+str(uuid4()),sha256="b"*64,size=100)


def test_duplicate_scheduling_is_durable(event):
    assert jobs.schedule(event)
    assert not jobs.schedule(event)
    assert jobs.schedule(event.model_copy(update={"eventId":uuid4()}))
    with database() as db:
        assert db.execute("SELECT count(*) AS n FROM worker.jobs").fetchone()["n"] == 1
        assert db.execute("SELECT count(*) AS n FROM worker.inbox").fetchone()["n"] == 2


def test_wrong_tenant_and_hash_cannot_schedule(event):
    for changes in ({"tenantId":uuid4()},{"inputHash":"b"*64},{"aggregateId":uuid4()}):
        with pytest.raises(ValueError):
            jobs.schedule(event.model_copy(update=changes))
    with database() as db:
        assert db.execute("SELECT count(*) AS n FROM worker.jobs").fetchone()["n"] == 0


def test_concurrent_claim_and_terminal_success(event):
    jobs.schedule(event)
    with ThreadPoolExecutor(max_workers=2) as pool:
        claimed=list(pool.map(lambda _:jobs.claim(uuid4()),range(2)))
    winners=[job for job in claimed if job]
    assert len(winners)==1
    job=winners[0]
    assert jobs.finish(job,artifact())
    assert not jobs.finish(job,artifact())
    assert not jobs.fail(job,"DELAYED_FAILURE",True)
    with database() as db:
        assert db.execute("SELECT status FROM worker.jobs").fetchone()["status"]=="SUCCEEDED"
        assert db.execute("SELECT count(*) AS n FROM worker.artifacts").fetchone()["n"]==1
        assert db.execute("SELECT count(*) AS n FROM worker.outbox WHERE payload->>'status'='SUCCEEDED'").fetchone()["n"]==1


def test_expired_lease_is_reclaimed_and_old_owner_fenced(event,isolated_database):
    jobs.schedule(event)
    stale=jobs.claim(uuid4())
    with psycopg.connect(**isolated_database) as db:
        db.execute("UPDATE worker.jobs SET lease_until=now()-interval '1 second'")
    assert not jobs.heartbeat(stale)
    current=jobs.claim(uuid4())
    assert current["fence"]>stale["fence"]
    assert not jobs.finish(stale,artifact())
    assert not jobs.fail(stale,"LATE_FAILURE",True)
    assert jobs.finish(current,artifact())


def test_failure_retry_preserves_logical_id_and_advances_attempt(event,isolated_database):
    jobs.schedule(event)
    job=jobs.claim(uuid4())
    assert jobs.fail(job,"INVALID_TEMPLATE",True)
    with psycopg.connect(**isolated_database) as db:
        db.execute("UPDATE core.job_requests SET status='QUEUED',attempt=2")
    retry=event.model_copy(update={"eventId":uuid4(),"attempt":2})
    jobs.schedule(retry)
    current=jobs.claim(uuid4())
    assert current["job_id"]==job["job_id"] and current["attempt"]==2
    assert current["fence"]>job["fence"]
    assert not jobs.finish(job,artifact())
    assert jobs.finish(current,artifact())


def test_database_ownership_boundaries(event,isolated_database):
    with database() as db:
        assert db.execute("SELECT count(*) AS n FROM core.worker_job_inputs").fetchone()["n"]==1
    for command in ("UPDATE core.cases SET version=version+1", "SELECT * FROM core.memberships"):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with database() as db:
                db.execute(command)
    import os
    api=dict(isolated_database,user="caseflow_api",password=os.environ["DB_API_PASSWORD"])
    with psycopg.connect(**api) as db:
        db.execute("SELECT * FROM worker.document_results")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with psycopg.connect(**api) as db:
            db.execute("UPDATE worker.jobs SET status='FAILED'")
