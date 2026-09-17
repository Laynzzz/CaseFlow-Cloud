"""Real broker boundaries in owned worker subprocesses, with isolated topics."""
import json
import os
from uuid import uuid4

import pytest

from caseflow_worker import jobs
from caseflow_worker.settings import database
from kafka_process_probe import BrokerFixture, run_child, guard_broker


@pytest.fixture
def broker(event):
    with BrokerFixture() as fixture:
        yield fixture


def state():
    with database() as db:
        return {
            'jobs': db.execute('SELECT count(*) AS n FROM worker.jobs').fetchone()['n'],
            'inbox': db.execute('SELECT count(*) AS n FROM worker.inbox').fetchone()['n'],
            'outbox': db.execute('SELECT event_id,published_at FROM worker.outbox').fetchall(),
        }


@pytest.mark.parametrize('boundary', ['consume-before-offset', 'consume-after-offset'])
def test_real_offset_recovery(event, broker, boundary, record_testsuite_property):
    first = broker.send(event.model_dump_json())
    killed = run_child(broker, boundary, kill=True)
    record_testsuite_property(boundary, json.dumps(killed))
    assert killed['record'] == first
    assert state()['jobs'] == state()['inbox'] == 1
    before = broker.committed()
    if boundary == 'consume-before-offset':
        assert before < first['offset'] + 1
        expected = first
    else:
        assert before == first['offset'] + 1
        expected = broker.send(event.model_copy(update={'eventId': uuid4()}).model_dump_json())
    recovered = run_child(broker, 'consume-recover', kill=False)
    assert recovered['record'] == expected
    assert broker.committed() == expected['offset'] + 1
    assert state()['jobs'] == 1
    assert state()['inbox'] == (1 if boundary == 'consume-before-offset' else 2)
    record_testsuite_property(boundary + '-recovery', json.dumps(dict(
        before_offset=before, after_offset=broker.committed(), recovered=recovered)))


@pytest.mark.parametrize('boundary', ['publish-before-mark', 'publish-after-mark'])
def test_real_publish_recovery(event, broker, boundary, record_testsuite_property):
    jobs.schedule(event)
    assert jobs.claim(uuid4()) is not None
    initial = state()
    assert len(initial['outbox']) == 1 and initial['outbox'][0]['published_at'] is None
    event_id = str(initial['outbox'][0]['event_id'])
    killed = run_child(broker, boundary, kill=True)
    record_testsuite_property(boundary, json.dumps(killed))
    assert killed['sent_event'] == event_id
    first = broker.records(1)
    assert first[0]['eventId'] == event_id
    assert (state()['outbox'][0]['published_at'] is not None) == (boundary == 'publish-after-mark')
    recovered = run_child(broker, 'publish-recover', kill=False)
    records = broker.records(2 if boundary == 'publish-before-mark' else 1)
    assert [r['eventId'] for r in records] == [event_id] * len(records)
    assert len({r['offset'] for r in records}) == len(records)
    assert broker.high_watermark() == len(records)
    assert recovered['sent_event'] == (event_id if boundary == 'publish-before-mark' else None)
    final = state()
    assert final['jobs'] == final['inbox'] == len(final['outbox']) == 1
    assert final['outbox'][0]['published_at'] is not None
    record_testsuite_property(boundary + '-recovery', json.dumps(dict(records=records, recovered=recovered)))


@pytest.mark.parametrize('topic,group', [
    ('caseflow.jobs.v1', 'caseflow-worker-v1'),
    ('caseflow_test_python_' + 'a' * 32, 'caseflow-worker-v1'),
])
def test_broker_probe_rejects_production_names(topic, group):
    with pytest.raises(ValueError, match='isolated broker'):
        guard_broker(topic, group)


def test_broker_probe_rejects_nonlocal_endpoint(monkeypatch):
    monkeypatch.setenv('KAFKA_BOOTSTRAP_SERVERS', 'remote.invalid:9092')
    name = 'caseflow_test_python_' + uuid4().hex
    with pytest.raises(ValueError, match='loopback'):
        guard_broker(name, name)
