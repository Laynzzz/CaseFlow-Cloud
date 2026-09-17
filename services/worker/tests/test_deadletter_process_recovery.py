"""Real Kafka dead-letter acknowledgements and original offsets across actual kills."""
import hashlib
import json
import time
from uuid import uuid4

import pytest
from confluent_kafka import Consumer, TopicPartition

from caseflow_worker.settings import database
from deadletter_process_probe import run_child
from kafka_process_probe import BrokerFixture, consumer_options, coordinate


def dead_records(fixture, expected, source_coordinate, digest, sentinel):
    observer = Consumer(consumer_options(fixture.group))
    try:
        observer.assign([TopicPartition(fixture.topic, 0, 0)])
        assert observer.get_watermark_offsets(TopicPartition(fixture.topic, 0), timeout=10)[1] == expected
        records = []
        deadline = time.monotonic() + 12
        while len(records) < expected and time.monotonic() < deadline:
            message = observer.poll(0.25)
            if message is None:
                continue
            assert message.error() is None
            if sentinel.encode() in message.value():
                pytest.fail('raw poison content reached dead-letter topic')
            assert message.key() == b'invalid-request'
            payload = json.loads(message.value())
            assert set(payload) == {'reason', 'sha256', 'topic', 'partition', 'offset'}
            assert payload == dict(source_coordinate, reason='INVALID_REQUEST_ENVELOPE_OR_REFERENCE', sha256=digest)
            records.append(coordinate(message))
        assert len(records) == expected
        return records
    finally:
        observer.close()


def assert_no_business_effects():
    with database() as db:
        for table in ('worker.jobs', 'worker.inbox', 'worker.outbox', 'worker.artifacts'):
            assert db.execute('SELECT count(*) AS n FROM ' + table).fetchone()['n'] == 0


@pytest.mark.parametrize('boundary', ['dead-before-send', 'dead-after-ack'])
def test_poison_deadletter_process_recovery(isolated_database, boundary, record_testsuite_property):
    sentinel = 'synthetic-private-poison-' + uuid4().hex
    payload = json.dumps({'privateContent': sentinel}).encode()
    digest = hashlib.sha256(payload).hexdigest()
    with BrokerFixture() as source, BrokerFixture() as dead:
        original = source.send(payload)
        killed = run_child(source, dead, boundary, kill=True)
        assert killed['record'] == original
        assert killed['acknowledged'] == (boundary == 'dead-after-ack')
        assert source.committed() < original['offset'] + 1
        initial_count = 1 if boundary == 'dead-after-ack' else 0
        before = dead_records(dead, initial_count, original, digest, sentinel)
        assert_no_business_effects()
        recovered = run_child(source, dead, 'dead-recover', kill=False)
        assert recovered['record'] == original and recovered['acknowledged']
        assert source.committed() == original['offset'] + 1
        after = dead_records(dead, initial_count + 1, original, digest, sentinel)
        assert len({item['offset'] for item in after}) == len(after)
        assert_no_business_effects()
        evidence = dict(killed=killed, recovered=recovered, original=original,
                        dead_before=before, dead_after=after, committed=source.committed(),
                        redaction_verified=True, business_effects=0)
        encoded = json.dumps(evidence)
        if sentinel in encoded:
            pytest.fail('raw poison content reached evidence')
        record_testsuite_property(boundary, encoded)
