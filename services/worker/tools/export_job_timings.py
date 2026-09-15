"""Export timing-only rows for the assistant jobs named in a synthetic run."""
import argparse
import json
import os
from pathlib import Path
from uuid import UUID
import psycopg
from psycopg.rows import dict_row

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--records',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    records=[json.loads(line) for line in args.records.read_text(encoding='utf-8').splitlines()]
    ids={UUID(row[kind]['jobId']) for row in records for kind in ('extraction','review') if row.get(kind)}
    if not ids:parser.error('No assistant jobs in these records')
    with psycopg.connect(host=os.getenv('DB_HOST','127.0.0.1'),port=int(os.getenv('DB_PORT','54320')),
                        dbname=os.getenv('DB_NAME','caseflow'),user='caseflow_migrator',
                        password=os.environ['DB_MIGRATOR_PASSWORD'],row_factory=dict_row) as db:
        rows=db.execute('''SELECT j.job_id,j.kind,j.status,j.attempt,j.created_at AS requested_at,
            CASE WHEN j.status IN ('SUCCEEDED','FAILED') THEN j.updated_at END AS completed_at,
            w.created_at AS scheduled_at,w.executions,
            (SELECT min(o.created_at) FROM worker.outbox o WHERE o.tenant_id=j.tenant_id AND o.job_id=j.job_id
             AND o.payload->>'status'='RUNNING') AS first_claim_at
            FROM core.job_requests j LEFT JOIN worker.jobs w USING (tenant_id,job_id)
            WHERE j.job_id=ANY(%s::uuid[]) ORDER BY j.created_at,j.job_id''',(list(ids),)).fetchall()
    with args.output.open('x',encoding='utf-8',newline='\n') as output:
        output.write(json.dumps(dict(jobIds=sorted(str(id) for id in ids),jobs=rows,
            scope='Selected synthetic assistant jobs; database transaction timestamps, no purchase content.'),default=str,indent=2)+'\n')
    print(f'Exported timing rows for {len(rows)} synthetic jobs.')
