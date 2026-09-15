import re
from psycopg.types.json import Jsonb
from .settings import database
from . import ai_provider


def authorized(job):
    with database() as db:
        if not db.execute("SELECT 1 FROM core.worker_ai_eligible WHERE tenant_id=%s AND job_id=%s",(job["tenant_id"],job["job_id"])).fetchone():
            raise ValueError("AI_INPUT_STALE_OR_ACCESS_REVOKED")


def execute(job, source):
    authorized(job)
    query=None
    with database() as db:
        if job["kind"]=="EXTRACTION":
            rows=db.execute("""SELECT id,source_id,page,start_offset,text FROM worker.chunks
                WHERE tenant_id=%s AND source_id=%s ORDER BY ordinal LIMIT 1000""",(job["tenant_id"],job["source_id"])).fetchall()
        else:
            terms=re.findall(r"[A-Za-z0-9]+",source["purchase"].get("description","")+" purchase cost center justification")[:30]
            query=" OR ".join(terms)
            rows=db.execute("""SELECT id,source_id,page,start_offset,text FROM worker.chunks
                WHERE tenant_id=%s AND source_id=ANY(%s::uuid[]) AND search @@ websearch_to_tsquery('english',%s)
                ORDER BY ts_rank_cd(search,websearch_to_tsquery('english',%s)) DESC,source_id,ordinal LIMIT 5""",
                (job["tenant_id"],source["policyIds"],query,query)).fetchall()
    chunks={str(c["id"]):dict(sourceId=str(c["source_id"]),page=c["page"],start=c["start_offset"],text=c["text"]) for c in rows}
    if job["kind"]=="EXTRACTION" and not chunks:raise ValueError("AI_SOURCE_UNAVAILABLE")
    result=ai_provider.request(job,job["kind"],source["purchase"],chunks,lambda:authorized(job))
    # JSONB objects do not preserve insertion/rank order; store rank as an explicit array.
    result.update(revision=source["revision"],evidence=chunks,retrievedChunkIds=list(chunks),retrievalQuery=query,
                  retrievalMethod="postgres-full-text-v1" if job["kind"]=="REVIEW" else "quote-pages-v1")
    result.update(sourceId=source.get("sourceId"),sourceVersion=source.get("sourceVersion"),sourceSha256=source.get("sourceSha256"))
    return result


def persist(db,job,result):
    if not db.execute("SELECT 1 FROM core.worker_ai_eligible WHERE tenant_id=%s AND job_id=%s",(job["tenant_id"],job["job_id"])).fetchone():
        raise ValueError("AI_INPUT_STALE_OR_ACCESS_REVOKED")
    db.execute("INSERT INTO worker.ai_results(tenant_id,job_id,attempt,fence,result) VALUES (%s,%s,%s,%s,%s)",
               (job["tenant_id"],job["job_id"],job["attempt"],job["fence"],Jsonb(result)))
