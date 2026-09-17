"""Bounded broker lag reads, independent of business consumer positions/commits.

SDK reference: https://docs.confluent.io/platform/current/clients/confluent-kafka-python/html/index.html
AdminClient.list_consumer_group_offsets supports one group per request.
"""
import threading
import time

from confluent_kafka import ConsumerGroupTopicPartitions, TopicPartition, OFFSET_INVALID
from confluent_kafka.admin import AdminClient, OffsetSpec
from prometheus_client.core import GaugeMetricFamily

from .settings import BROKER

PAIRS = (("caseflow.jobs.v1", "caseflow-worker-v1"),
         ("caseflow.completions.v1", "caseflow-api-completion-v1"))


class KafkaMetrics:
    def __init__(self, *, admin=None, timeout_seconds=3):
        if not 0 < timeout_seconds <= 3:
            raise ValueError("Kafka metrics timeout must be within (0, 3] seconds")
        self._admin = admin
        self._timeout = timeout_seconds
        self._lock = threading.Lock()

    def describe(self):
        return []  # Registry registration never starts broker work.

    def _snapshot(self):
        deadline = time.monotonic() + self._timeout

        def remaining():
            value = deadline - time.monotonic()
            if value <= 0:
                raise TimeoutError("Kafka metrics deadline")
            return value

        if self._admin is None:
            self._admin = AdminClient({"bootstrap.servers": BROKER, "socket.timeout.ms": 3000,
                                       "allow.auto.create.topics": False})
        admin = self._admin
        # Asking for one missing topic can auto-create it on some broker configs.
        metadata = admin.list_topics(timeout=remaining())
        partitions = {}
        for topic, _ in PAIRS:
            description = metadata.topics.get(topic)
            if not description or description.error or not description.partitions:
                raise ValueError("Required topic metadata unavailable")
            if len(description.partitions) > 64 or any(p.error for p in description.partitions.values()):
                raise ValueError("Invalid or excessive topic partitions")
            partitions[topic] = [TopicPartition(topic, index) for index in description.partitions]

        descriptions = admin.describe_consumer_groups([group for _, group in PAIRS], request_timeout=remaining())
        committed = {}
        for topic, group in PAIRS:
            description = descriptions[group].result(timeout=remaining())
            state = getattr(description.state, "name", str(description.state))
            if state not in ("STABLE", "EMPTY", "PREPARING_REBALANCING", "COMPLETING_REBALANCING", "ASSIGNING", "RECONCILING"):
                raise ValueError("Required consumer group unavailable")
            requests = [ConsumerGroupTopicPartitions(group, partitions[topic])]
            result = admin.list_consumer_group_offsets(requests, request_timeout=remaining())[group].result(timeout=remaining())
            if result.group_id != group:
                raise ValueError("Unexpected consumer group")
            offsets = {(p.topic, p.partition): p for p in result.topic_partitions}
            for partition in partitions[topic]:
                offset = offsets.get((topic, partition.partition))
                if offset is None or offset.error or (offset.offset < 0 and offset.offset != OFFSET_INVALID):
                    raise ValueError("Consumer offset unavailable")
                committed[(topic, partition.partition)] = offset.offset

        all_partitions = [partition for entries in partitions.values() for partition in entries]
        # Read end offsets after committed offsets, preventing a normal advancing
        # consumer from appearing ahead of an older end-offset observation.
        starts = admin.list_offsets({p: OffsetSpec.earliest() for p in all_partitions}, request_timeout=remaining())
        ends = admin.list_offsets({p: OffsetSpec.latest() for p in all_partitions}, request_timeout=remaining())
        totals = []
        for topic, group in PAIRS:
            total = 0
            for partition in partitions[topic]:
                low = starts[partition].result(timeout=remaining()).offset
                high = ends[partition].result(timeout=remaining()).offset
                position = committed[(topic, partition.partition)]
                # Both product consumers use earliest reset for a new partition.
                if position == OFFSET_INVALID:
                    position = low
                if not 0 <= low <= position <= high:
                    raise ValueError("Inconsistent broker offsets")
                total += high-position
            totals.append((topic, group, total))
        return totals

    def collect(self):
        up = GaugeMetricFamily("caseflow_kafka_metrics_up", "Both configured topic/group offsets were observed")
        if not self._lock.acquire(blocking=False):
            up.add_metric([], 0)
            yield up
            return
        try:
            snapshot = self._snapshot()
        except Exception:
            snapshot = None
        finally:
            self._lock.release()
        if snapshot is None:
            up.add_metric([], 0)
            yield up
            return
        up.add_metric([], 1)
        yield up
        lag = GaugeMetricFamily("caseflow_kafka_consumer_lag", "Retained records after committed next offset; partition sum",
                                labels=["topic", "group"])
        for topic, group, value in snapshot:
            lag.add_metric([topic, group], value)
        yield lag
