"""Operator-only budget configuration. Does not call the provider or print secrets."""
import argparse
from decimal import Decimal
import os
import psycopg

if __name__ == "__main__":
    parser=argparse.ArgumentParser(description="Set an explicitly approved lifetime and tenant-day AI ceiling in USD. Zero disables new calls.")
    parser.add_argument("--total-usd",type=Decimal,required=True)
    parser.add_argument("--tenant-daily-usd",type=Decimal,required=True)
    args=parser.parse_args()
    if any(not value.is_finite() or value<0 or value>1000 or value.as_tuple().exponent < -6 for value in (args.total_usd,args.tenant_daily_usd)):
        parser.error("Each limit must be a finite USD amount from 0 to 1000, with at most six decimals")
    with psycopg.connect(host=os.getenv("DB_HOST","127.0.0.1"),port=int(os.getenv("DB_PORT","54320")),dbname=os.getenv("DB_NAME","caseflow"),
                        user="caseflow_migrator",password=os.environ["DB_MIGRATOR_PASSWORD"]) as db:
        db.execute("SELECT pg_advisory_xact_lock(846201)")
        db.execute("UPDATE worker.ai_budget SET total_limit_usd=%s,tenant_daily_limit_usd=%s WHERE id=true",(args.total_usd,args.tenant_daily_usd))
        spent=db.execute("SELECT COALESCE(sum(COALESCE(actual_usd,reserved_usd)),0) FROM worker.ai_calls").fetchone()[0]
    print(f"AI total ceiling USD {args.total_usd}; tenant/day USD {args.tenant_daily_usd}; settled/reserved USD {spent}. No model call was made.")
