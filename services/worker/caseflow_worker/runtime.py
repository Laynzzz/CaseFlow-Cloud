import hashlib
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from uuid import uuid4
from confluent_kafka import Consumer, Producer, KafkaException
from pydantic import ValidationError
from . import jobs, render, ingestion, assistant, telemetry
from .settings import database, BROKER, REQUEST_TOPIC, COMPLETION_TOPIC, DEAD_TOPIC


def log(event, **fields):
    print(json.dumps(dict(timestamp=datetime.now(timezone.utc).isoformat(), service="case-worker",
                          event=event, **telemetry.correlation(), **fields)), flush=True)


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
                            with telemetry.span("worker.schedule", envelope.traceContext):
                                jobs.schedule(envelope)
                        except (ValidationError, ValueError):
                            self.send(DEAD_TOPIC, "invalid-request", {
                                "reason": "INVALID_REQUEST_ENVELOPE_OR_REFERENCE",
                                "sha256": hashlib.sha256(message.value()).hexdigest(),
                                "topic": message.topic(), "partition": message.partition(), "offset": message.offset(),
                            })
                            telemetry.events.labels("deadletter", "acknowledged").inc()
                        consumer.commit(message=message, asynchronous=False)
                        break
                    except Exception as error:
                        telemetry.events.labels("schedule", "retry").inc()
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
        with telemetry.span("worker.execute", job.get("trace_context", {})) as span:
            span.set_attribute("job.kind", job["kind"])
            telemetry.queue_seconds.labels(job["kind"]).observe(max(0, (job["updated_at"]-job.get("ready_at", job["available_at"])).total_seconds()))
            if job["executions"] > 1:
                telemetry.events.labels("execute", "retry").inc()
            started = time.monotonic()
            outcome = "deferred"
            try:
                outcome = self._execute(job)
                if outcome in ("failed", "deferred"):
                    span.set_status(telemetry.trace.StatusCode.ERROR)
            finally:
                telemetry.execution_seconds.labels(job["kind"], outcome).observe(time.monotonic()-started)
                span.set_attribute("outcome", outcome)

    def _execute(self, job):
        finished = threading.Event()
        def renew():
            while not finished.wait(5):
                try:
                    if not jobs.heartbeat(job):
                        telemetry.events.labels("lease", "lost").inc()
                        return
                except Exception:
                    telemetry.events.labels("lease", "renewal_failed").inc()
                    return  # Never revive a lost lease; fenced completion will reject it.
        heartbeat = threading.Thread(target=renew, daemon=True)
        heartbeat.start()
        try:
            executor = {"INGESTION":ingestion,"DOCUMENT":render,"EXTRACTION":assistant,"REVIEW":assistant}[job["kind"]]
            artifact = executor.execute(job, jobs.input_for(job))
            selected = jobs.finish(job, artifact)
            log("job_finished", kind=job["kind"], job_id=str(job["job_id"]), attempt=job["attempt"], fence=job["fence"], selected=selected)
            return "succeeded" if selected else "fenced"
        except Exception as error:
            permanent = isinstance(error, (ValueError, KeyError))
            code = "INVALID_DOCUMENT_INPUT" if permanent else "DEPENDENCY_UNAVAILABLE"
            if permanent and job["kind"] in ("EXTRACTION","REVIEW"):
                known_ai={"AI_NOT_CONFIGURED","AI_INPUT_LIMIT","AI_BUDGET_EXCEEDED","STALE_AI_EXECUTION",
                          "AI_CALL_ALREADY_RESERVED","AI_PROVIDER_UNAVAILABLE","AI_REFUSED_OR_INCOMPLETE",
                          "UNEXPECTED_MODEL_VERSION","AI_USAGE_UNAVAILABLE","AI_TOKEN_LIMIT","INVALID_AI_OUTPUT",
                          "AI_INPUT_STALE_OR_ACCESS_REVOKED","AI_SOURCE_UNAVAILABLE","AI_RETRIEVAL_LIMIT","INVALID_EMBEDDING"}
                code=str(error) if str(error) in known_ai else "INVALID_AI_INPUT"
            if permanent and job["kind"] == "INGESTION":
                known = {"SOURCE_SIZE_LIMIT", "SOURCE_PAGE_LIMIT", "SOURCE_TEXT_LIMIT", "NO_EXTRACTABLE_TEXT",
                         "ENCRYPTED_PDF_UNSUPPORTED", "MALFORMED_PDF", "INVALID_UTF8", "BINARY_TEXT_UNSUPPORTED",
                         "UNSUPPORTED_SOURCE_TYPE", "PDF_STREAM_LIMIT", "PARSER_TIME_LIMIT", "PARSER_RESOURCE_LIMIT",
                         "SOURCE_CHECKSUM_MISMATCH", "INVALID_SOURCE_OWNER"}
                code = str(error) if str(error) in known else "INVALID_SOURCE_INPUT"
            try:
                jobs.fail(job, code, permanent)
            except Exception:
                log("failure_record_deferred", job_id=str(job["job_id"]))
            log("job_failed", kind=job["kind"], job_id=str(job["job_id"]), code=code)
            telemetry.events.labels("execute", "validation_failed" if permanent else "dependency_failed").inc()
            return "failed"
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
                        with telemetry.span("worker.publish", row["payload"].get("traceContext", {})):
                            payload = {**row["payload"], "traceContext": telemetry.capture() or row["payload"].get("traceContext", {})}
                            self.send(COMPLETION_TOPIC, str(row["tenant_id"])+":"+payload["aggregateId"], payload)
                            db.execute("UPDATE worker.outbox SET published_at=now() WHERE event_id=%s", (row["event_id"],))
            except Exception as error:
                telemetry.events.labels("publish", "retry").inc()
                log("completion_publish_retry", error_type=type(error).__name__)
            self.stop.wait(0.5)
