"""Read-only cost and safe failure summary; never emits credentials or provider bodies."""
import json
import os
import psycopg

if __name__ == "__main__":
    with psycopg.connect(host=os.getenv("DB_HOST", "127.0.0.1"), port=int(os.getenv("DB_PORT", "54320")),
                        dbname=os.getenv("DB_NAME", "caseflow"), user="caseflow_migrator",
                        password=os.environ["DB_MIGRATOR_PASSWORD"]) as db:
        limits = db.execute("SELECT total_limit_usd,tenant_daily_limit_usd FROM worker.ai_budget WHERE id=true").fetchone()
        rows = db.execute("""SELECT state,error_code,count(*),sum(COALESCE(actual_usd,reserved_usd))
            FROM worker.ai_calls GROUP BY state,error_code ORDER BY state,error_code""").fetchall()
    print(json.dumps(dict(totalLimitUsd=str(limits[0]), tenantDailyLimitUsd=str(limits[1]),
                         accountedUsd=str(sum(row[3] for row in rows)),
                         calls=[dict(state=row[0], errorCode=row[1], count=row[2], accountedUsd=str(row[3])) for row in rows]), indent=2))
