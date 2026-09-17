# Task 2 report: Java completion transaction contracts

Status: **DONE**

Date: 2026-09-16  
Baseline: `3e5820a` on `codex/r2-evaluation`  
Database: local PostgreSQL on `127.0.0.1:54320`; a fresh guarded `caseflow_test_<32 hex>` database per test  
Live AI calls: none

## Files

- Added `services/case-api/src/test/java/dev/caseflow/documents/CompletionHandlerIntegrationTest.java`.
- Added this report.
- `services/case-api/src/main/java/dev/caseflow/documents/CompletionHandler.java` required no production fix and has no final diff.

## Implemented contracts

The fixture applies all migrations as `caseflow_migrator`, creates synthetic approved document cases and worker artifacts, then exercises `CompletionHandler.apply` through a real `TransactionTemplate` and the `caseflow_api` role.

Five database-backed tests prove:

1. A valid success atomically changes `core.job_requests.status` and `core.cases.document_status` to `SUCCEEDED`, records one `APPLIED` inbox receipt, and writes one `DOCUMENT_SUCCEEDED` audit row.
2. An injected exception after `handler.apply` and before transaction commit leaves the committed view at `QUEUED`/`QUEUED` with zero inbox and audit rows. Replay succeeds once; the same event ID is idempotent and a distinct success event is durably `STALE` with `OLDER_EXECUTION`, without another audit effect.
3. A delayed failure after success cannot replace terminal success and is durably classified `STALE` / `OLDER_EXECUTION`; it creates no `DOCUMENT_FAILED` audit row.
4. Future attempt, unproven fence, missing result, and wrong-tenant completion events leave business state unchanged and create durable `QUARANTINED` receipts with `FUTURE_ATTEMPT`, `UNPROVEN_EXECUTION`, `MISSING_RESULT`, and `UNKNOWN_JOB` respectively.
5. Two real API-role transactions overlap for the same event ID. The first holds the case row; the second enters `handler.apply`, passes its initial receipt read, and is observed by an admin-only test observer waiting on a PostgreSQL lock. Releasing the first transaction lets both finish within finite deadlines with one success projection, one applied receipt, and one success audit.

## Commands and outcomes

Environment variables were loaded without printing them:

```powershell
. ./scripts/dev-env.ps1 *> $null
```

The first compilation attempt exposed a checked-exception error in the new concurrency helper. It was corrected in test code before any behavioral conclusion.

Focused full suite, restored production source:

```powershell
. ./scripts/dev-env.ps1 *> $null
./services/case-api/gradlew.bat -p services/case-api test --tests dev.caseflow.documents.CompletionHandlerIntegrationTest --rerun-tasks
```

Outcome: exit code 0, `BUILD SUCCESSFUL in 6s`.

JUnit XML check:

```powershell
$xml = [xml](Get-Content -Raw 'services/case-api/build/test-results/test/TEST-dev.caseflow.documents.CompletionHandlerIntegrationTest.xml')
$xml.testsuite | Select-Object tests,failures,errors,skipped,time
```

Recorded result: 5 tests, 0 failures, 0 errors, 0 skipped, 2.385 seconds.

## Mutation evidence

Negative control: temporarily changed the production document branch from `"DOCUMENT".equals(kind)` to `"MUTATED_DOCUMENT".equals(kind)`, disabling the case document-status projection while leaving the job update intact.

```powershell
. ./scripts/dev-env.ps1 *> $null
./services/case-api/gradlew.bat -p services/case-api test --tests dev.caseflow.documents.CompletionHandlerIntegrationTest.appliesSuccessAtomically --rerun-tasks
```

Outcome: exit code 1; 1 test completed, 1 failed at `CompletionHandlerIntegrationTest.java:231` because the hand-derived expected document status was `SUCCEEDED` and the committed value remained `QUEUED`. The mutation was then restored with `apply_patch`; the full focused suite above passed. Final `git diff` for `CompletionHandler.java` is empty.

## Evidence limits

- Failure injection is a deterministic Java exception immediately before transaction commit, not an operating-system process kill.
- Concurrency uses two local JDBC transactions, a controlled case-row lock, and PostgreSQL `pg_stat_activity` observation. It proves this duplicate pair reached real row-lock contention; it does not establish broker scheduling, Kafka durability, fairness, or high-load behavior.
- Duplicate delivery evidence covers one concurrent pair plus sequential same-ID and distinct-ID replay. It is not the planned 10,000-redelivery R3 load result.
- The test proves database business-effect idempotency at the completion boundary. It does not claim exactly-once transport, worker object-store cleanup, broker restart recovery, or model billing idempotency.
- No live AI, cloud, demo-data mutation, or production credentials were used.

## Commit handoff

No commit was created because the root agent is serializing scoped commits. Suggested scoped message: `test: verify completion transaction recovery`.

## Review correction: deterministic transaction overlap

The initial concurrency version released two executor tasks before either task necessarily entered `TransactionTemplate`. Review correctly identified that one task could commit before the other transaction began, so the test did not support a lock-contention claim.

The corrected test now:

1. Starts the first real API-role transaction and takes `FOR UPDATE` on the synthetic case row.
2. Starts the second real API-role transaction and records its PostgreSQL backend PID immediately before calling `handler.apply`.
3. Uses the existing admin role only as a read-only observer to require that the second backend reports `wait_event_type='Lock'`. Because the handler's inbox lookup precedes its case-row lock, this observation also establishes that the competing handler passed the initial receipt read before being blocked.
4. Releases the first transaction only after the lock wait is observed, then requires both futures to finish inside the existing 8-second future deadlines and 10-second test deadline.
5. Uses `finally` to release the first transaction even when the observation assertion fails, preventing executor cleanup from hanging.

Focused corrected concurrency test:

```powershell
. ./scripts/dev-env.ps1 *> $null
./services/case-api/gradlew.bat -p services/case-api test --tests dev.caseflow.documents.CompletionHandlerIntegrationTest.concurrentDuplicateCompletionHasOneBusinessEffectAndFiniteDeadline --rerun-tasks
```

Outcome after correcting observer permissions: exit code 0, `BUILD SUCCESSFUL in 4s`.

Concurrency-specific negative control: temporarily removed `FOR UPDATE` from the first transaction's controlled lock statement. With no row lock to contend on, the observer could not find a blocked backend and the test failed at the literal `expected: <Lock>` assertion (`CompletionHandlerIntegrationTest.java:240`): 1 test completed, 1 failed, exit code 1, `BUILD FAILED in 9s`. The `FOR UPDATE` clause was restored.

Final focused suite after restoration:

```powershell
. ./scripts/dev-env.ps1 *> $null
./services/case-api/gradlew.bat -p services/case-api test --tests dev.caseflow.documents.CompletionHandlerIntegrationTest --rerun-tasks
```

Outcome: exit code 0, `BUILD SUCCESSFUL in 5s`; JUnit XML records 5 tests, 0 failures, 0 errors, 0 skipped, 2.29 seconds. The production handler still has no diff.
