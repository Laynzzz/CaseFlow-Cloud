"""Read-only, metadata-only operational findings using the real worker role."""
import json
import importlib.util
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg.types.json import Jsonb
import pytest

from caseflow_worker import jobs
from caseflow_worker.reconciliation import reconcile
from caseflow_worker.settings import database


def kinds(report):
    return {row['kind'] for row in report['findings']}


def test_recent_work_is_not_reported(event):
    jobs.schedule(event)
    report = reconcile()
    assert report['status'] == 'NO_FINDINGS' and report['findings'] == []
    assert report['truncated'] is False


def test_old_queue_and_expired_lease_are_distinct(event, isolated_database):
    jobs.schedule(event)
    with psycopg.connect(**isolated_database) as db:
        db.execute("UPDATE worker.jobs SET available_at=now()-interval '10 minutes'")
    assert kinds(reconcile()) == {'OVERDUE_JOB'}
    jobs.claim(uuid4())
    with psycopg.connect(**isolated_database) as db:
        db.execute("UPDATE worker.jobs SET lease_until=now()-interval '1 second'")
    report = reconcile()
    assert kinds(report) == {'EXPIRED_LEASE'}
    assert report['findings'][0]['jobId'] == str(event.jobId)


def test_both_outboxes_report_only_old_unpublished_metadata(event, isolated_database):
    jobs.schedule(event)
    jobs.claim(uuid4())
    with psycopg.connect(**isolated_database) as db:
        db.execute("UPDATE worker.outbox SET created_at=now()-interval '10 minutes'")
        db.execute("""INSERT INTO core.outbox(event_id,tenant_id,case_id,event_type,payload,created_at)
            VALUES (%s,%s,%s,'document.requested',%s,now()-interval '10 minutes')""",
                   (uuid4(), event.tenantId, event.aggregateId, Jsonb({'private': 'DO_NOT_EXPORT_CONTENT'})))
    report = reconcile()
    assert kinds(report) == {'API_OUTBOX_PENDING', 'WORKER_OUTBOX_PENDING'}
    assert 'DO_NOT_EXPORT_CONTENT' not in json.dumps(report)
    with psycopg.connect(**isolated_database) as db:
        db.execute('UPDATE core.outbox SET published_at=now()')
        db.execute('UPDATE worker.outbox SET published_at=now()')
    assert reconcile()['findings'] == []


def test_approved_missing_request_and_missing_worker_job(event, isolated_database):
    with psycopg.connect(**isolated_database) as db:
        db.execute("""UPDATE core.cases SET state='APPROVED',generation_id=%s,
            approved_at=now()-interval '10 minutes',updated_at=now()-interval '10 minutes'
            WHERE tenant_id=%s AND id=%s""", (uuid4(), event.tenantId, event.aggregateId))
    assert kinds(reconcile()) == {'APPROVED_MISSING_REQUEST'}
    with psycopg.connect(**isolated_database) as db:
        db.execute('UPDATE core.cases SET generation_id=%s WHERE tenant_id=%s AND id=%s',
                   (event.jobId, event.tenantId, event.aggregateId))
        db.execute("UPDATE core.job_requests SET created_at=now()-interval '10 minutes',updated_at=now()-interval '10 minutes'")
    assert kinds(reconcile()) == {'APPROVED_MISSING_WORKER_JOB'}
    jobs.schedule(event)
    assert reconcile()['findings'] == []


def test_report_limit_is_explicit_and_does_not_change_work(event, isolated_database):
    jobs.schedule(event)
    with psycopg.connect(**isolated_database) as db:
        db.execute("UPDATE worker.jobs SET available_at=now()-interval '10 minutes'")
        for _ in range(3):
            db.execute("INSERT INTO worker.outbox(event_id,tenant_id,job_id,payload,created_at) VALUES (%s,%s,%s,'{}',now()-interval '10 minutes')",
                       (uuid4(),event.tenantId,event.jobId))
    report=reconcile(limit=2)
    assert report['status']=='ATTENTION' and report['truncated'] and len(report['findings'])==2
    assert len(reconcile(limit=10)['findings'])==4
    with database() as db:
        assert db.execute('SELECT status FROM worker.jobs').fetchone()['status']=='QUEUED'
        assert db.execute('SELECT count(*) AS n FROM worker.outbox WHERE published_at IS NULL').fetchone()['n']==3


def test_worker_view_exposes_no_business_content_and_is_read_only(event):
    with database() as db:
        columns=[r.name for r in db.execute('SELECT * FROM core.worker_operation_signals LIMIT 0').description]
        assert columns==['kind','tenant_id','case_id','job_id','event_id','observed_at']
        assert not db.execute("SELECT has_table_privilege(current_user,'core.cases','SELECT') AS allowed").fetchone()['allowed']
        assert not db.execute("SELECT has_table_privilege(current_user,'core.worker_operation_signals','UPDATE') AS allowed").fetchone()['allowed']


@pytest.mark.parametrize('kwargs', [{'age_seconds':0},{'age_seconds':-1},{'limit':0},{'limit':1001}])
def test_report_rejects_unbounded_parameters(kwargs):
    with pytest.raises(ValueError):
        reconcile(**kwargs)


def test_backoff_threshold(event, isolated_database):
    jobs.schedule(event)
    with psycopg.connect(**isolated_database) as db:
        db.execute("UPDATE worker.jobs SET status='RETRY_WAIT',available_at=now()+interval '10 minutes'")
    assert reconcile()['findings'] == []
    with psycopg.connect(**isolated_database) as db:
        db.execute("UPDATE worker.jobs SET available_at=now()-interval '2 minutes'")
    assert reconcile()['findings'] == []
    assert kinds(reconcile(age_seconds=60)) == {'OVERDUE_JOB'}


def test_missing_retry_attempt_is_detected_after_current_attempt_grace(event, isolated_database):
    jobs.schedule(event)
    with psycopg.connect(**isolated_database) as db:
        db.execute("UPDATE worker.jobs SET status='FAILED'")
        db.execute("""UPDATE core.cases SET state='APPROVED',generation_id=%s,
            approved_at=now()-interval '1 day',updated_at=now()-interval '1 day'""", (event.jobId,))
        db.execute("""UPDATE core.job_requests SET attempt=2,created_at=now()-interval '1 day',updated_at=now()""")
    # Original request age must not make a fresh retry immediately overdue.
    assert reconcile()['findings'] == []
    with psycopg.connect(**isolated_database) as db:
        db.execute("UPDATE core.job_requests SET updated_at=now()-interval '10 minutes'")
    assert kinds(reconcile()) == {'APPROVED_MISSING_WORKER_JOB'}
    jobs.schedule(event.model_copy(update={'eventId': uuid4(), 'attempt': 2}))
    assert reconcile()['findings'] == []


@pytest.mark.parametrize('status,code', [('NO_FINDINGS', 0), ('ATTENTION', 2), ('ERROR', 1)])
def test_operator_cli_status_and_redacted_errors(monkeypatch, capsys, status, code):
    path = Path(__file__).resolve().parents[1] / 'tools/reconcile.py'
    spec = importlib.util.spec_from_file_location('reconcile_cli', path)
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    def run(**kwargs):
        assert kwargs == {'age_seconds': 120, 'limit': 3}
        if status == 'ERROR':
            raise RuntimeError('SECRET_DSN_DO_NOT_PRINT')
        return {'status': status, 'findings': [] if status == 'NO_FINDINGS' else [{'kind': 'OVERDUE_JOB'}]}
    monkeypatch.setattr(cli, 'reconcile', run)
    assert cli.main(['--age-seconds', '120', '--limit', '3']) == code
    output = capsys.readouterr().out
    assert 'SECRET_DSN_DO_NOT_PRINT' not in output
    report = json.loads(output)
    assert report['status'] == ('REPORT_FAILED' if status == 'ERROR' else status)
