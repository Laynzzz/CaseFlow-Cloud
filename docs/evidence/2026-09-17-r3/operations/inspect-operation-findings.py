import json, os
import psycopg
from psycopg.rows import dict_row
from pathlib import Path
report = json.loads(Path('output/r3-operations-local-report.json').read_text())
with psycopg.connect(host='127.0.0.1',port=54320,dbname='caseflow',user='caseflow_migrator',password=os.environ['DB_MIGRATOR_PASSWORD'],row_factory=dict_row) as db:
    db.execute('SET TRANSACTION READ ONLY')
    observations=[]
    for finding in report['findings']:
        case=finding['caseId']
        observations.append(dict(case=db.execute('SELECT id,state,created_at,updated_at,document_status,generation_id FROM core.cases WHERE id=%s',(case,)).fetchone(),
            jobs=db.execute('SELECT job_id,kind,attempt,status,created_at FROM core.job_requests WHERE case_id=%s',(case,)).fetchall(),
            audit=db.execute('SELECT event_type,created_at FROM core.audit WHERE case_id=%s ORDER BY created_at',(case,)).fetchall(),
            events=db.execute('SELECT event_type,created_at,published_at FROM core.outbox WHERE case_id=%s ORDER BY created_at',(case,)).fetchall()))
    print(json.dumps(observations,default=str,indent=2))
