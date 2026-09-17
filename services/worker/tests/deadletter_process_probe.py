"""Owned-process poison-message probes; delegates all handling to Runtime.consume."""
from datetime import datetime, timezone
import multiprocessing
import os

from confluent_kafka import Consumer
from kafka_process_probe import consumer_options, coordinate, guard_broker
from process_probe import guard_database

BOUNDARIES = {'dead-before-send', 'dead-after-ack', 'dead-recover'}


def child_main(pipe, topic, group, dead_topic, boundary):
    try:
        guard_database()
        guard_broker(topic, group)
        guard_broker(dead_topic, group)
        from caseflow_worker import runtime
        runtime.REQUEST_TOPIC = topic
        runtime.DEAD_TOPIC = dead_topic
        worker = runtime.Runtime()
        metadata = {'acknowledged': False}

        def checkpoint():
            pipe.send(dict(boundary=boundary, pid=os.getpid(),
                           reached_at=datetime.now(timezone.utc).isoformat(), **metadata))
            if not pipe.poll(35):
                raise TimeoutError('owned child release deadline')
            assert pipe.recv() == 'RELEASE'

        real_send = worker.send
        def observed_send(destination, key, payload):
            assert destination == dead_topic and key == 'invalid-request'
            if boundary == 'dead-before-send':
                checkpoint()
            real_send(destination, key, payload)
            metadata['acknowledged'] = True
            if boundary == 'dead-after-ack':
                checkpoint()
        worker.send = observed_send

        class ObservedConsumer:
            def __init__(self, options):
                self.real = Consumer(dict(options, **consumer_options(group)))
            def subscribe(self, topics):
                assert topics == [topic]
                self.real.subscribe(topics)
            def poll(self, timeout):
                message = self.real.poll(timeout)
                if message is not None and not message.error():
                    metadata['record'] = coordinate(message)
                return message
            def commit(self, *, message, asynchronous):
                assert metadata['acknowledged'], 'source offset committed before dead-letter acknowledgement'
                result = self.real.commit(message=message, asynchronous=asynchronous)
                assert result and all(item.error is None for item in result)
                worker.stop.set()
            def close(self):
                self.real.close()
        runtime.Consumer = ObservedConsumer
        worker.consume()
        worker.producer.flush(5)
        pipe.send(dict(boundary=boundary, pid=os.getpid(), finished=True, **metadata))
    except Exception as error:
        # No exception traceback: connection failures can embed inherited secrets.
        pipe.send(dict(error_type=type(error).__name__, boundary=boundary))
        raise SystemExit(2) from None
    finally:
        pipe.close()


def run_child(source, dead, boundary, *, kill):
    guard_database()
    guard_broker(source.topic, source.group)
    guard_broker(dead.topic, source.group)
    if boundary not in BOUNDARIES:
        raise ValueError('unknown dead-letter boundary')
    source.consumed = True
    context = multiprocessing.get_context('spawn')
    parent, child = context.Pipe()
    process = context.Process(target=child_main,
                              args=(child, source.topic, source.group, dead.topic, boundary))
    try:
        process.start()
        child.close()
        assert parent.poll(30), 'owned child boundary deadline'
        evidence = parent.recv()
        assert 'error_type' not in evidence, evidence.get('error_type')
        assert evidence['pid'] == process.pid and evidence['boundary'] == boundary
        if kill:
            assert not evidence.get('finished') and process.is_alive()
            process.terminate()
        process.join(10)
        assert not process.is_alive()
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
            assert not process.is_alive()
            process.close()
        parent.close()
        child.close()
