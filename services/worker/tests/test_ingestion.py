import hashlib
from uuid import uuid4
import psycopg
import pytest
from psycopg.types.json import Jsonb
from caseflow_worker import jobs
from caseflow_worker.parsing import parse
from caseflow_worker.settings import database


def policy_event(connection, document_event):
    source, job = uuid4(), uuid4()
    tenant = document_event.tenantId
    data = b"Equipment purchase requests require a cost center before approval."
    digest = hashlib.sha256(data).hexdigest()
    with psycopg.connect(**connection) as db:
        actor = db.execute("SELECT requested_by FROM core.job_requests WHERE job_id=%s", (document_event.jobId,)).fetchone()[0]
        db.execute("""INSERT INTO core.sources(tenant_id,id,kind,name,media_type,upload_key,byte_size,created_by)
            VALUES (%s,%s,'POLICY','Synthetic policy','text/plain',%s,%s,%s)""", (tenant,source,str(source),len(data),actor))
        payload = dict(sourceId=str(source),tenantId=str(tenant),revision=1,sha256=digest)
        db.execute("""INSERT INTO core.job_requests(tenant_id,job_id,source_id,kind,input,input_hash,requested_by)
            VALUES (%s,%s,%s,'INGESTION',%s,%s,%s)""",(tenant,job,source,Jsonb(payload),digest,actor))
        db.execute("""UPDATE core.sources SET state='INDEXING',object_key=%s,sha256=%s,ingestion_job_id=%s,version=1
            WHERE tenant_id=%s AND id=%s""",(str(uuid4()),digest,job,tenant,source))
    event = document_event.model_copy(update=dict(eventId=uuid4(),eventType="ingestion.requested",aggregateType="policy",
                                                  aggregateId=source,jobId=job,correlationId=job,inputHash=digest))
    return event, data


def test_policy_index_fenced_atomic_and_scoped(isolated_database, event):
    request, data = policy_event(isolated_database, event)
    assert jobs.schedule(request)
    assert not jobs.schedule(request)
    bad = request.model_copy(update=dict(eventId=uuid4(),aggregateType="case"))
    with pytest.raises(ValueError, match="INVALID_JOB_REFERENCE"):
        jobs.schedule(bad)
    old = jobs.claim(uuid4())
    assert jobs.input_for(old)["sourceId"] == str(request.aggregateId)
    with database() as db:
        db.execute("UPDATE worker.jobs SET lease_until=now()-interval '1 second' WHERE job_id=%s", (request.jobId,))
    new = jobs.claim(uuid4())
    result = parse(data, "text/plain")
    assert not jobs.finish(old, result)
    assert jobs.finish(new, result)
    assert not jobs.finish(new, result)
    with database() as db:
        chunks = db.execute("SELECT * FROM worker.chunks WHERE tenant_id=%s AND source_id=%s", (request.tenantId,request.aggregateId)).fetchall()
        assert len(chunks) == 1 and chunks[0]["text"] == data.decode()
        assert db.execute("SELECT count(*) AS n FROM worker.outbox WHERE job_id=%s AND payload->>'status'='SUCCEEDED'",(request.jobId,)).fetchone()["n"] == 1
        assert not db.execute("SELECT * FROM worker.chunks WHERE tenant_id=%s AND source_id=%s",(uuid4(),request.aggregateId)).fetchall()


def test_index_constraints_and_api_ownership(isolated_database, event):
    request, data = policy_event(isolated_database, event)
    jobs.schedule(request)
    job = jobs.claim(uuid4())
    assert jobs.finish(job, parse(data,"text/plain"))
    with psycopg.connect(**isolated_database) as db:
        db.execute("UPDATE core.sources SET state='INDEXED' WHERE tenant_id=%s AND id=%s",(request.tenantId,request.aggregateId))
        db.execute("UPDATE core.sources SET state='PUBLISHED' WHERE tenant_id=%s AND id=%s",(request.tenantId,request.aggregateId))
    with psycopg.connect(**isolated_database) as db:
        with pytest.raises(psycopg.errors.CheckViolation):
            db.execute("UPDATE core.sources SET sha256=%s WHERE tenant_id=%s AND id=%s",("f"*64,request.tenantId,request.aggregateId))
    with psycopg.connect(**isolated_database) as db:
        with pytest.raises(psycopg.errors.CheckViolation):
            db.execute("""INSERT INTO core.job_requests(tenant_id,job_id,case_id,source_id,kind,input,input_hash,requested_by)
                SELECT tenant_id,%s,case_id,%s,'INGESTION',input,input_hash,requested_by FROM core.job_requests WHERE job_id=%s""",
                (uuid4(),request.aggregateId,event.jobId))
    import os
    api = dict(isolated_database,user="caseflow_api",password=os.environ["DB_API_PASSWORD"])
    with psycopg.connect(**api) as db:
        assert db.execute("SELECT count(*) FROM worker.source_chunks").fetchone()[0] == 1
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute("DELETE FROM worker.chunks")
