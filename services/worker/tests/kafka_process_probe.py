"""Test-only local Kafka/process harness; production identities are forbidden."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import multiprocessing
import os
import re
import time
from uuid import uuid4

from confluent_kafka import Consumer, Producer, TopicPartition
from confluent_kafka.admin import AdminClient, NewTopic
from process_probe import guard_database

BROKER = '127.0.0.1:9092'
BOUNDARIES = {'consume-before-offset', 'consume-after-offset', 'consume-recover',
              'publish-before-mark', 'publish-after-mark', 'publish-recover'}


def guard_broker(topic, group):
    if os.getenv('KAFKA_BOOTSTRAP_SERVERS', BROKER) != BROKER:
        raise ValueError('broker probe requires loopback Kafka')
    if not all(re.fullmatch(r'caseflow_test_python_[a-f0-9]{32}', name) for name in (topic, group)):
        raise ValueError('probe requires isolated broker topic and group')


def consumer_options(group):
    return {'bootstrap.servers': BROKER, 'group.id': group,
            'enable.auto.commit': False, 'enable.auto.offset.store': False,
            'auto.offset.reset': 'earliest', 'session.timeout.ms': 6000,
            'heartbeat.interval.ms': 2000, 'allow.auto.create.topics': False}


def coordinate(message):
    return dict(topic=message.topic(), partition=message.partition(), offset=message.offset())


class BrokerFixture:
    def __init__(self):
        self.topic = 'caseflow_test_python_' + uuid4().hex
        self.group = 'caseflow_test_python_' + uuid4().hex
        self.consumed = False

    def __enter__(self):
        guard_database()
        guard_broker(self.topic, self.group)
        self.admin = AdminClient({'bootstrap.servers': BROKER})
        self.admin.create_topics([NewTopic(self.topic, num_partitions=1, replication_factor=1)],
                                 request_timeout=10)[self.topic].result(12)
        return self

    def __exit__(self, *_):
        guard_broker(self.topic, self.group)
        try:
            if self.consumed:
                # A killed member expires at the broker; wait only on this owned group.
                deadline = time.monotonic() + 15
                while True:
                    try:
                        self.admin.delete_consumer_groups([self.group], request_timeout=5)[self.group].result(6)
                        break
                    except Exception as error:
                        from confluent_kafka import KafkaException, KafkaError
                        if not isinstance(error, KafkaException):
                            raise
                        if error.args[0].code() == KafkaError.GROUP_ID_NOT_FOUND:
                            break
                        if error.args[0].code() != KafkaError.NON_EMPTY_GROUP or time.monotonic() >= deadline:
                            raise
                        time.sleep(0.25)
        finally:
            self.admin.delete_topics([self.topic], request_timeout=10)[self.topic].result(12)

    def send(self, payload):
        producer = Producer({'bootstrap.servers': BROKER, 'acks': 'all',
                             'enable.idempotence': True, 'message.timeout.ms': 10000})
        records, errors = [], []
        def delivered(error, message):
            (errors if error else records).append(type(error).__name__ if error else coordinate(message))
        producer.produce(self.topic, partition=0, value=payload, on_delivery=delivered)
        assert producer.flush(12) == 0 and not errors and len(records) == 1
        return records[0]

    def committed(self):
        observer = Consumer(consumer_options(self.group))
        try:
            result = observer.committed([TopicPartition(self.topic, 0)], timeout=10)[0]
            assert result.error is None
            return result.offset
        finally:
            observer.close()

    def high_watermark(self):
        observer = Consumer(consumer_options(self.group))
        try:
            return observer.get_watermark_offsets(TopicPartition(self.topic, 0), timeout=10)[1]
        finally:
            observer.close()

    def records(self, expected):
        observer = Consumer(consumer_options(self.group))
        try:
            observer.assign([TopicPartition(self.topic, 0, 0)])
            records = []
            deadline = time.monotonic() + 12
            while len(records) < expected and time.monotonic() < deadline:
                message = observer.poll(0.25)
                if message is not None:
                    assert message.error() is None
                    records.append(dict(coordinate(message), eventId=json.loads(message.value())['eventId']))
            assert len(records) == expected
            return records
        finally:
            observer.close()


def child_main(pipe, topic, group, boundary):
    try:
        guard_database()
        guard_broker(topic, group)
        from caseflow_worker import runtime
        runtime.REQUEST_TOPIC = runtime.COMPLETION_TOPIC = runtime.DEAD_TOPIC = topic
        worker = runtime.Runtime()
        metadata = {'sent_event': None}

        def checkpoint():
            pipe.send(dict(boundary=boundary, pid=os.getpid(),
                           reached_at=datetime.now(timezone.utc).isoformat(), **metadata))
            if not pipe.poll(35):
                raise TimeoutError('owned child release deadline')
            assert pipe.recv() == 'RELEASE'

        if boundary.startswith('consume-'):
            class ObservedConsumer:
                def __init__(self, options):
                    self.real = Consumer(dict(options, **consumer_options(group)))
                def subscribe(self, topics):
                    assert topics == [topic]
                    self.real.subscribe(topics)
                def poll(self, timeout):
                    return self.real.poll(timeout)
                def commit(self, *, message, asynchronous):
                    metadata['record'] = coordinate(message)
                    if boundary == 'consume-before-offset':
                        checkpoint()
                    result = self.real.commit(message=message, asynchronous=asynchronous)
                    assert result and all(item.error is None for item in result)
                    if boundary == 'consume-after-offset':
                        checkpoint()
                    worker.stop.set()
                def close(self):
                    self.real.close()
            runtime.Consumer = ObservedConsumer
            worker.consume()
        else:
            real_send = worker.send
            def observed_send(destination, key, payload):
                assert destination == topic
                real_send(destination, key, payload)
                metadata['sent_event'] = payload['eventId']
                if boundary == 'publish-before-mark':
                    checkpoint()
            worker.send = observed_send
            real_database = runtime.database
            @contextmanager
            def observed_database():
                with real_database() as db:
                    yield db
                if boundary == 'publish-after-mark':
                    checkpoint()
                worker.stop.set()
            runtime.database = observed_database
            worker.publish()
        worker.producer.flush(5)
        pipe.send(dict(boundary=boundary, pid=os.getpid(), finished=True, **metadata))
    except Exception as error:
        pipe.send(dict(error_type=type(error).__name__, boundary=boundary))
        raise
    finally:
        pipe.close()


def run_child(fixture, boundary, *, kill):
    guard_database()
    guard_broker(fixture.topic, fixture.group)
    if boundary not in BOUNDARIES:
        raise ValueError('unknown broker crash boundary')
    fixture.consumed |= boundary.startswith('consume-')
    context = multiprocessing.get_context('spawn')
    parent, child = context.Pipe()
    process = context.Process(target=child_main, args=(child, fixture.topic, fixture.group, boundary))
    try:
        process.start()
        child.close()
        assert parent.poll(30), 'child did not reach broker boundary before deadline'
        evidence = parent.recv()
        assert 'error_type' not in evidence, evidence.get('error_type')
        assert evidence['pid'] == process.pid and evidence['boundary'] == boundary
        if kill:
            assert not evidence.get('finished') and process.is_alive()
            process.terminate()
        process.join(10)
        assert not process.is_alive(), 'owned child did not terminate'
        if kill:
            assert process.exitcode not in (None, 0), 'normal exit is not crash evidence'
        else:
            assert process.exitcode == 0 and evidence.get('finished')
        return dict(evidence, exit_code=process.exitcode,
                    termination='Process.terminate' if kill else 'normal',
                    ended_at=datetime.now(timezone.utc).isoformat())
    finally:
        if process.pid is not None:
            if process.is_alive():
                process.kill()
                process.join(5)
            assert not process.is_alive(), 'owned child cleanup failed'
            process.close()
        parent.close()
        child.close()
