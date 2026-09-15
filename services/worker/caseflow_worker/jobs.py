"""Durable scheduling, bounded leases and fenced result selection."""
import json
import random
from datetime import datetime, timezone
from uuid import UUID, uuid4
from typing import Literal
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field, ConfigDict
from .settings import database


class Envelope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    eventId: UUID
    eventType: Literal["document.requested", "ingestion.requested", "extraction.requested", "review.requested"]
    schemaVersion: Literal[1]
    timestamp: datetime
    tenantId: UUID
    aggregateId: UUID
    aggregateType: Literal["case", "policy"]
    aggregateSequence: int = Field(ge=0)
    jobId: UUID
    attempt: int = Field(ge=1)
    correlationId: UUID
    causationId: str
    inputHash: str = Field(pattern="^[a-f0-9]{64}$")
    traceContext: dict[str, str] = Field(default_factory=dict)


def schedule(event: Envelope):
    with database() as db:
        source = db.execute("""SELECT * FROM core.worker_job_inputs
            WHERE tenant_id=%s AND job_id=%s""", (event.tenantId, event.jobId)).fetchone()
        if (not source or (source["case_id"] or source["source_id"]) != event.aggregateId
            or ("case" if source["case_id"] else "policy") != event.aggregateType
            or source["kind"].lower()+".requested" != event.eventType or source["input_hash"] != event.inputHash):
            raise ValueError("INVALID_JOB_REFERENCE")
        if source["attempt"] < event.attempt:
            raise ValueError("FUTURE_ATTEMPT")
        receipt = db.execute("INSERT INTO worker.inbox(event_id) VALUES (%s) ON CONFLICT DO NOTHING RETURNING event_id",
                             (event.eventId,)).fetchone()
        if not receipt or source["attempt"] > event.attempt or source["status"] == "SUCCEEDED":
            return False
        db.execute("""INSERT INTO worker.jobs(tenant_id,job_id,case_id,source_id,kind,attempt,input_hash,status)
            VALUES (%s,%s,%s,%s,%s,%s,%s,'QUEUED')
            ON CONFLICT (tenant_id,job_id) DO UPDATE SET attempt=EXCLUDED.attempt,status='QUEUED',
            fence=worker.jobs.fence+1,executions=0,available_at=now(),updated_at=now(),
            lease_owner=NULL,lease_until=NULL,failure_code=NULL
            WHERE worker.jobs.status='FAILED' AND worker.jobs.attempt<EXCLUDED.attempt""",
            (event.tenantId,event.jobId,source["case_id"],source["source_id"],source["kind"],event.attempt,event.inputHash))
        return True


def emit(db, job, status, code=None):
    source = db.execute("SELECT input->>'revision' AS revision FROM core.worker_job_inputs WHERE tenant_id=%s AND job_id=%s",
                        (job["tenant_id"], job["job_id"])).fetchone()
    event = dict(eventId=str(uuid4()), eventType=job["kind"].lower()+"."+status.lower(), schemaVersion=1,
                 timestamp=datetime.now(timezone.utc).isoformat(), tenantId=str(job["tenant_id"]),
                 aggregateId=str(job["case_id"] or job["source_id"]), aggregateType="case" if job["case_id"] else "policy", jobId=str(job["job_id"]),
                 attempt=job["attempt"], fence=job["fence"], status=status, failureCode=code,
                 inputHash=job["input_hash"], correlationId=str(job["job_id"]),
                 causationId=str(job["job_id"]), aggregateSequence=int(source["revision"] or 0), traceContext={})
    db.execute("INSERT INTO worker.outbox(event_id,tenant_id,job_id,payload) VALUES (%s,%s,%s,%s)",
               (event["eventId"],job["tenant_id"],job["job_id"],Jsonb(event)))


def claim(owner: UUID, lease_seconds=30):
    with database() as db:
        job = db.execute("""SELECT * FROM worker.jobs WHERE
            ((status IN ('QUEUED','RETRY_WAIT') AND available_at<=now())
             OR (status='RUNNING' AND lease_until<now()))
            ORDER BY available_at,created_at FOR UPDATE SKIP LOCKED LIMIT 1""").fetchone()
        if not job:
            return None
        if not db.execute("SELECT pg_try_advisory_xact_lock(hashtextextended(%s,17)) AS locked",
                          (str(job["tenant_id"]),)).fetchone()["locked"]:
            return None
        active = db.execute("""SELECT count(*) AS n FROM worker.jobs
            WHERE tenant_id=%s AND status='RUNNING' AND lease_until>=now()""", (job["tenant_id"],)).fetchone()["n"]
        if active >= 2:
            return None
        if job["executions"] >= 5:
            failed = db.execute("""UPDATE worker.jobs SET status='FAILED',lease_owner=NULL,lease_until=NULL,
                failure_code='EXECUTION_LIMIT',updated_at=now() WHERE tenant_id=%s AND job_id=%s RETURNING *""",
                (job["tenant_id"],job["job_id"])).fetchone()
            emit(db,failed,"FAILED","EXECUTION_LIMIT")
            return None
        job = db.execute("""UPDATE worker.jobs SET status='RUNNING',fence=fence+1,executions=executions+1,
            lease_owner=%s,lease_until=now()+%s*interval '1 second',updated_at=now()
            WHERE tenant_id=%s AND job_id=%s RETURNING *""", (owner,lease_seconds,job["tenant_id"],job["job_id"])).fetchone()
        emit(db,job,"RUNNING")
        return job


def heartbeat(job, lease_seconds=30):
    with database() as db:
        return db.execute("""UPDATE worker.jobs SET lease_until=now()+%s*interval '1 second'
            WHERE tenant_id=%s AND job_id=%s AND fence=%s AND attempt=%s AND lease_owner=%s
            AND status='RUNNING' AND lease_until>now()""",
            (lease_seconds,job["tenant_id"],job["job_id"],job["fence"],job["attempt"],job["lease_owner"])).rowcount == 1


def input_for(job):
    with database() as db:
        row = db.execute("""SELECT input FROM core.worker_job_inputs WHERE tenant_id=%s AND job_id=%s
            AND case_id IS NOT DISTINCT FROM %s AND attempt=%s AND input_hash=%s""",
            (job["tenant_id"],job["job_id"],job["case_id"],job["attempt"],job["input_hash"])).fetchone()
        if not row:
            raise ValueError("STALE_INPUT")
        return row["input"]


def finish(job, artifact):
    with database() as db:
        updated = db.execute("""UPDATE worker.jobs SET status='SUCCEEDED',lease_owner=NULL,lease_until=NULL,
            failure_code=NULL,updated_at=now() WHERE tenant_id=%s AND job_id=%s AND attempt=%s AND fence=%s
            AND lease_owner=%s AND status='RUNNING' AND lease_until>now() RETURNING job_id""",
            (job["tenant_id"],job["job_id"],job["attempt"],job["fence"],job["lease_owner"])).fetchone()
        if not updated:
            return False
        if job["kind"] == "INGESTION":
            from .ingestion import persist
            persist(db, job, artifact)
        elif job["kind"] in ("EXTRACTION","REVIEW"):
            from .assistant import persist
            persist(db, job, artifact)
        else:
            db.execute("""INSERT INTO worker.artifacts(tenant_id,job_id,attempt,fence,object_key,sha256,byte_size)
                VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (job["tenant_id"],job["job_id"],job["attempt"],job["fence"],artifact["key"],artifact["sha256"],artifact["size"]))
        emit(db,job,"SUCCEEDED")
        return True


def fail(job, code, permanent=False):
    terminal = permanent or job["executions"] >= 5
    status = "FAILED" if terminal else "RETRY_WAIT"
    delay = min(120, 2 ** job["executions"]) + random.uniform(0, 1)
    with database() as db:
        updated = db.execute("""UPDATE worker.jobs SET status=%s,failure_code=%s,lease_owner=NULL,lease_until=NULL,
            available_at=now()+%s*interval '1 second',updated_at=now()
            WHERE tenant_id=%s AND job_id=%s AND attempt=%s AND fence=%s AND lease_owner=%s
            AND status='RUNNING' AND lease_until>now() RETURNING job_id""",
            (status,code,delay,job["tenant_id"],job["job_id"],job["attempt"],job["fence"],job["lease_owner"])).fetchone()
        if updated:
            emit(db,job,status,code)
        return bool(updated)
