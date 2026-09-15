from uuid import uuid4
import psycopg
import pytest


def test_policy_pin_constraints(event, isolated_database):
    tenant, case, source = event.tenantId, event.aggregateId, uuid4()
    with psycopg.connect(**isolated_database) as db:
        actor = db.execute("SELECT owner_id FROM core.cases WHERE id=%s",(case,)).fetchone()[0]
        db.execute("""INSERT INTO core.sources(tenant_id,id,kind,name,media_type,upload_key,byte_size,created_by)
            VALUES (%s,%s,'POLICY','Synthetic pin test','text/plain',%s,1,%s)""",(tenant,source,str(source),actor))
    with psycopg.connect(**isolated_database) as db:
        with pytest.raises(psycopg.errors.CheckViolation):
            db.execute("INSERT INTO core.case_policy_pins(tenant_id,case_id,source_id,source_version) VALUES (%s,%s,%s,0)",(tenant,case,source))
    with psycopg.connect(**isolated_database) as db:
        job = uuid4()
        db.execute("""INSERT INTO core.job_requests(tenant_id,job_id,source_id,kind,input,input_hash,requested_by)
            VALUES (%s,%s,%s,'INGESTION','{}',%s,%s)""",(tenant,job,source,'b'*64,actor))
        db.execute("UPDATE core.sources SET state='INDEXING',ingestion_job_id=%s,object_key=%s,sha256=%s WHERE tenant_id=%s AND id=%s",(job,str(source),'b'*64,tenant,source))
        db.execute("UPDATE core.sources SET state='INDEXED' WHERE tenant_id=%s AND id=%s",(tenant,source))
        db.execute("UPDATE core.sources SET state='PUBLISHED',version=2 WHERE tenant_id=%s AND id=%s",(tenant,source))
        db.execute("INSERT INTO core.case_policy_pins(tenant_id,case_id,source_id,source_version) VALUES (%s,%s,%s,2)",(tenant,case,source))
        # Cancellation is terminal and also freezes the historical policy selection.
        db.execute("UPDATE core.cases SET state='CANCELLED' WHERE tenant_id=%s AND id=%s",(tenant,case))
    with psycopg.connect(**isolated_database) as db:
        with pytest.raises(psycopg.errors.CheckViolation):
            db.execute("DELETE FROM core.case_policy_pins WHERE tenant_id=%s AND case_id=%s",(tenant,case))
    with psycopg.connect(**isolated_database) as db:
        db.execute("UPDATE core.sources SET state='DEACTIVATED' WHERE tenant_id=%s AND id=%s",(tenant,source))
        assert db.execute("SELECT source_version FROM core.case_policy_pins WHERE tenant_id=%s AND case_id=%s",(tenant,case)).fetchone()[0] == 2
