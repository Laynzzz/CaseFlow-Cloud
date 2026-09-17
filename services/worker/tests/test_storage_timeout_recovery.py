"""Real socket timeouts at template read and after durable object upload."""
from hashlib import sha256
from io import BytesIO
import json
import time
from uuid import uuid4

from docx import Document
import pytest

from caseflow_worker import jobs, render, runtime
from caseflow_worker.settings import database
from test_process_recovery import uploaded_document, object_bytes
from storage_timeout_probe import storage_timeout


def current_state():
    with database() as db:
        return dict(
            job=db.execute('SELECT * FROM worker.jobs').fetchone(),
            artifacts=db.execute('SELECT * FROM worker.artifacts').fetchall(),
            success=db.execute("SELECT count(*) AS n FROM worker.outbox WHERE payload->>'status'='SUCCEEDED'").fetchone()['n'],
            retries=db.execute("SELECT count(*) AS n FROM worker.outbox WHERE payload->>'status'='RETRY_WAIT'").fetchone()['n'],
        )


@pytest.mark.parametrize('boundary', ['template-read', 'upload-response'])
def test_storage_timeout_retries_without_selecting_partial_result(uploaded_document, boundary,
                                                                 monkeypatch, record_testsuite_property):
    event, client = uploaded_document
    jobs.schedule(event)
    first = jobs.claim(uuid4())
    worker = runtime.Runtime.__new__(runtime.Runtime)
    original_storage = render.storage
    started = time.monotonic()
    with storage_timeout(client, event, boundary) as fault:
        monkeypatch.setattr(render, 'storage', lambda: fault.client)
        worker.execute(first)
        assert fault.received.is_set(), 'timeout endpoint must receive an actual request'
        assert fault.timeouts == ['ReadTimeoutError'], 'must observe a network timeout, not a fake exception'
        assert not fault.errors, fault.errors
        failed = current_state()
        assert failed['job']['status'] == 'RETRY_WAIT'
        assert failed['job']['failure_code'] == 'DEPENDENCY_UNAVAILABLE'
        assert failed['job']['lease_owner'] is None
        assert failed['artifacts'] == [] and failed['success'] == 0 and failed['retries'] == 1
        assert jobs.claim(uuid4()) is None, 'backoff must delay immediate retry'
        orphan = fault.uploaded
        assert (orphan is not None) == (boundary == 'upload-response')
        if orphan:
            assert fault.upload_acknowledged_at <= fault.timed_out_at
            assert sha256(object_bytes(client, orphan['key'])).hexdigest() == orphan['sha256']
        record_testsuite_property(boundary + '-timeout', json.dumps(dict(
            boundary=boundary, network_errors=fault.timeouts, orphan=orphan,
            failure_code=failed['job']['failure_code'], status=failed['job']['status'],
            upload_acknowledged_before_timeout=(fault.upload_acknowledged_at <= fault.timed_out_at) if orphan else None,
            elapsed_seconds=round(time.monotonic()-started, 3))))

    monkeypatch.setattr(render, 'storage', original_storage)
    deadline = time.monotonic() + 8
    second = None
    while time.monotonic() < deadline and second is None:
        second = jobs.claim(uuid4())
        if second is None:
            time.sleep(0.05)
    assert second is not None, 'actual retry backoff must expire without changing SQL timestamps'
    assert second['fence'] > first['fence'] and second['executions'] == 2
    assert second['attempt'] == first['attempt']
    worker.execute(second)
    result = current_state()
    assert result['job']['status'] == 'SUCCEEDED' and result['success'] == 1
    assert len(result['artifacts']) == 1
    selected = result['artifacts'][0]
    content = object_bytes(client, selected['object_key'])
    assert sha256(content).hexdigest() == selected['sha256']
    text = '\n'.join(p.text for p in Document(BytesIO(content)).paragraphs)
    assert 'Synthetic crash-test supplies' in text and 'USD 70.00' in text and '{{' not in text
    if orphan:
        assert selected['object_key'] != orphan['key']
        assert sha256(object_bytes(client, orphan['key'])).hexdigest() == orphan['sha256']
        assert not jobs.finish(first, dict(key=orphan['key'], sha256=orphan['sha256'], size=orphan['size']))
    assert not jobs.fail(first, 'DELAYED_TIMEOUT', True)
    assert current_state()['job']['status'] == 'SUCCEEDED'
    record_testsuite_property(boundary + '-recovery', json.dumps(dict(
        status=result['job']['status'], executions=second['executions'],
        first_fence=first['fence'], recovered_fence=second['fence'],
        selected_key=selected['object_key'], selected_sha256=selected['sha256'],
        elapsed_seconds=round(time.monotonic()-started, 3))))
