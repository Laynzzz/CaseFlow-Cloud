"""Synthetic integration probe: repeat broker events and inject a late failure."""
import json
import os
import time
from pathlib import Path
from uuid import uuid4
import psycopg
from psycopg.rows import dict_row
from confluent_kafka import Producer

root=Path(__file__).resolve().parents[3]
fixture=json.loads((root / "infrastructure/local/generated/document-demo.json").read_text())
connection=dict(host="127.0.0.1",port=54320,dbname="caseflow",user="caseflow_migrator",
                password=os.environ["DB_MIGRATOR_PASSWORD"],row_factory=dict_row)
with psycopg.connect(**connection) as db:
    request=db.execute("SELECT payload FROM core.outbox WHERE tenant_id=%s AND case_id=%s AND payload->>'jobId'=%s",
                       (fixture["tenantId"],fixture["caseId"],fixture["jobId"])).fetchone()["payload"]
    complete=db.execute("SELECT payload FROM worker.outbox WHERE tenant_id=%s AND job_id=%s AND payload->>'status'='SUCCEEDED'",
                        (fixture["tenantId"],fixture["jobId"])).fetchone()["payload"]
late=dict(complete,eventId=str(uuid4()),eventType="document.failed",status="FAILED",failureCode="DELAYED_FAILURE")
producer=Producer({"bootstrap.servers":"127.0.0.1:9092","acks":"all"})
errors=[]
def delivered(error,message):
    if error:errors.append(error)
for _ in range(10):
    for topic,event in [("caseflow.jobs.v1",request),("caseflow.completions.v1",complete)]:
        producer.produce(topic,key=fixture["tenantId"]+":"+fixture["caseId"],value=json.dumps(event),on_delivery=delivered)
producer.produce("caseflow.completions.v1",key=fixture["tenantId"]+":"+fixture["caseId"],value=json.dumps(late),on_delivery=delivered)
assert producer.flush(15)==0 and not errors
deadline=time.monotonic()+20
while time.monotonic()<deadline:
    with psycopg.connect(**connection) as db:
        received=db.execute("SELECT disposition FROM core.event_inbox WHERE event_id=%s",(late["eventId"],)).fetchone()
        if received:break
    time.sleep(.25)
assert received and received["disposition"]=="STALE"
with psycopg.connect(**connection) as db:
    job=db.execute("SELECT status FROM core.job_requests WHERE tenant_id=%s AND job_id=%s",(fixture["tenantId"],fixture["jobId"])).fetchone()
    assert job["status"]=="SUCCEEDED"
    assert db.execute("SELECT count(*) AS n FROM worker.artifacts WHERE tenant_id=%s AND job_id=%s",(fixture["tenantId"],fixture["jobId"])).fetchone()["n"]==1
    assert db.execute("SELECT count(*) AS n FROM core.audit WHERE tenant_id=%s AND case_id=%s AND event_type='DOCUMENT_SUCCEEDED'",(fixture["tenantId"],fixture["caseId"])).fetchone()["n"]==1
print("PASS 10 request and 10 completion redeliveries plus delayed failure: one artifact, one success audit, success preserved")
