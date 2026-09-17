"""Real isolated PostgreSQL/S3 cleanup; object aging uses an explicit controlled clock.

Objects are freshly uploaded to a random fixture prefix. Advancing the cleanup
clock proves grace-period decisions without claiming a real 24-hour soak.
"""
from datetime import datetime, timedelta, timezone
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import psycopg
import pytest
from botocore.exceptions import ClientError

from caseflow_worker import jobs, render
from caseflow_worker.settings import BUCKET, database
from test_process_recovery import uploaded_document, object_bytes


@pytest.fixture
def cleanup():
    return importlib.import_module('caseflow_worker.cleanup')


@pytest.fixture
def succeeded(uploaded_document):
    event, client = uploaded_document
    jobs.schedule(event)
    job = jobs.claim(uuid4())
    selected = render.execute(job, jobs.input_for(job))
    assert jobs.finish(job, selected)
    prefix = f'tenants/{event.tenantId}/documents/{event.jobId}/'
    orphan = prefix + f'attempt-1/fence-1/{uuid4()}.docx'
    client.put_object(Bucket=BUCKET, Key=orphan, Body=b'synthetic abandoned upload', IfNoneMatch='*')
    return event, client, selected, orphan


def aged_clock():
    return datetime.now(timezone.utc) + timedelta(hours=25)


def scan(cleanup, succeeded, **kwargs):
    event, client, _, _ = succeeded
    return cleanup.preview(str(event.tenantId), str(event.jobId), client=client,
                           now=kwargs.pop('now', aged_clock()), **kwargs)


def records(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_preview_never_deletes_selected_or_orphan(cleanup, succeeded):
    _, client, selected, orphan = succeeded
    report = scan(cleanup, succeeded)
    assert report['eligible'] and not report['truncated']
    assert [item['key'] for item in report['objects'] if item['reason'] == 'CANDIDATE'] == [orphan]
    assert next(item for item in report['objects'] if item['key'] == selected['key'])['reason'] == 'SELECTED'
    assert object_bytes(client, orphan) == b'synthetic abandoned upload'
    assert object_bytes(client, selected['key'])


def test_apply_deletes_only_old_orphan_with_durable_journal(cleanup, succeeded, tmp_path):
    _, client, selected, orphan = succeeded
    report = scan(cleanup, succeeded)
    path = tmp_path / 'apply.jsonl'
    with cleanup.DeletionJournal(path, report) as journal:
        result = cleanup.apply(report, journal, client=client, now=aged_clock())
    assert result['deleted'] == 1 and result['unknown'] == 0
    with pytest.raises(client.exceptions.NoSuchKey):
        object_bytes(client, orphan)
    assert object_bytes(client, selected['key'])
    lines = records(path)
    assert [line['event'] for line in lines] == ['START', 'DELETE_INTENT', 'DELETE_RESULT', 'FINISHED']
    assert lines[1]['key'] == orphan and lines[2]['outcome'] == 'DELETE_ACKNOWLEDGED'


@pytest.mark.parametrize('mutation', ['FAILED', 'QUEUED', 'RUNNING', 'RETRY_WAIT', 'wrong_kind', 'wrong_fence', 'missing_artifact', 'missing_job', 'bad_selected_key'])
def test_inconsistent_or_nonterminal_jobs_protected(cleanup, succeeded, isolated_database, mutation, tmp_path):
    event, client, _, orphan = succeeded
    report = scan(cleanup, succeeded)
    with psycopg.connect(**isolated_database) as db:
        if mutation == 'missing_job':
            db.execute('DELETE FROM worker.artifacts')
            db.execute('DELETE FROM worker.outbox')
            db.execute('DELETE FROM worker.jobs')
        elif mutation == 'missing_artifact':
            db.execute('DELETE FROM worker.artifacts')
        elif mutation == 'wrong_fence':
            db.execute('UPDATE worker.artifacts SET fence=fence+1')
        elif mutation == 'bad_selected_key':
            db.execute("UPDATE worker.artifacts SET object_key='tenants/foreign/templates/file.docx'")
        elif mutation == 'wrong_kind':
            db.execute("UPDATE worker.jobs SET kind='EXTRACTION'")
        elif mutation == 'RUNNING':
            db.execute("UPDATE worker.jobs SET status='RUNNING',lease_owner=%s,lease_until=now()+interval '1 hour'", (uuid4(),))
        else:
            db.execute('UPDATE worker.jobs SET status=%s', (mutation,))
    assert not scan(cleanup, succeeded)['eligible']
    with cleanup.DeletionJournal(tmp_path / 'state.jsonl', report) as journal:
        result = cleanup.apply(report, journal, client=client, now=aged_clock())
    assert result['deleted'] == 0 and result['skipped'] == 1
    assert object_bytes(client, orphan)


def test_fresh_malformed_and_foreign_keys_are_protected(cleanup, succeeded):
    event, client, _, orphan = succeeded
    prefix = f'tenants/{event.tenantId}/documents/{event.jobId}/'
    for tail in ['attempt-01/fence-1/' + str(uuid4()) + '.docx',
                 'attempt-1/fence-0/' + str(uuid4()) + '.docx',
                 'attempt-1/fence-1/not-a-uuid.docx', 'source.txt',
                 'attempt-1/fence-1/' + str(uuid4()).upper() + '.docx']:
        client.put_object(Bucket=BUCKET, Key=prefix + tail, Body=b'synthetic malformed fixture')
    fresh = scan(cleanup, succeeded, now=datetime.now(timezone.utc))
    assert not any(item['reason'] == 'CANDIDATE' for item in fresh['objects'])
    aged = scan(cleanup, succeeded)
    assert sum(item['reason'] == 'MALFORMED' for item in aged['objects']) == 5
    assert cleanup.classify_key(orphan.replace(str(event.tenantId), str(uuid4())), str(event.tenantId), str(event.jobId)) is None


def test_listing_is_bounded_and_truncation_explicit(cleanup, succeeded):
    report = scan(cleanup, succeeded, limit=1)
    assert len(report['objects']) == 1 and report['truncated']


@pytest.mark.parametrize('tenant,job,hours,limit', [('bad', str(uuid4()), 24, 50),
    (str(uuid4()).upper(), str(uuid4()), 24, 50),
    (str(uuid4()), '../other', 24, 50), (str(uuid4()), str(uuid4()), 23.99, 50),
    (str(uuid4()), str(uuid4()), float('nan'), 50), (str(uuid4()), str(uuid4()), 24, 0)])
def test_invalid_scope_and_limits_refused_before_dependencies(cleanup, tenant, job, hours, limit):
    with pytest.raises(ValueError):
        cleanup.preview(tenant, job, grace_hours=hours, limit=limit)


def test_additional_artifact_reference_protects_key(cleanup, succeeded, event, isolated_database, tmp_path):
    _, client, _, orphan = succeeded
    report = scan(cleanup, succeeded)
    jobs.schedule(event)
    with psycopg.connect(**isolated_database) as db:
        db.execute('''INSERT INTO worker.artifacts(tenant_id,job_id,attempt,fence,object_key,sha256,byte_size)
            VALUES (%s,%s,1,1,%s,%s,1)''', (event.tenantId, event.jobId, orphan, 'b'*64))
    with cleanup.DeletionJournal(tmp_path / 'reference.jsonl', report) as journal:
        result = cleanup.apply(report, journal, client=client, now=aged_clock())
    assert result['skipped'] == 1 and result['deleted'] == 0
    assert object_bytes(client, orphan)


def test_existing_report_refused_without_touching_objects(cleanup, succeeded, tmp_path):
    path = tmp_path / 'exists.jsonl'
    path.write_text('preserve me')
    with pytest.raises(FileExistsError):
        cleanup.DeletionJournal(path, scan(cleanup, succeeded))
    assert path.read_text() == 'preserve me'
    assert object_bytes(succeeded[1], succeeded[3])


def test_intent_flush_failure_prevents_delete(cleanup, succeeded, tmp_path, monkeypatch):
    report = scan(cleanup, succeeded)
    with cleanup.DeletionJournal(tmp_path / 'flush.jsonl', report) as journal:
        def failed_flush(_):
            raise OSError('synthetic disk failure')
        monkeypatch.setattr(cleanup.os, 'fsync', failed_flush)
        with pytest.raises(OSError):
            cleanup.apply(report, journal, client=succeeded[1], now=aged_clock())
    assert object_bytes(succeeded[1], succeeded[3])


def test_delete_acknowledgement_loss_is_unknown_and_stops_batch(cleanup, succeeded, tmp_path):
    _, client, _, orphan = succeeded
    extra = orphan.rsplit('/', 1)[0] + '/' + str(uuid4()) + '.docx'
    client.put_object(Bucket=BUCKET, Key=extra, Body=b'additional synthetic orphan')
    class LostAcknowledgement:
        def __getattr__(self, name):
            return getattr(client, name)
        def delete_object(self, **kwargs):
            client.delete_object(**kwargs)
            raise TimeoutError('synthetic lost acknowledgement')
    report = scan(cleanup, succeeded)
    path = tmp_path / 'unknown.jsonl'
    with cleanup.DeletionJournal(path, report) as journal:
        result = cleanup.apply(report, journal, client=LostAcknowledgement(), now=aged_clock())
    assert result['unknown'] == 1 and result['deleted'] == 0 and result['notAttempted'] == 1
    assert records(path)[2]['outcome'] == 'UNKNOWN'
    remaining = client.list_objects_v2(Bucket=BUCKET, Prefix=report['prefix'])['Contents']
    assert len(remaining) == 2


def test_result_journal_failure_leaves_pending_intent(cleanup, succeeded, tmp_path, monkeypatch):
    report = scan(cleanup, succeeded)
    path = tmp_path / 'crash.jsonl'
    with cleanup.DeletionJournal(path, report) as journal:
        append = journal.append
        def crash_on_result(record):
            if record['event'] == 'DELETE_RESULT':
                raise OSError('synthetic crash before result persistence')
            append(record)
        monkeypatch.setattr(journal, 'append', crash_on_result)
        with pytest.raises(OSError):
            cleanup.apply(report, journal, client=succeeded[1], now=aged_clock())
    assert [line['event'] for line in records(path)] == ['START', 'DELETE_INTENT']
    with pytest.raises(succeeded[1].exceptions.NoSuchKey):
        object_bytes(succeeded[1], succeeded[3])


def test_apply_blocks_selection_races_but_keeps_other_heartbeats_working(cleanup, succeeded, event, tmp_path):
    _, client, _, orphan = succeeded
    jobs.schedule(event)
    other_job = jobs.claim(uuid4())
    report = scan(cleanup, succeeded)
    class RaceProbe:
        def __getattr__(self, name):
            return getattr(client, name)
        def head_object(self, **kwargs):
            assert jobs.heartbeat(other_job), 'cleanup must not block another job heartbeat'
            with database() as db:
                db.execute("SET LOCAL lock_timeout='100ms'")
                with pytest.raises(psycopg.errors.LockNotAvailable):
                    db.execute('''INSERT INTO worker.artifacts(tenant_id,job_id,attempt,fence,object_key,sha256,byte_size)
                        VALUES (%s,%s,1,1,%s,%s,1)''', (event.tenantId, event.jobId, orphan, 'b'*64))
                db.rollback()
            with database() as db:
                db.execute("SET LOCAL lock_timeout='100ms'")
                with pytest.raises(psycopg.errors.LockNotAvailable):
                    db.execute("UPDATE worker.jobs SET status='FAILED' WHERE tenant_id=%s AND job_id=%s",
                               (report['tenant'], report['job']))
                db.rollback()
            return client.head_object(**kwargs)
    with cleanup.DeletionJournal(tmp_path / 'locks.jsonl', report) as journal:
        result = cleanup.apply(report, journal, client=RaceProbe(), now=aged_clock())
    assert result['deleted'] == 1


def test_cleanup_lock_function_has_narrow_privileges(cleanup, event):
    with database() as db:
        assert not db.execute("SELECT has_table_privilege(current_user,'worker.artifacts','UPDATE') AS allowed").fetchone()['allowed']
        assert not db.execute("SELECT has_table_privilege(current_user,'core.cases','SELECT') AS allowed").fetchone()['allowed']
        assert not db.execute("SELECT has_function_privilege('caseflow_api','worker.lock_artifacts_for_cleanup()','EXECUTE') AS allowed").fetchone()['allowed']
        db.execute('SELECT worker.lock_artifacts_for_cleanup()')


@pytest.mark.parametrize('change', ['fresh_clock', 'replaced_object'])
def test_object_rechecked_immediately_before_deletion(cleanup, succeeded, tmp_path, change):
    _, client, _, orphan = succeeded
    report = scan(cleanup, succeeded)
    if change == 'replaced_object':
        client.put_object(Bucket=BUCKET, Key=orphan, Body=b'replaced synthetic bytes')
    now = datetime.now(timezone.utc) if change == 'fresh_clock' else aged_clock()
    path = tmp_path / 'recheck.jsonl'
    with cleanup.DeletionJournal(path, report) as journal:
        result = cleanup.apply(report, journal, client=client, now=now)
    assert result['deleted'] == 0 and result['skipped'] == 1
    assert records(path)[1]['reason'] == ('FRESH' if change == 'fresh_clock' else 'OBJECT_CHANGED')
    assert object_bytes(client, orphan)


def test_cli_defaults_preview_and_requires_exclusive_apply_report(cleanup, succeeded, tmp_path, capsys):
    from tools.cleanup_documents import main
    event, client, _, orphan = succeeded
    argv = ['--tenant', str(event.tenantId), '--job', str(event.jobId)]
    assert main(argv) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['mode'] == 'PREVIEW' and result['eligible']
    assert object_bytes(client, orphan)
    with pytest.raises(SystemExit) as error:
        main(argv + ['--apply'])
    assert error.value.code == 2
    path = tmp_path / 'exists.jsonl'
    path.write_text('preserve existing report')
    assert main(argv + ['--apply', '--report', str(path)]) == 1
    assert path.read_text() == 'preserve existing report'
    assert object_bytes(client, orphan)


@pytest.mark.parametrize('boundary,object_remains', [('intent', True), ('result', False)])
def test_actual_process_exit_preserves_pending_intent(cleanup, succeeded, tmp_path, boundary, object_remains,
                                                     record_testsuite_property):
    report = scan(cleanup, succeeded)
    input_path = tmp_path / 'preview.json'
    input_path.write_text(json.dumps(report))
    path = tmp_path / 'terminated.jsonl'
    probe = Path(__file__).with_name('cleanup_process_probe.py')
    child = subprocess.run([sys.executable, str(probe), str(input_path), str(path), boundary,
                            aged_clock().isoformat()], capture_output=True, text=True, timeout=15, env=os.environ.copy())
    assert child.returncode == 73, child.stderr
    assert [row['event'] for row in records(path)] == ['START', 'DELETE_INTENT']
    if object_remains:
        assert object_bytes(succeeded[1], succeeded[3])
    else:
        with pytest.raises(succeeded[1].exceptions.NoSuchKey):
            object_bytes(succeeded[1], succeeded[3])
    assert object_bytes(succeeded[1], succeeded[2]['key'])
    # The abandoned connection must release all locks after actual termination.
    with database() as db:
        db.execute('SELECT worker.lock_artifacts_for_cleanup()')
    record_testsuite_property('cleanup-process-' + boundary, json.dumps(dict(
        boundary=boundary, exitCode=child.returncode, durableRecords=['START', 'DELETE_INTENT'],
        outcome='PENDING_UNKNOWN', orphanStillPresent=object_remains,
        selectedStillPresent=True, ageEvidence='controlled clock +25h; no real 24h soak')))


def test_real_storage_rejects_conditional_delete_with_wrong_etag(succeeded):
    _, client, _, orphan = succeeded
    original = object_bytes(client, orphan)
    with pytest.raises(ClientError) as error:
        client.delete_object(Bucket=BUCKET, Key=orphan, IfMatch='"00000000000000000000000000000000"')
    assert error.value.response['ResponseMetadata']['HTTPStatusCode'] == 412
    assert object_bytes(client, orphan) == original


def test_cli_runs_from_repository_without_pythonpath():
    env = os.environ.copy()
    env.pop('PYTHONPATH', None)
    command = Path(__file__).parents[1] / 'tools' / 'cleanup_documents.py'
    child = subprocess.run([sys.executable, str(command), '--help'], env=env,
                           capture_output=True, text=True, timeout=10)
    assert child.returncode == 0, child.stderr
    assert '--apply' in child.stdout and '--report' in child.stdout
