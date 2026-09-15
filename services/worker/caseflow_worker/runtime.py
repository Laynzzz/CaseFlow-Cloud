import hashlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from uuid import uuid4
from confluent_kafka import Consumer, Producer, KafkaException
from pydantic import ValidationError
from . import jobs, render
from .settings import database, BROKER, REQUEST_TOPIC, COMPLETION_TOPIC, DEAD_TOPIC


def log(event, **fields):
    print(json.dumps(dict(timestamp=datetime.now(timezone.utc).isoformat(), service="case-worker",
                          event=event, **fields)), flush=True)


class Runtime:
    def __init__(self):
        self.stop = threading.Event()
        self.owner = uuid4()
        self.producer = Producer({"bootstrap.servers": BROKER, "enable.idempotence": True,
                                  "acks": "all", "message.timeout.ms": 15000})
        self.threads = []

    def start(self):
        for target in (self.consume, self.dispatch, self.publish):
            thread = threading.Thread(target=target, daemon=True, name=target.__name__)
            thread.start()
            self.threads.append(thread)

    def close(self):
        self.stop.set()
        for thread in self.threads:
            thread.join(timeout=20)

    def send(self, topic, key, payload):
        acknowledged = threading.Event()
        errors = []
        def delivered(error, message):
            if error:
                errors.append(error)
            acknowledged.set()
        self.producer.produce(topic, key=key, value=json.dumps(payload), on_delivery=delivered)
        while not acknowledged.is_set():
            self.producer.poll(0.25)
        if errors:
            raise KafkaException(errors[0])

    def consume(self):
        consumer = Consumer({"bootstrap.servers": BROKER, "group.id": "caseflow-worker-v1",
                             "enable.auto.commit": False, "enable.auto.offset.store": False,
                             "auto.offset.reset": "earliest", "max.poll.interval.ms": 300000})
        consumer.subscribe([REQUEST_TOPIC])
        try:
            while not self.stop.is_set():
                message = consumer.poll(1)
                if message is None or message.error():
                    continue
                # Retry this record until durable handling succeeds; never skip it then
                # commit a later offset in the same partition after a database failure.
                while not self.stop.is_set():
                    try:
                        try:
                            envelope = jobs.Envelope.model_validate_json(message.value())
                            jobs.schedule(envelope)
                        except (ValidationError, ValueError):
                            self.send(DEAD_TOPIC, "invalid-request", {
                                "reason": "INVALID_REQUEST_ENVELOPE_OR_REFERENCE",
                                "sha256": hashlib.sha256(message.value()).hexdigest(),
                                "topic": message.topic(), "partition": message.partition(), "offset": message.offset(),
                            })
                        consumer.commit(message=message, asynchronous=False)
                        break
                    except Exception as error:
                        log("scheduling_retry", error_type=type(error).__name__)
                        self.stop.wait(2)
        finally:
            consumer.close()

    def dispatch(self):
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="document") as pool:
            active = set()
            while not self.stop.is_set():
                active = {future for future in active if not future.done()}
                if len(active) < 2:
                    try:
                        job = jobs.claim(self.owner)
                        if job:
                            active.add(pool.submit(self.execute, job))
                    except Exception as error:
                        log("dispatch_retry", error_type=type(error).__name__)
                self.stop.wait(0.5)

    def execute(self, job):
        finished = threading.Event()
        def renew():
            while not finished.wait(5):
                try:
                    if not jobs.heartbeat(job):
                        return
                except Exception:
                    return  # Never revive a lost lease; fenced completion will reject it.
        heartbeat = threading.Thread(target=renew, daemon=True)
        heartbeat.start()
        try:
            artifact = render.execute(job, jobs.input_for(job))
            selected = jobs.finish(job, artifact)
            log("document_finished", job_id=str(job["job_id"]), attempt=job["attempt"], fence=job["fence"], selected=selected)
        except Exception as error:
            permanent = isinstance(error, (ValueError, KeyError))
            code = "INVALID_DOCUMENT_INPUT" if permanent else "DEPENDENCY_UNAVAILABLE"
            try:
                jobs.fail(job, code, permanent)
            except Exception:
                log("failure_record_deferred", job_id=str(job["job_id"]))
            log("document_failed", job_id=str(job["job_id"]), code=code)
        finally:
            finished.set()
            heartbeat.join(timeout=1)

    def publish(self):
        while not self.stop.is_set():
            try:
                with database() as db:
                    row = db.execute("""SELECT * FROM worker.outbox WHERE published_at IS NULL
                        ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1""").fetchone()
                    if row:
                        self.send(COMPLETION_TOPIC, str(row["tenant_id"])+":"+row["payload"]["aggregateId"], row["payload"])
                        db.execute("UPDATE worker.outbox SET published_at=now() WHERE event_id=%s", (row["event_id"],))
            except Exception as error:
                log("completion_publish_retry", error_type=type(error).__name__)
            self.stop.wait(0.5)
