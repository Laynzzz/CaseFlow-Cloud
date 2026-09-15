import hashlib
from uuid import uuid5, NAMESPACE_URL
from psycopg.types.json import Jsonb
from .parsing import isolated_parse, MAX_BYTES
from .settings import storage, BUCKET


def execute(job, source):
    if source["sourceId"] != str(job["source_id"]) or source["tenantId"] != str(job["tenant_id"]):
        raise ValueError("INVALID_SOURCE_OWNER")
    client = storage()
    response = client.get_object(Bucket=BUCKET, Key=source["key"])
    with response["Body"] as stream:
        if response["ContentLength"] > MAX_BYTES:
            raise ValueError("SOURCE_SIZE_LIMIT")
        data = stream.read(MAX_BYTES+1)
    if len(data) != source["byteSize"] or hashlib.sha256(data).hexdigest() != source["sha256"]:
        raise ValueError("SOURCE_CHECKSUM_MISMATCH")
    return isolated_parse(data, source["mediaType"])


def persist(db, job, result):
    db.execute("""INSERT INTO worker.ingestions(tenant_id,source_id,job_id,attempt,fence,
        source_sha256,parser_version,chunk_version,page_count,warnings) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (job["tenant_id"],job["source_id"],job["job_id"],job["attempt"],job["fence"],result["sourceSha256"],
         result["parserVersion"],result["chunkVersion"],result["pageCount"],Jsonb(result["warnings"])))
    with db.cursor() as cursor:
        cursor.executemany("""INSERT INTO worker.chunks(tenant_id,source_id,id,ordinal,page,section,start_offset,end_offset,text,sha256)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""", [
            (job["tenant_id"],job["source_id"],uuid5(NAMESPACE_URL,f"caseflow:{job['tenant_id']}:{job['source_id']}:{result['chunkVersion']}:{c['ordinal']}"),
             c["ordinal"],c["page"],c["section"],c["start"],c["end"],c["text"],c["sha256"]) for c in result["chunks"]])
