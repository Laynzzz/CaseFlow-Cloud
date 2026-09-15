from uuid import uuid4
import psycopg
import pytest
from psycopg.types.json import Jsonb
from caseflow_worker import jobs, assistant
from caseflow_worker.settings import database


def review_event(event,connection):
    job=uuid4()
    with psycopg.connect(**connection) as db:
        db.execute("""INSERT INTO core.job_requests(tenant_id,job_id,case_id,kind,input,input_hash,requested_by)
            SELECT tenant_id,%s,case_id,'REVIEW',%s,input_hash,requested_by FROM core.job_requests WHERE job_id=%s""",
            (job,Jsonb(dict(revision=0,policyIds=[],purchase={"description":"Synthetic equipment"})),event.jobId))
    return event.model_copy(update=dict(eventId=uuid4(),eventType="review.requested",jobId=job,correlationId=job))


def test_review_eligibility_revoked_before_result_selection(event,isolated_database,monkeypatch):
    request=review_event(event,isolated_database);jobs.schedule(request);job=jobs.claim(uuid4())
    assistant.authorized(job)
    def fake_provider(job,kind,facts,chunks,authorize):
        assert kind=="REVIEW" and chunks=={}
        authorize()
        return dict(output={"summary":"No evidence", "insufficient_evidence":True},model="synthetic-fixture")
    monkeypatch.setattr(assistant.ai_provider,"request",fake_provider)
    result=assistant.execute(job,jobs.input_for(job))
    assert result["retrievedChunkIds"]==[]
    assert result["retrievalQuery"]=="Synthetic OR equipment OR purchase OR cost OR center OR justification"
    with psycopg.connect(**isolated_database) as db:
        db.execute("UPDATE core.memberships SET active=false WHERE tenant_id=%s",(request.tenantId,))
    with pytest.raises(ValueError,match="AI_INPUT_STALE_OR_ACCESS_REVOKED"):jobs.finish(job,result)
    with database() as db:
        assert db.execute("SELECT count(*) AS n FROM worker.ai_results").fetchone()["n"]==0
        assert db.execute("SELECT status FROM worker.jobs WHERE job_id=%s",(job["job_id"],)).fetchone()["status"]=="RUNNING"


def test_review_revision_change_blocks_provider(event,isolated_database,monkeypatch):
    request=review_event(event,isolated_database);jobs.schedule(request);job=jobs.claim(uuid4())
    with psycopg.connect(**isolated_database) as db:
        db.execute("UPDATE core.cases SET version=version+1 WHERE tenant_id=%s AND id=%s",(request.tenantId,request.aggregateId))
    def forbidden(*args):raise AssertionError("Provider must not be called")
    monkeypatch.setattr(assistant.ai_provider,"request",forbidden)
    with pytest.raises(ValueError,match="AI_INPUT_STALE_OR_ACCESS_REVOKED"):assistant.execute(job,jobs.input_for(job))


def test_successful_review_result_is_fenced(event,isolated_database):
    request=review_event(event,isolated_database);jobs.schedule(request);job=jobs.claim(uuid4())
    assert jobs.finish(job,{"syntheticFixture":True})
    assert not jobs.finish(job,{"syntheticFixture":False})
    with database() as db:
        assert db.execute("SELECT result FROM worker.ai_results WHERE job_id=%s",(job["job_id"],)).fetchone()["result"]=={"syntheticFixture":True}
