"""Opt-in actual dependency restarts; never run against caseflow-local services.

Catches lost outbox events, premature publish marking, committing Kafka offsets
before scheduling commits, and retry-loop termination after a DB/broker outage.
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sys
import threading
import time
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb
import pytest
from confluent_kafka import Consumer, Producer, TopicPartition
from confluent_kafka.admin import AdminClient, NewTopic

from restart_probe import BROKER, Dependencies, ROOT, until

sys.path.insert(0, str(ROOT / "services/worker"))
from caseflow_worker import jobs, runtime
from caseflow_worker.settings import database

pytestmark = pytest.mark.skipif(os.getenv("CASEFLOW_RESTART_TESTS") != "1",
                                reason="explicit CASEFLOW_RESTART_TESTS=1 required")


@pytest.fixture(scope="module")
def dependencies():
    stack = Dependencies()
    try:
        stack.open()
        yield stack
    finally:
        stack.close()


@pytest.fixture
def fixture(dependencies, monkeypatch):
    name = "caseflow_test_" + uuid4().hex
    admin = dict(host="127.0.0.1", port=55432, user="caseflow_admin", dbname="caseflow",
                 password=os.environ["DB_ADMIN_PASSWORD"], connect_timeout=5)
    with psycopg.connect(**admin, autocommit=True) as db:
        db.execute(sql.SQL("CREATE DATABASE {} OWNER caseflow_migrator").format(sql.Identifier(name)))
    migrator = dict(admin, dbname=name, user="caseflow_migrator", password=os.environ["DB_MIGRATOR_PASSWORD"])
    with psycopg.connect(**migrator) as db:
        for path in sorted((ROOT / "db/migrations").glob("V*__*.sql"), key=lambda p: int(p.name.split("__")[0][1:])):
            db.execute(path.read_text(encoding="utf-8"))
        tenant, actor, case, job = [uuid4() for _ in range(4)]
        db.execute("INSERT INTO core.identities(id,issuer,subject,display_name) VALUES (%s,%s,%s,'Synthetic restart')",
                   (actor, "https://restart.synthetic.invalid", str(actor)))
        db.execute("INSERT INTO core.tenants(id,name) VALUES (%s,'Synthetic restart')", (tenant,))
        db.execute("INSERT INTO core.memberships(tenant_id,user_id,roles) VALUES (%s,%s,ARRAY['REQUESTER'])", (tenant, actor))
        db.execute("INSERT INTO core.cases(tenant_id,id,owner_id,purchase) VALUES (%s,%s,%s,%s)", (tenant, case, actor, Jsonb({})))
        db.execute("""INSERT INTO core.job_requests(tenant_id,job_id,case_id,kind,input,input_hash,requested_by)
                    VALUES (%s,%s,%s,'DOCUMENT',%s,%s,%s)""", (tenant, job, case, Jsonb({"synthetic": True}), "a" * 64, actor))
    for key, value in dict(DB_HOST="127.0.0.1", DB_PORT="55432", DB_NAME=name).items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(runtime, "BROKER", BROKER)
    topic, group = ("caseflow_restart_" + uuid4().hex for _ in range(2))
    broker_admin = AdminClient({"bootstrap.servers": BROKER})
    broker_admin.create_topics(
        [NewTopic(topic, num_partitions=1, replication_factor=1)], request_timeout=10)[topic].result(12)
    monkeypatch.setattr(runtime, "REQUEST_TOPIC", topic)
    monkeypatch.setattr(runtime, "COMPLETION_TOPIC", topic)
    monkeypatch.setattr(runtime, "DEAD_TOPIC", topic)
    real_consumer = runtime.Consumer
    monkeypatch.setattr(runtime, "Consumer", lambda options: real_consumer(dict(options, **{"group.id": group})))
    event = jobs.Envelope(eventId=uuid4(), eventType="document.requested", schemaVersion=1,
                          timestamp="2026-09-17T00:00:00Z", tenantId=tenant, aggregateId=case,
                          aggregateType="case", aggregateSequence=1, jobId=job, attempt=1,
                          correlationId=job, causationId="synthetic-restart", inputHash="a" * 64, traceContext={})
    logs = []
    real_log = runtime.log
    def observed_log(event, **fields):
        logs.append(dict(event=event, **fields))
        dependencies.record("worker_log", worker_event=event, **fields)
        real_log(event, **fields)
    monkeypatch.setattr(runtime, "log", observed_log)
    dependencies.record("fixture", database=name, topic=topic, group=group, job_id=str(job))
    return dict(stack=dependencies, event=event, topic=topic, group=group, logs=logs)


def state():
    with database() as db:
        return dict(jobs=db.execute("SELECT job_id,status FROM worker.jobs").fetchall(),
                    inbox=db.execute("SELECT event_id FROM worker.inbox").fetchall(),
                    outbox=db.execute("SELECT event_id,published_at FROM worker.outbox").fetchall())


@contextmanager
def running(worker, operation, release=None):
    errors = []
    def target():
        try:
            operation()
        except BaseException as error:
            errors.append(type(error).__name__)
    thread = threading.Thread(target=target, name="restart-worker", daemon=True)
    thread.start()
    try:
        yield thread
        assert not errors, errors
    finally:
        worker.stop.set()
        if release:
            release()
        thread.join(22)
        assert not thread.is_alive(), "restart worker did not stop before deadline"
        assert worker.producer.flush(3) == 0


def options(group):
    return {"bootstrap.servers": BROKER, "group.id": group, "enable.auto.commit": False,
            "enable.auto.offset.store": False, "auto.offset.reset": "earliest"}


def committed(fixture):
    consumer = Consumer(options(fixture["group"]))
    try:
        result = consumer.committed([TopicPartition(fixture["topic"], 0)], timeout=10)[0]
        assert result.error is None
        return result.offset
    finally:
        consumer.close()


def send(fixture):
    producer = Producer({"bootstrap.servers": BROKER, "acks": "all", "message.timeout.ms": 10000})
    acknowledgements = []
    producer.produce(fixture["topic"], value=fixture["event"].model_dump_json(),
                     on_delivery=lambda error, message: acknowledgements.append((error, message.offset())))
    assert producer.flush(12) == 0
    assert len(acknowledgements) == 1 and acknowledgements[0][0] is None
    return acknowledgements[0][1]


def test_kafka_restart_retains_pending_outbox_and_same_runtime_recovers(fixture, record_testsuite_property):
    stack = fixture["stack"]
    assert jobs.schedule(fixture["event"])
    assert jobs.claim(uuid4())
    before = state()
    assert len(before["outbox"]) == 1 and before["outbox"][0]["published_at"] is None
    event_id = str(before["outbox"][0]["event_id"])
    worker = runtime.Runtime()
    server = stack.stop("kafka")
    try:
        with running(worker, worker.publish) as thread:
            until(lambda: any(row.get("error_type") == "KafkaException" and row["event"] == "completion_publish_retry"
                              for row in fixture["logs"]), timeout=23, message="no real unavailable-broker publish failure observed")
            failed = state()
            assert failed["outbox"] == before["outbox"]
            assert len(failed["jobs"]) == len(failed["inbox"]) == 1
            stack.record("kafka_failure_pending_outbox", state=failed, runtime_owner=str(worker.owner))
            stack.start("kafka", server)
            until(lambda: state()["outbox"][0]["published_at"] is not None, timeout=40,
                  message="same runtime failed to publish after broker restart")
            assert thread.is_alive()
            final = state()
            assert len(final["jobs"]) == len(final["inbox"]) == len(final["outbox"]) == 1
            assert str(final["outbox"][0]["event_id"]) == event_id
        observer = Consumer(options(fixture["group"]))
        try:
            observer.assign([TopicPartition(fixture["topic"], 0, 0)])
            message = until(lambda: observer.poll(0.25), timeout=15)
            assert message.error() is None
            assert json.loads(message.value())["eventId"] == event_id
            assert observer.get_watermark_offsets(TopicPartition(fixture["topic"], 0), timeout=10) == (0, 1)
        finally:
            observer.close()
        evidence = dict(event_id=event_id, final=final, runtime_owner=str(worker.owner), broker_records=1)
        stack.record("kafka_recovered", **evidence)
        record_testsuite_property("kafka_restart", json.dumps(evidence, default=str))
    finally:
        if not stack.inspect("kafka")["state"]["Running"]:
            stack.start("kafka", server)


def test_postgres_restart_rolls_back_scheduling_and_same_consumer_replays(fixture, monkeypatch, record_testsuite_property):
    stack = fixture["stack"]
    prepared, release_commit, permit_recovery = (threading.Event() for _ in range(3))
    first = True
    real_database = jobs.database
    @contextmanager
    def transaction_boundary():
        nonlocal first
        pause = first
        first = False
        if not pause:
            assert permit_recovery.wait(45), "recovery observation deadline"
        with real_database() as db:
            yield db
            if pause:
                # SQL really ran, but neither inbox nor job is committed yet.
                prepared.set()
                assert release_commit.wait(30), "database stop coordination deadline"
    monkeypatch.setattr(jobs, "database", transaction_boundary)
    offset = send(fixture)
    worker = runtime.Runtime()
    server = None
    try:
        with running(worker, worker.consume, release=lambda: (release_commit.set(), permit_recovery.set())) as thread:
            assert prepared.wait(20), "production scheduling did not reach transaction boundary"
            assert committed(fixture) < offset + 1
            server = stack.stop("postgres")
            release_commit.set()
            until(lambda: any(row["event"] == "scheduling_retry" and row.get("error_type") in
                              {"OperationalError", "AdminShutdown"} for row in fixture["logs"]),
                  timeout=10, message="no actual failed database commit observed")
            assert committed(fixture) < offset + 1
            stack.start("postgres", server)
            rolled_back = state()
            assert rolled_back == {"jobs": [], "inbox": [], "outbox": []}
            stack.record("postgres_transaction_rolled_back", state=rolled_back, uncommitted_offset=committed(fixture))
            permit_recovery.set()
            until(lambda: committed(fixture) == offset + 1, timeout=20)
            assert thread.is_alive()
            recovered = state()
            assert len(recovered["jobs"]) == len(recovered["inbox"]) == 1
            assert recovered["jobs"][0]["status"] == "QUEUED"
            duplicate_offset = send(fixture)
            until(lambda: committed(fixture) == duplicate_offset + 1, timeout=20)
            assert state() == recovered
            evidence = dict(state=recovered, first_offset=offset, duplicate_offset=duplicate_offset,
                            committed_offset=committed(fixture), runtime_owner=str(worker.owner))
            stack.record("postgres_recovered_duplicate_deduplicated", **evidence)
            record_testsuite_property("postgres_restart", json.dumps(evidence, default=str))
    finally:
        release_commit.set()
        permit_recovery.set()
        if server and not stack.inspect("postgres")["state"]["Running"]:
            stack.start("postgres", server)
