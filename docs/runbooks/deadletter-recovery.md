# Poison-envelope diagnosis and recovery

A malformed message must not schedule a purchase job or change an approval.
The consumer publishes redacted diagnosis metadata to its dead-letter topic,
waits for Kafka acknowledgement, and only then commits the original offset.
If it stops after acknowledgement but before that commit, normal restart
replays the original message and may publish the same diagnosis again.
Deduplicate incident records by original topic, partition, offset and digest;
do not interpret duplicate dead letters as additional failed purchases.

## Operator procedure

1. Obtain authorization for the affected environment and incident scope. Record
   the source topic, partition, offset, consumer group, reason and digest from
   the redacted dead letter. Preserve those coordinates throughout diagnosis.
   Keep application payloads, credentials and document text out of tickets,
   terminal transcripts, metrics and evidence archives.
2. Check the consumer's health and committed offset using metadata-only access.
   If the source offset is not committed, restore the failed dependency or
   consumer and let its normal loop retry. Do not advance the offset to skip
   the record. A successful dead-letter acknowledgement allows that loop to
   commit the source offset; a publication failure must leave it retryable.
3. Diagnose the producer/schema/reference defect using the authorized source
   of truth. The dead letter deliberately cannot reconstruct the envelope.
   If investigation requires original content, use a separately authorized,
   narrowly scoped read for the exact coordinate, within the source topic's
   retention window. Do not copy the payload into the redacted incident report.
4. Correct the originating defect and use the existing authorized business
   command or eligible audited job-retry operation. Preserve tenant, logical
   job, revision and attempt rules, and recheck current resource permissions.
   A malformed envelope may have no corresponding job, so the job-retry route
   is not always applicable. Escalate such a case for explicit reconciliation
   against durable business state; do not invent a job or mark one successful.
5. Record the original coordinates, diagnosis, approved corrective action and
   resulting command/job/event references. Verify the new operation's normal
   inbox/business/audit effects and the consumer's progress. A successful
   transport publication by itself does not establish business recovery.

There is no generic production replay command in this repository. Republishing
arbitrary JSON or rewinding a live consumer group can bypass diagnosis and
repeat unrelated work. Neither is this runbook's recovery mechanism. An expired
source record cannot be reconstructed from a digest; retention limits remain
an operational constraint.

## Payload contract and local proof

Python dead letters contain only `reason`, `sha256`, `topic`, `partition` and
`offset`. Java dead letters contain only `reason`, `hash`, `topic`, `partition`
and `offset`. Python hashes the source bytes; Java uses its existing JSON helper
to hash the serialized source string. These digest formats are component
specific and must not be compared as though they used identical encoding.
Neither payload includes raw invalid content, exception details or credentials.

The local tests are
[`test_deadletter_process_recovery.py`](../../services/worker/tests/test_deadletter_process_recovery.py)
and
[`DeadLetterProcessRecoveryTest.java`](../../services/case-api/src/test/java/dev/caseflow/documents/DeadLetterProcessRecoveryTest.java).
They terminate only owned child processes, use isolated Kafka topics/groups and
migrated disposable databases, and validate both before-submission and
after-real-acknowledgement boundaries. These are four named poison-message
crash scenarios across the two languages; cleanup and normal recovery runs do
not add crash-scenario counts. The before-submission case does not claim to
test a network interruption while publication is already in flight.

Run from the repository root with local PostgreSQL and Kafka already available:

```powershell
. ./scripts/dev-env.ps1
$env:PYTHONPATH = (Join-Path (Get-Location) 'services/worker')
$env:CASEFLOW_KAFKA_PROCESS_TESTS = '1'
New-Item -ItemType Directory -Force output/r3-deadletters | Out-Null
services/worker/.venv/Scripts/python.exe -m pytest services/worker/tests/test_deadletter_process_recovery.py -q --tb=short --junitxml=output/r3-deadletters/python-focused.xml
./services/case-api/gradlew.bat -p services/case-api test --tests dev.caseflow.documents.DeadLetterProcessRecoveryTest --rerun-tasks --console plain
```

The environment loader reads ignored local credentials without printing them.
The Java opt-in variable is required; skipped tests are not recovery evidence.
The expected focused result is two Python cases and two Java cases, each with
nonzero forced-child exit, identical replayed source coordinate, a committed
source offset only after acknowledgement, metadata-only dead letters and zero
business effects. Current execution results belong in the dated evidence
summary, separate from this procedure.
