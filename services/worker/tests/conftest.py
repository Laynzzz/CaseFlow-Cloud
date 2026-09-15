"""Disposable database per test; never delete or truncate the demo database."""
import os
from pathlib import Path
from uuid import uuid4
import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb
import pytest
from caseflow_worker.jobs import Envelope

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def isolated_database(monkeypatch):
    name = "caseflow_test_" + uuid4().hex
    connection = dict(host="127.0.0.1", port=54320, dbname="caseflow", user="caseflow_admin",
                      password=os.environ["DB_ADMIN_PASSWORD"])
    with psycopg.connect(**connection, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {} OWNER caseflow_migrator").format(sql.Identifier(name)))
    monkeypatch.setenv("DB_NAME", name)
    migrator = dict(connection, dbname=name, user="caseflow_migrator", password=os.environ["DB_MIGRATOR_PASSWORD"])
    try:
        with psycopg.connect(**migrator) as db:
            for migration in sorted((ROOT / "db/migrations").glob("V*__*.sql")):
                db.execute(migration.read_text(encoding="utf-8"))
        yield migrator
    finally:
        assert name.startswith("caseflow_test_") and len(name)==46
        with psycopg.connect(**connection, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


@pytest.fixture
def event(isolated_database):
    tenant, actor, case, job, event_id = [uuid4() for _ in range(5)]
    with psycopg.connect(**isolated_database) as db:
        db.execute("INSERT INTO core.identities(id,issuer,subject,display_name) VALUES (%s,%s,%s,%s)",
                   (actor,"https://synthetic-worker-test.invalid",str(actor),"Synthetic worker test"))
        db.execute("INSERT INTO core.tenants(id,name) VALUES (%s,'Isolated worker test')",(tenant,))
        db.execute("INSERT INTO core.memberships(tenant_id,user_id,roles) VALUES (%s,%s,ARRAY['REQUESTER'])",(tenant,actor))
        db.execute("INSERT INTO core.cases(tenant_id,id,owner_id,purchase) VALUES (%s,%s,%s,%s)",(tenant,case,actor,Jsonb({})))
        db.execute("""INSERT INTO core.job_requests(tenant_id,job_id,case_id,kind,input,input_hash,requested_by)
            VALUES (%s,%s,%s,'DOCUMENT',%s,%s,%s)""",(tenant,job,case,Jsonb({"synthetic":True}),"a"*64,actor))
    return Envelope(eventId=event_id,eventType="document.requested",schemaVersion=1,timestamp="2026-09-15T00:00:00Z",
                    tenantId=tenant,aggregateId=case,aggregateType="case",aggregateSequence=1,jobId=job,
                    attempt=1,correlationId=job,causationId="synthetic-test",inputHash="a"*64,traceContext={})
