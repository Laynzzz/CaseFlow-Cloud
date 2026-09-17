"""Bounded redelivery evidence for the existing synthetic local document demo.

Not a load benchmark. No database writes, consumer subscriptions, offset changes,
cloud access, or model calls. Set DB_MIGRATOR_PASSWORD and use the worker venv.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "infrastructure/local/generated/document-demo.json"
BROKER = "127.0.0.1:9092"
GROUPS = {"caseflow.jobs.v1": "caseflow-worker-v1",
          "caseflow.completions.v1": "caseflow-api-completion-v1"}
HASH = re.compile(r"[a-f0-9]{64}")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def bounded_count(value):
    count = int(value)
    if not 1 <= count <= 5000:
        raise argparse.ArgumentTypeError("count must be 1..5000 per topic")
    return count


def bounded_timeout(value):
    seconds = float(value)
    if not math.isfinite(seconds) or not 0 < seconds <= 3600:
        raise argparse.ArgumentTypeError("timeout must be finite and in (0, 3600] seconds")
    return seconds


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=bounded_count, default=10,
                        help="duplicates per request/completion topic, 1..5000 (default 10)")
    parser.add_argument("--timeout", type=bounded_timeout, default=180,
                        help="overall probe deadline in seconds, maximum 3600 (default 180)")
    parser.add_argument("--output", type=Path, required=True, help="new JSON evidence file; never overwritten")
    return parser.parse_args(argv)


def validate_fixture(value):
    if not isinstance(value, dict) or set(value) != {"tenantId", "caseId", "jobId"}:
        raise ValueError("INVALID_FIXTURE")
    for item in value.values():
        if not isinstance(item, str) or str(UUID(item)) != item:
            raise ValueError("INVALID_FIXTURE_ID")
    return value


def state_assertions(state, fixture):
    artifact = state.get("artifact") or {}
    prefix = (f'tenants/{fixture["tenantId"]}/documents/{fixture["jobId"]}/'
              f'attempt-{state.get("worker_attempt")}/fence-{state.get("worker_fence")}/')
    key = artifact.get("object_key", "")
    suffix = key.removeprefix(prefix).removesuffix(".docx")
    try:
        valid_key = key.startswith(prefix) and key.endswith(".docx") and str(UUID(suffix)) == suffix
    except (ValueError, AttributeError):
        valid_key = False
    return dict(
        terminalSuccess=state.get("core_status") == state.get("worker_status") == "SUCCEEDED",
        approvedDocument=state.get("business_state") == "APPROVED" and state.get("document_status") == "SUCCEEDED",
        selectedJob=state.get("generation_id") == fixture["jobId"],
        oneArtifact=state.get("artifact_count") == 1,
        oneSuccessAudit=state.get("success_audits") == 1,
        noFailureAudit=state.get("failure_audits") == 0,
        sameAttempt=state.get("core_attempt") == state.get("worker_attempt") == artifact.get("attempt") and artifact.get("attempt", 0) > 0,
        sameFence=state.get("core_fence") == state.get("worker_fence") == artifact.get("fence") and artifact.get("fence", 0) > 0,
        inputHash=bool(HASH.fullmatch(state.get("core_input_hash", ""))) and state.get("core_input_hash") == state.get("worker_input_hash"),
        artifactHash=bool(HASH.fullmatch(artifact.get("sha256", ""))),
        immutableArtifactKey=valid_key,
        artifactSize=isinstance(artifact.get("byte_size"), int) and artifact["byte_size"] > 0,
    )


def final_assertions(baseline, final, fixture, disposition):
    return dict(**state_assertions(final, fixture), unchanged=baseline == final,
                lateFailureStale=disposition == "STALE")


def delivery_boundaries(acknowledgements):
    boundaries = {}
    seen = set()
    for ack in acknowledgements:
        topic, partition, offset = ack["topic"], ack["partition"], ack["offset"]
        if topic not in GROUPS or not isinstance(partition, int) or partition < 0 or not isinstance(offset, int) or offset < 0:
            raise ValueError("INVALID_ACKNOWLEDGEMENT")
        coordinate = (topic, partition, offset)
        if coordinate in seen:
            raise ValueError("DUPLICATE_ACKNOWLEDGEMENT")
        seen.add(coordinate)
        key = (topic, partition)
        if key not in boundaries:
            boundaries[key] = dict(topic=topic, partition=partition, first=offset, last=offset,
                                   acknowledged=0, requiredCommitted=offset + 1, group=GROUPS[topic])
        row = boundaries[key]
        row.update(first=min(row["first"], offset), last=max(row["last"], offset),
                   acknowledged=row["acknowledged"] + 1, requiredCommitted=max(row["last"], offset) + 1)
    return [boundaries[key] for key in sorted(boundaries)]


def offsets_reached(boundaries, committed):
    observed = {(row["group"], row["topic"], row["partition"]): row for row in committed}
    return bool(boundaries) and all(
        (row := observed.get((bound["group"], bound["topic"], bound["partition"]))) is not None
        and row.get("error") is None and row["offset"] >= bound["requiredCommitted"]
        for bound in boundaries)


def remaining(deadline, limit=5):
    seconds = deadline - time.monotonic()
    if seconds <= 0:
        raise TimeoutError("PROBE_DEADLINE")
    return min(seconds, limit)


def database(deadline):
    import psycopg
    from psycopg.rows import dict_row
    # Server-enforced read-only transactions, including all preflight queries.
    seconds = remaining(deadline)
    return psycopg.connect(host="127.0.0.1", port=54320, dbname="caseflow", user="caseflow_migrator",
                           password=os.environ["DB_MIGRATOR_PASSWORD"], row_factory=dict_row,
                           connect_timeout=max(1, math.ceil(seconds)),
                           options=f"-c default_transaction_read_only=on -c statement_timeout={max(1, int(seconds * 1000))}")


def read_state(db, fixture):
    tenant, case, job = (fixture[key] for key in ("tenantId", "caseId", "jobId"))
    state = db.execute("""SELECT r.status AS core_status,j.status AS worker_status,
        c.state AS business_state,c.document_status,c.generation_id::text,
        r.attempt AS core_attempt,j.attempt AS worker_attempt,r.last_fence AS core_fence,
        j.fence AS worker_fence,j.executions AS worker_executions,r.input_hash AS core_input_hash,j.input_hash AS worker_input_hash
        FROM core.job_requests r JOIN worker.jobs j USING (tenant_id,job_id)
        JOIN core.cases c ON c.tenant_id=r.tenant_id AND c.id=r.case_id
        WHERE r.tenant_id=%s AND r.case_id=%s AND r.job_id=%s
          AND r.kind='DOCUMENT' AND j.kind='DOCUMENT' AND j.case_id=r.case_id""", (tenant, case, job)).fetchone()
    if state is None:
        raise ValueError("MISSING_SCOPED_DOCUMENT_JOB")
    artifacts = db.execute("SELECT attempt,fence,object_key,sha256,byte_size FROM worker.artifacts WHERE tenant_id=%s AND job_id=%s",
                           (tenant, job)).fetchall()
    counts = db.execute("""SELECT count(*) FILTER (WHERE event_type='DOCUMENT_SUCCEEDED') AS success_audits,
        count(*) FILTER (WHERE event_type='DOCUMENT_FAILED') AS failure_audits FROM core.audit
        WHERE tenant_id=%s AND case_id=%s AND details->>'jobId'=%s""", (tenant, case, job)).fetchone()
    return dict(state, **counts, artifact_count=len(artifacts), artifact=artifacts[0] if len(artifacts) == 1 else None)


def validate_events(db, fixture, state):
    tenant, case, job = (fixture[key] for key in ("tenantId", "caseId", "jobId"))
    requests = db.execute("""SELECT o.event_id::text,o.payload,o.published_at IS NOT NULL AS published,
        EXISTS(SELECT 1 FROM worker.inbox i WHERE i.event_id=o.event_id) AS received
        FROM core.outbox o WHERE tenant_id=%s AND case_id=%s AND event_type='document.requested'
        AND payload->>'jobId'=%s AND payload->>'attempt'=%s""", (tenant, case, job, str(state["core_attempt"]))).fetchall()
    completions = db.execute("""SELECT o.event_id::text,o.payload,o.published_at IS NOT NULL AS published,
        (SELECT disposition FROM core.event_inbox i WHERE i.event_id=o.event_id) AS disposition
        FROM worker.outbox o WHERE tenant_id=%s AND job_id=%s AND payload->>'status'='SUCCEEDED'
        AND payload->>'attempt'=%s""", (tenant, job, str(state["core_attempt"]))).fetchall()
    if len(requests) != 1 or len(completions) != 1:
        raise ValueError("AMBIGUOUS_OR_MISSING_ORIGINAL_EVENTS")
    request, success = requests[0], completions[0]
    if not request["published"] or not request["received"] or not success["published"] or success["disposition"] != "APPLIED":
        raise ValueError("ORIGINAL_EVENTS_NOT_ACKNOWLEDGED_AND_APPLIED")
    for row, event_type in ((request, "document.requested"), (success, "document.succeeded")):
        event = row["payload"]
        expected = dict(eventId=row["event_id"], eventType=event_type, tenantId=tenant,
                        aggregateId=case, aggregateType="case", jobId=job, schemaVersion=1,
                        attempt=state["core_attempt"], inputHash=state["core_input_hash"])
        if any(event.get(key) != value for key, value in expected.items()):
            raise ValueError("INVALID_ORIGINAL_EVENT_REFERENCE")
    if success["payload"].get("fence") != state["core_fence"] or success["payload"].get("status") != "SUCCEEDED":
        raise ValueError("INVALID_COMPLETION_FENCE")
    return request["payload"], success["payload"]


def read_committed(consumers, boundaries, deadline):
    from confluent_kafka import TopicPartition
    # committed retrieves offsets without subscribing, assigning, polling or committing.
    committed = []
    for group, consumer in consumers.items():
        partitions = [TopicPartition(row["topic"], row["partition"]) for row in boundaries if row["group"] == group]
        for partition in consumer.committed(partitions, timeout=remaining(deadline)):
            committed.append(dict(group=group, topic=partition.topic, partition=partition.partition,
                                  offset=partition.offset, error=partition.error.name() if partition.error else None))
    return committed


def produce_events(producer, key, request, success, late, count, deadline, report, checkpoint):
    def delivered(error, message):
        if error:
            report["deliveryErrors"].append(dict(code=error.code(), name=error.name()))
        else:
            report["acknowledgements"].append(dict(topic=message.topic(), partition=message.partition(), offset=message.offset()))
    events = [("caseflow.jobs.v1", request), ("caseflow.completions.v1", success)]
    for index in range(count * 2 + 1):
        topic, event = events[index % 2] if index < count * 2 else ("caseflow.completions.v1", late)
        while True:
            remaining(deadline)
            if report["deliveryErrors"]:
                raise RuntimeError("BROKER_DELIVERY_FAILED")
            try:
                producer.produce(topic, key=key, value=canonical(event), on_delivery=delivered)
                report["enqueued"] += 1
                break
            except BufferError:
                producer.poll(remaining(deadline, .1))
        producer.poll(0)
        if (index + 1) % 1000 == 0:
            checkpoint()
    report["unflushed"] = producer.flush(remaining(deadline, 20))
    report["boundaries"] = delivery_boundaries(report["acknowledgements"])
    report["deliveryAssertions"] = dict(noErrors=not report["deliveryErrors"], flushed=report["unflushed"] == 0,
        allAcknowledged=len(report["acknowledgements"]) == count * 2 + 1,
        requestCount=sum(row["topic"] == "caseflow.jobs.v1" for row in report["acknowledgements"]) == count,
        completionCount=sum(row["topic"] == "caseflow.completions.v1" for row in report["acknowledgements"]) == count + 1)
    checkpoint()
    if not all(report["deliveryAssertions"].values()):
        raise RuntimeError("DELIVERY_PROOF_INCOMPLETE")


def run_probe(args, report, checkpoint):
    deadline = time.monotonic() + args.timeout
    fixture_bytes = FIXTURE.read_bytes()
    fixture = validate_fixture(json.loads(fixture_bytes))
    report.update(fixture=fixture, fixturePath=str(FIXTURE.relative_to(ROOT)),
                  fixtureSha256=hashlib.sha256(fixture_bytes).hexdigest())
    with database(deadline) as db:
        report["baseline"] = read_state(db, fixture)
        report["baselineAssertions"] = state_assertions(report["baseline"], fixture)
        checkpoint()
        if not all(report["baselineAssertions"].values()):
            raise ValueError("BASELINE_INVARIANT_FAILED")
        request, success = validate_events(db, fixture, report["baseline"])
    late = dict(success, eventId=str(uuid4()), eventType="document.failed", status="FAILED", failureCode="DELAYED_FAILURE")
    report["events"] = {label: dict(eventId=event["eventId"], sha256=digest(event))
                        for label, event in (("request", request), ("success", success), ("lateFailure", late))}
    checkpoint()
    from confluent_kafka import Consumer, Producer
    producer = Producer({"bootstrap.servers": BROKER, "acks": "all", "enable.idempotence": True,
                         "message.timeout.ms": max(1, min(15000, int(remaining(deadline, 3600) * 1000))),
                         "queue.buffering.max.messages": 1000, "allow.auto.create.topics": False})
    consumers = {}
    try:
        produce_events(producer, fixture["tenantId"] + ":" + fixture["caseId"], request, success, late,
                       args.count, deadline, report, checkpoint)
        for group in GROUPS.values():
            consumers[group] = Consumer({"bootstrap.servers": BROKER, "group.id": group,
                "enable.auto.commit": False, "enable.auto.offset.store": False,
                "allow.auto.create.topics": False, "socket.timeout.ms": 5000})
        while True:
            report["committedOffsets"] = read_committed(consumers, report["boundaries"], deadline)
            report["offsetsReached"] = offsets_reached(report["boundaries"], report["committedOffsets"])
            checkpoint()
            if report["offsetsReached"]:
                break
            time.sleep(remaining(deadline, .25))
        with database(deadline) as db:
            report["final"] = read_state(db, fixture)
            receipt = db.execute("SELECT disposition FROM core.event_inbox WHERE event_id=%s", (late["eventId"],)).fetchone()
        report["lateFailureDisposition"] = receipt["disposition"] if receipt else None
        report["finalAssertions"] = final_assertions(report["baseline"], report["final"], fixture, report["lateFailureDisposition"])
        checkpoint()
        if not all(report["finalAssertions"].values()):
            raise RuntimeError("FINAL_INVARIANT_FAILED")
    finally:
        # Serve callbacks on failed/partial runs without extending the deadline.
        report["unflushed"] = producer.flush(max(0, min(2, deadline - time.monotonic())))
        report["boundaries"] = delivery_boundaries(report["acknowledgements"])
        for consumer in consumers.values():
            consumer.close()


def main(argv=None):
    args = parse_args(argv)
    started = time.monotonic()
    report = dict(schemaVersion=1, runId=str(uuid4()), status="RUNNING", startedAt=utc_now(),
        scope="Existing synthetic local document; repeated event IDs; not a throughput benchmark",
        environment=dict(broker=BROKER, database="127.0.0.1:54320/caseflow", groups=GROUPS),
        countPerTopic=args.count, requestedRedeliveries=args.count * 2, lateFailures=1,
        timeoutSeconds=args.timeout, scriptSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        acknowledgements=[], deliveryErrors=[], enqueued=0, boundaries=[], committedOffsets=[],
        baselineAssertions={"observed": False}, finalAssertions={"observed": False},
        artifactVerification="Selected database object key/checksum metadata; no object-store byte download")
    try:
        output = args.output.open("x", encoding="utf-8")
    except OSError:
        print("Cannot create new evidence file; choose an unused path in an existing directory.", file=sys.stderr)
        return 2
    with output:
        def checkpoint():
            output.seek(0)
            json.dump(report, output, indent=2)
            output.write("\n")
            output.truncate()
            output.flush()
            os.fsync(output.fileno())
        checkpoint()
        try:
            report["revision"] = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                capture_output=True, text=True, check=True, timeout=5).stdout.strip()
            run_probe(args, report, checkpoint)
            report["status"] = "PASSED"
        except (Exception, KeyboardInterrupt) as error:
            # Exception text from drivers can contain secrets or raw purchase values.
            report["status"] = "FAILED"
            report["error"] = dict(type=type(error).__name__)
            if isinstance(error, (ValueError, RuntimeError, TimeoutError)) and re.fullmatch(r"[A-Z_]+", str(error)):
                report["error"]["code"] = str(error)
        finally:
            report.update(finishedAt=utc_now(), elapsedSeconds=round(time.monotonic() - started, 3))
            checkpoint()
    print(f'{report["status"]}: {args.output} ({len(report["acknowledgements"])} acknowledged)')
    return 0 if report["status"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
