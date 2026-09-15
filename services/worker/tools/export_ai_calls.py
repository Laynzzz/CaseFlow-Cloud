"""Export private call evidence for explicitly selected synthetic run records only."""
import argparse
import json
import os
from pathlib import Path
from uuid import UUID
import psycopg
from psycopg.rows import dict_row

if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    raw=args.records.read_text(encoding="utf-8")
    records=[json.loads(line) for line in raw.splitlines() if line.strip()] if args.records.suffix==".jsonl" else [json.loads(raw)]
    ids={UUID(row[kind]["jobId"]) for row in records for kind in ("extraction","review") if row.get(kind)}
    if not ids:parser.error("No assistant job IDs found in these records")
    with psycopg.connect(host=os.getenv("DB_HOST","127.0.0.1"),port=int(os.getenv("DB_PORT","54320")),
                        dbname=os.getenv("DB_NAME","caseflow"),user="caseflow_migrator",
                        password=os.environ["DB_MIGRATOR_PASSWORD"],row_factory=dict_row) as db:
        rows=db.execute("""SELECT id,tenant_id,job_id,attempt,fence,purpose,model,pricing_version,
            reserved_usd,actual_usd,input_tokens,output_tokens,state,error_code,elapsed_ms,created_at,response_evidence
            FROM worker.ai_calls WHERE job_id=ANY(%s::uuid[]) ORDER BY created_at,id""",(list(ids),)).fetchall()
    report=dict(jobIds=sorted(str(id) for id in ids),calls=rows,
                accountedUsd=str(sum(row["actual_usd"] if row["actual_usd"] is not None else row["reserved_usd"] for row in rows)),
                scope="Selected synthetic job IDs only; unknown usage retains its reservation")
    with args.output.open("x",encoding="utf-8") as output:
        output.write(json.dumps(report,default=str,indent=2)+"\n")
    print(f"Exported {len(rows)} calls for {len(ids)} synthetic jobs. No credentials or HTTP headers included.")
