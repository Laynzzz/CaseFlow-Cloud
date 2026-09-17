# Task 1 report: worker recovery contracts

## Status

DONE. The worker recovery contracts are covered with real SQL against guarded,
per-test PostgreSQL databases. No production defect was reproduced, so
`caseflow_worker/jobs.py` and `caseflow_worker/runtime.py` remain unchanged.

## Files

- Added `services/worker/tests/test_recovery.py`.
- Added this report.
- No documentation, Java, production Python, dependency, or credential changes.

## Contracts exercised

1. A scheduling transaction forced to raise immediately before context exit
   rolls back both `worker.inbox` and `worker.jobs`; replay writes exactly one
   row to each table.
2. A completion transaction whose `jobs.emit` raises leaves the job `RUNNING`,
   with zero artifacts and zero success outbox rows; replay commits one artifact
   and one success event.
3. A consumer retries the same record after a scheduling transaction rollback,
   without another poll or an early offset commit, and durable scheduling stays
   unique.
4. A synchronous offset commit failure retries the same record before another
   poll; the inbox and job each remain unique.
5. A malformed record is not committed when the first dead-letter send fails.
   The retry sends only reason, SHA-256, and broker coordinates. The synthetic
   source body and its field name are absent.
6. A publisher acknowledgement followed by an injected database rollback sends
   the same event ID again. The second transaction marks the one real outbox row
   published.

The consumer, stop event, and send doubles have hard bounds. Database state is
read through the worker role, while the existing fixture creates, migrates, and
drops databases only when their names match `caseflow_test_<32 hex>`.

## Commands and outcomes

Environment loading was silent so secrets did not enter command output:

```powershell
. ./scripts/dev-env.ps1 *> $null
$env:PYTHONPATH = Join-Path (Get-Location) 'services/worker'
```

Baseline before adding recovery tests:

```powershell
services/worker/.venv/Scripts/python.exe -m pytest services/worker/tests/test_jobs.py -q
```

Outcome: `6 passed in 1.52s`, exit code 0.

Initial new recovery suite:

```powershell
services/worker/.venv/Scripts/python.exe -m pytest services/worker/tests/test_recovery.py -q
```

Outcome: `6 passed in 1.18s`, exit code 0. Existing production behavior already
satisfied these contracts, so no production code was changed.

Final focused verification after strengthening the consumer rollback test:

```powershell
services/worker/.venv/Scripts/python.exe -m pytest services/worker/tests/test_recovery.py services/worker/tests/test_jobs.py -q
```

Outcome: final fresh run `12 passed in 2.46s`, exit code 0, with 0 failures
and 0 skips. An earlier identical focused run passed in 2.32s.

## Mutation evidence

For a targeted negative control, `Runtime.consume()` was temporarily changed to
call synchronous `consumer.commit(...)` immediately after parsing and before
`jobs.schedule(envelope)`. The mutation was not retained.

Command:

```powershell
services/worker/.venv/Scripts/python.exe -m pytest services/worker/tests/test_recovery.py::test_consumer_retries_schedule_before_acknowledging_record -q
```

Outcome: exit code 1, `1 failed in 0.49s`. The early commit set the controlled
consumer's stop state, so scheduling ran once instead of the required rollback
and replay (`assert 1 == 2`). This demonstrates that the test detects an offset
acknowledgement moved ahead of durable scheduling. The mutation was removed
immediately, and the final 12-test run above passed.

## Limits

- Failure injection uses deterministic Python exceptions at transaction and
  acknowledgement boundaries; it does not kill a worker process.
- Transport doubles prove local control flow and stable event identity, not
  Kafka broker delivery, durability, partition rebalancing, or restart behavior.
- This task does not execute the 10,000-redelivery matrix, database/broker
  restarts, object-store timeout recovery, load tests, or cloud rollback.
- An acknowledgement-before-database-commit crash can publish the same event
  more than once. The contract intentionally promises an idempotent business
  effect, not exactly-once transport.
- No live AI call or shared AI budget was used.

## Review follow-up: exact dead-letter payload

Review identified that the original malformed-message check asserted the reason,
hash, and absence of two literal source strings only on the successful retry. It
did not prove that both attempts contained every broker coordinate or excluded
all additional fields. The test now asserts both attempted payloads equal this
complete allowed structure: `reason`, `sha256`, `topic`, `partition`, and
`offset`.

Focused assertion command after the change:

```powershell
services/worker/.venv/Scripts/python.exe -m pytest services/worker/tests/test_recovery.py::test_malformed_message_is_acknowledged_only_after_dead_letter_send -q
```

Outcome: `1 passed in 0.20s`, exit code 0.

For a second targeted negative control, the production payload was temporarily
mutated to omit `topic`. The mutation was not retained. The same focused command
exited 1 with this failure excerpt:

```text
>       assert sends == [expected, expected]
E       AssertionError: assert [{'reason': '... 'offset': 7}] == [{'reason': '...ion': 0, ...}]
E         At index 0 diff: {'reason': 'INVALID_REQUEST_ENVELOPE_OR_REFERENCE', 'sha256': '1b8fe1b6ffac9bb2e3ab202be033860f21ed90b6650c449a93e7ed12f793568d', 'partition': 0, 'offset': 7} != {'reason': 'INVALID_REQUEST_ENVELOPE_OR_REFERENCE', 'sha256': '1b8fe1b6ffac9bb2e3ab202be033860f21ed90b6650c449a93e7ed12f793568d', 'topic': 'caseflow.jobs.v1', 'partition': 0, 'offset': 7}
FAILED services/worker/tests/test_recovery.py::test_malformed_message_is_acknowledged_only_after_dead_letter_send
1 failed in 0.35s
```

After restoring `topic`, the requested focused recovery-suite verification was:

```powershell
services/worker/.venv/Scripts/python.exe -m pytest services/worker/tests/test_recovery.py -q
```

Final output: `6 passed in 1.19s`, exit code 0, with 0 failures and 0 skips.
