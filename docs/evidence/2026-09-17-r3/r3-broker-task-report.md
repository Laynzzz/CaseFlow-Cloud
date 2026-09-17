# R3 broker-redelivery runner task report

## Changes

- `services/worker/tools/replay_document.py`: import-safe fixed-local CLI, bounded `--count` (1..5000 per topic, default 10), finite `--timeout` (0..3600 seconds exclusive at zero), mandatory exclusive new JSON `--output`.
- `services/worker/tests/test_replay_document.py`: 13 focused offline tests.
- No production runtime/service changes, no commits, no live broker production by this task.

## Behavior

The runner reads only `infrastructure/local/generated/document-demo.json` and fixed endpoints `127.0.0.1:54320/caseflow` and `127.0.0.1:9092`. The fixture is the existing synthetic local demo produced by earlier scripts; its canonical UUID shape, filename, raw file SHA-256 and IDs bind the run scope. It does not discover or change other cases.

Preflight requires a terminal successful document in the API and worker, approved business state, matching selected generation, one artifact, one success audit and zero failure audits for the scoped job. Artifact key, stored checksum, attempt, fence and size are validated. It requires exactly one matching original published request with worker receipt and one original published success event with APPLIED API receipt; tenant/case/job/input hash/current attempt/fence must match.

Request and success event IDs and payload content are reused. A single additional failure has a fresh event ID. Every producer acknowledgement records topic/partition/offset; any callback error, incomplete flush, missing delivery, or duplicate acknowledgement coordinate fails. Backpressure polling has the same finite deadline. Count 5000 means 10,000 redeliveries plus one delayed failure, 10,001 messages total.

Read-only `Consumer.committed()` calls inspect the existing `caseflow-worker-v1` and `caseflow-api-completion-v1` groups. The tool never subscribes, assigns, consumes, polls a consumer, or commits/resets offsets. Each acknowledged partition must reach at least its maximum acknowledged offset plus one. Official API reference: https://docs.confluent.io/platform/current/clients/confluent-kafka-python/html/index.html#confluent_kafka.Consumer.committed

The final selected result/business snapshot must exactly equal the baseline, including worker executions, and the fresh delayed-failure receipt must be STALE. Database connections enforce `default_transaction_read_only=on` server-side. The artifact proof compares selected database key/checksum metadata; it does not download/check current object-store bytes.

Evidence is reserved exclusively before network access and checkpointed throughout the run. It records status, timestamps, elapsed time, revision, script hash, fixture hash, event IDs/hashes, counts, callback acknowledgements/errors, partition boundaries, committed offsets, snapshots and assertions. Caught failures retain JSON; exception text is redacted to exception type and selected uppercase internal error code. Assertions not reached are explicitly marked unobserved. Invalid CLI arguments or an unavailable/already-existing output path fail before a report can be reserved. Abrupt OS/process termination may leave the latest RUNNING checkpoint rather than a final result.

## Verification

TDD red: initial import test failed against old script because importing it required psycopg immediately. Additional red tests demonstrated lack of duplicate acknowledgement protection and testable bounded producer helper. Both then passed with implementation.

Command from repository root:

```powershell
$env:PYTHONPATH='services/worker'
services/worker/.venv/Scripts/python.exe -m pytest services/worker/tests/test_replay_document.py -q
```

Result: 13 passed (0.40 seconds). Tests cover import without third-party dependencies or credentials, CLI bounds, canonical fixture IDs, per-partition next-offset arithmetic, missing/wrong group and broker-error rejection, invalid/duplicate acknowledgement coordinates, exclusive report protection, failure redaction, invalid fixture failure evidence, baseline/final invariants, cross-tenant/hash/event reference rejection, unpublished originals, bounded producer backpressure, callback errors, and read-only offset calls.

Read-only local preflight result: `transaction_read_only=on`; all 12 baseline assertions true; `worker_executions=1`; original published request/success receipts validated. No events produced during preflight.

## Commands for parent execution

With DB_MIGRATOR_PASSWORD loaded from the ignored local environment (never print it), select unused output filenames in an existing directory:

```powershell
services/worker/.venv/Scripts/python.exe services/worker/tools/replay_document.py --count 10 --timeout 180 --output docs/evidence/2026-09-17-r3/broker-smoke.json
services/worker/.venv/Scripts/python.exe services/worker/tools/replay_document.py --count 5000 --timeout 600 --output docs/evidence/2026-09-17-r3/broker-10000.json
```

Inspect PASSED status, exact acknowledgement count (21 / 10,001), all delivery/final assertions true, offsetsReached true and lateFailureDisposition STALE. This is bounded synthetic redelivery evidence, not a sustained throughput benchmark, cloud validation, exactly-once transport assertion, or proof of object-store integrity.

Needed from you: nothing right now.
