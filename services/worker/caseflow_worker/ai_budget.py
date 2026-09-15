"""Reserve worst-case spend durably before each transport call; unknown usage stays charged."""
from decimal import Decimal, ROUND_CEILING
from uuid import uuid4
from psycopg.types.json import Jsonb
from .settings import database

MODEL = "gpt-4.1-mini-2025-04-14"
PRICING_VERSION = "openai-standard-2026-09-15"
INPUT_PER_MILLION = Decimal("0.40")
OUTPUT_PER_MILLION = Decimal("1.60")
MAX_INPUT_TOKENS = 32768
MAX_OUTPUT_TOKENS = 4096


def cost(input_tokens, output_tokens):
    return ((Decimal(input_tokens)*INPUT_PER_MILLION+Decimal(output_tokens)*OUTPUT_PER_MILLION)/1_000_000).quantize(Decimal("0.000001"),rounding=ROUND_CEILING)


def reserve(job, purpose):
    upper = cost(MAX_INPUT_TOKENS, MAX_OUTPUT_TOKENS)
    with database() as db:
        # A transaction advisory lock works with a SELECT-only configuration role.
        db.execute("SELECT pg_advisory_xact_lock(846201)")
        limits = db.execute("SELECT * FROM worker.ai_budget WHERE id=true").fetchone()
        lease = db.execute("""SELECT job_id FROM worker.jobs WHERE tenant_id=%s AND job_id=%s
            AND attempt=%s AND fence=%s AND lease_owner=%s AND status='RUNNING' AND lease_until>now() FOR SHARE""",
            (job["tenant_id"],job["job_id"],job["attempt"],job["fence"],job["lease_owner"])).fetchone()
        if not lease:
            raise ValueError("STALE_AI_EXECUTION")
        if db.execute("SELECT id FROM worker.ai_calls WHERE tenant_id=%s AND job_id=%s AND attempt=%s AND fence=%s AND purpose=%s",
                      (job["tenant_id"],job["job_id"],job["attempt"],job["fence"],purpose)).fetchone():
            raise ValueError("AI_CALL_ALREADY_RESERVED")
        usage = db.execute("""SELECT COALESCE(sum(COALESCE(actual_usd,reserved_usd)),0) AS total,
            COALESCE(sum(COALESCE(actual_usd,reserved_usd)) FILTER (WHERE tenant_id=%s
                AND created_at >= date_trunc('day',now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC'),0) AS daily
            FROM worker.ai_calls""",(job["tenant_id"],)).fetchone()
        if not limits or usage["total"]+upper>limits["total_limit_usd"] or usage["daily"]+upper>limits["tenant_daily_limit_usd"]:
            raise ValueError("AI_BUDGET_EXCEEDED")
        call_id=uuid4()
        db.execute("""INSERT INTO worker.ai_calls(id,tenant_id,job_id,attempt,fence,purpose,model,pricing_version,reserved_usd)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (call_id,job["tenant_id"],job["job_id"],job["attempt"],job["fence"],purpose,MODEL,PRICING_VERSION,upper))
        return call_id


def settle(call_id, input_tokens, output_tokens, elapsed_ms, error_code=None):
    known = isinstance(input_tokens,int) and not isinstance(input_tokens,bool) and input_tokens>=0 and isinstance(output_tokens,int) and not isinstance(output_tokens,bool) and output_tokens>=0
    with database() as db:
        db.execute("SELECT pg_advisory_xact_lock(846201)")
        db.execute("""UPDATE worker.ai_calls SET state=%s,input_tokens=%s,output_tokens=%s,actual_usd=%s,elapsed_ms=%s,error_code=%s
            WHERE id=%s AND state='RESERVED'""",("SETTLED" if known else "UNKNOWN",input_tokens if known else None,
            output_tokens if known else None,cost(input_tokens,output_tokens) if known else None,elapsed_ms,error_code,call_id))


def record_response(call_id, evidence, error_code=None):
    """Private, bounded evaluation evidence; never overwrite a previously recorded response."""
    with database() as db:
        db.execute("""UPDATE worker.ai_calls SET response_evidence=%s,error_code=COALESCE(%s,error_code)
            WHERE id=%s AND response_evidence IS NULL""",(Jsonb(evidence),error_code,call_id))
