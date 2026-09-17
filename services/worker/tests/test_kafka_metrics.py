"""Collector contracts use SDK-shaped Admin replies without a live broker or consumer."""
from concurrent.futures import Future
from types import SimpleNamespace as NS
import time

from confluent_kafka import ConsumerGroupTopicPartitions, TopicPartition
from prometheus_client import CollectorRegistry, generate_latest
import pytest

from caseflow_worker.kafka_metrics import KafkaMetrics, PAIRS


def complete(value=None, error=None):
    future = Future()
    if error:
        future.set_exception(error)
    else:
        future.set_result(value)
    return future


class Broker:
    """Only exposes Admin reads: accidental consumer commits have no fake method."""
    def __init__(self, high=10, committed=7, low=0, unknown=False, broken=False):
        self.high, self.committed, self.low = high, committed, low
        self.unknown, self.broken = unknown, broken

    def list_topics(self, *, timeout):
        assert 0 < timeout <= 3
        if self.broken:
            raise TimeoutError('SECRET broker information')
        return NS(topics={topic: NS(error=None, partitions={0: NS(error=None), 1: NS(error=None)}) for topic, _ in PAIRS})

    def describe_consumer_groups(self, groups, *, request_timeout):
        return {group: complete(NS(state=NS(name='DEAD' if self.unknown else 'STABLE'))) for group in groups}

    def list_consumer_group_offsets(self, requests, *, request_timeout):
        assert len(requests) == 1
        request = requests[0]
        return {request.group_id: complete(ConsumerGroupTopicPartitions(request.group_id, [
            TopicPartition(p.topic, p.partition, self.committed) for p in request.topic_partitions]))}

    def list_offsets(self, requests, *, request_timeout):
        return {partition: complete(NS(offset=self.high if spec._value == -1 else self.low)) for partition, spec in requests.items()}


def rendered(broker):
    registry = CollectorRegistry()
    registry.register(KafkaMetrics(admin=broker))
    return generate_latest(registry).decode()


def test_lag_sums_all_partitions_and_has_only_fixed_pair_labels():
    text = rendered(Broker())
    assert 'caseflow_kafka_metrics_up 1.0' in text
    for topic, group in PAIRS:
        assert f'caseflow_kafka_consumer_lag{{group="{group}",topic="{topic}"}} 6.0' in text
    assert 'partition=' not in text


@pytest.mark.parametrize('broker', [Broker(broken=True), Broker(unknown=True), Broker(high=10, committed=11)])
def test_unknown_or_inconsistent_offsets_do_not_claim_zero_lag(broker):
    text = rendered(broker)
    assert 'caseflow_kafka_metrics_up 0.0' in text
    assert 'caseflow_kafka_consumer_lag{' not in text
    assert 'SECRET' not in text


def test_empty_partition_without_committed_offset_has_zero_lag_for_known_group():
    text = rendered(Broker(high=0, committed=-1001))
    assert 'caseflow_kafka_metrics_up 1.0' in text
    assert text.count('} 0.0') == 2


def test_uncommitted_partition_uses_retained_earliest_offset_not_zero():
    text = rendered(Broker(high=10, low=4, committed=-1001))
    assert text.count('} 12.0') == 2


def test_collector_registration_performs_no_network_read():
    collector = KafkaMetrics(admin=Broker(broken=True))
    assert collector.describe() == []


def test_unresolved_admin_future_has_a_bounded_deadline_and_no_lag_samples():
    class DelayedBroker(Broker):
        def describe_consumer_groups(self, groups, *, request_timeout):
            return {group: Future() for group in groups}
    registry = CollectorRegistry()
    registry.register(KafkaMetrics(admin=DelayedBroker(), timeout_seconds=.02))
    started = time.monotonic()
    text = generate_latest(registry).decode()
    assert time.monotonic()-started < .5
    assert 'caseflow_kafka_metrics_up 0.0' in text
    assert 'caseflow_kafka_consumer_lag{' not in text


def test_missing_topic_is_not_reported_as_a_healthy_empty_broker():
    class MissingTopic(Broker):
        def list_topics(self, *, timeout):
            return NS(topics={})
    text = rendered(MissingTopic())
    assert 'caseflow_kafka_metrics_up 0.0' in text
    assert 'caseflow_kafka_consumer_lag{' not in text
