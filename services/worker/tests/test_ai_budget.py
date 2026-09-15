from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import psycopg
import pytest
from caseflow_worker import ai_budget, jobs
from caseflow_worker.settings import database


def enable(connection, limit):
    with psycopg.connect(**connection) as db:
        db.execute("UPDATE worker.ai_budget SET total_limit_usd=%s,tenant_daily_limit_usd=%s",(limit,limit))


def test_budget_disabled_and_stale_execution_rejected(event, isolated_database):
    jobs.schedule(event);job=jobs.claim(uuid4())
    with pytest.raises(ValueError,match="AI_BUDGET_EXCEEDED"):ai_budget.reserve(job,"extract")
    enable(isolated_database,1)
    stale=dict(job,fence=job["fence"]+1)
    with pytest.raises(ValueError,match="STALE_AI_EXECUTION"):ai_budget.reserve(stale,"extract")


def test_concurrent_reservations_cannot_overspend(event, isolated_database):
    jobs.schedule(event);job=jobs.claim(uuid4())
    upper=ai_budget.cost(ai_budget.MAX_INPUT_TOKENS,ai_budget.MAX_OUTPUT_TOKENS)
    enable(isolated_database,upper)
    def claim(index):
        try:return ai_budget.reserve(job,f"call-{index}")
        except ValueError:return None
    with ThreadPoolExecutor(max_workers=6) as pool:results=list(pool.map(claim,range(6)))
    assert len([x for x in results if x])==1
    selected=next(x for x in results if x)
    ai_budget.settle(selected,None,None,50,"TIMEOUT")
    with pytest.raises(ValueError,match="AI_BUDGET_EXCEEDED"):ai_budget.reserve(job,"retry")
    with database() as db:
        row=db.execute("SELECT state,actual_usd,reserved_usd FROM worker.ai_calls WHERE id=%s",(selected,)).fetchone()
        assert row["state"]=="UNKNOWN" and row["actual_usd"] is None and row["reserved_usd"]==upper


def test_recorded_usage_releases_only_unused_reservation(event,isolated_database):
    jobs.schedule(event);job=jobs.claim(uuid4());enable(isolated_database,1)
    call=ai_budget.reserve(job,"extract")
    with pytest.raises(ValueError,match="AI_CALL_ALREADY_RESERVED"):ai_budget.reserve(job,"extract")
    ai_budget.settle(call,1000,100,400)
    ai_budget.settle(call,0,0,0) # Settled records cannot be rewritten by a duplicate.
    with database() as db:
        row=db.execute("SELECT * FROM worker.ai_calls WHERE id=%s",(call,)).fetchone()
        assert row["actual_usd"]==ai_budget.cost(1000,100) and row["input_tokens"]==1000
