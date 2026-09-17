# R3 recovery contracts: first batch

Date: September 16, 2026 local / September 17 UTC. This is a local learning-project
test result, not an R3 release, process-crash matrix or production-readiness claim.

## Scope and environment

Real PostgreSQL transactions run against a fresh migrated database per test,
named `caseflow_test_<32 hex characters>`. Python operations use
`caseflow_worker`; Java operations use `caseflow_api`. The fixture uses the
migrator for setup and validates the disposable name before dropping it.
The Java concurrency check uses a read-only admin connection to observe
`pg_stat_activity`; both competing handler transactions still use the API role.
The running demo's records are not reset. No live AI or cloud resource is used.

Environment: Windows 11, Python 3.12.10, pytest 9.1.1, psycopg 3.3.5,
confluent-kafka 2.15.1, Java 21, Gradle 9.7.1, Spring Boot 4.1.1 and the local
Compose PostgreSQL service on port 54320. Kafka transport in the new Python
tests is substituted with bounded doubles. Java invokes the actual completion
handler inside a real Spring JDBC transaction, without starting its Kafka consumer.

Production code needed no change. The new tests cover existing recovery
contracts. A passing regression test is useful evidence, but does not by itself
demonstrate a newly fixed production defect.

## Boundaries exercised

| Boundary | Injection or delivery | Durable assertion |
| --- | --- | --- |
| Scheduling before commit | Python exception just before transaction context exit | Neither inbox nor job survives; replay creates one of each |
| Scheduling before offset acknowledgement | First scheduling transaction rolls back | No offset commit before durable handling; same record retried before another poll |
| Scheduling after commit, offset unavailable | First synchronous commit call fails | Same record rescheduled, one inbox/job, next commit succeeds |
| Invalid request handling | First dead-letter send fails | No early offset commit; both attempts use the complete redacted reason/hash/topic/partition/offset payload |
| Worker result finalization | Exception while writing completion event | RUNNING status retained; no selected artifact or success event; replay commits one of each |
| Publisher after acknowledgement, before database commit | First real outbox transaction rolls back after fake send acknowledgement | Same event ID sent twice; one outbox row finally marked published |
| Java completion before commit | Exception after handler returns, before transaction commits | Job/case remain QUEUED; no inbox or audit; replay commits all effects together |
| Java sequential duplicate/reordered delivery | Same event ID, distinct success event ID, delayed failure | One success audit and projection; later events cannot replace success |
| Invalid Java completion references | Future attempt, unproven fence, missing result, wrong tenant | Durable quarantine reason; no business/audit mutation |
| Java concurrent duplicates | First API transaction holds the case row; second is observed waiting on a database lock before release | One success projection, applied receipt and success audit |

The six Python cases are in
[`test_recovery.py`](../../../services/worker/tests/test_recovery.py).
The five Java cases are in
[`CompletionHandlerIntegrationTest.java`](../../../services/case-api/src/test/java/dev/caseflow/documents/CompletionHandlerIntegrationTest.java).
Some cases cover several inputs; these are 11 test cases, not 11 killed processes.

## Reproduce

From the repository root, with the local PostgreSQL service running:

```powershell
. ./scripts/dev-env.ps1
$env:PYTHONPATH = Join-Path (Get-Location) 'services/worker'
services/worker/.venv/Scripts/python.exe -m pytest services/worker/tests -q
./services/case-api/gradlew.bat -p services/case-api test --rerun-tasks
```

At source revision `617aee9`, the full worker suite passed **73 tests** in
17.03 seconds; the full Java suite passed **20 tests**, with zero failures,
errors or skipped tests. This includes the new checks and existing assistant,
budget, parsing, rendering and domain checks. Durations are test execution
measurements, not product latency or throughput. The later focused evidence
records the strengthened review assertions separately.

Worker assertion fix `0d241dc`: the root rerun passed all **6 recovery tests**
in 1.27 seconds, zero failures/errors/skips. See
[focused output](worker-recovery-review.txt) and
[JUnit XML](worker-recovery-review.xml).

Java contention fix `0a1ef27`: the root rerun passed all **5 completion tests**
with zero failures/errors/skips in 2.349 seconds (Gradle build: 5 seconds).
See [focused output](java-recovery-review.txt) and
[JUnit XML](java-recovery-review.xml).

Raw outputs: [worker](worker-tests.txt), [Java](java-tests.txt). JUnit XML files
in this directory preserve case names/counts and timestamps; only the machine
hostname is generalized to `local-test-host`. Java compilation retains its
pre-existing unchecked-operation notice; the full suite also reports a JVM
class-data-sharing warning from its test tooling. Neither is a new assertion
failure, and neither was silently removed from the raw output.

## Review and negative controls

Independent task review identified two assertion weaknesses: the malformed
message check did not require the exact complete dead-letter payload, and the
Java concurrency start latch originally preceded transaction creation. The
scoped fix records and focused reruns accompany this batch. The worker test now
checks exact payload equality on both attempts. The Java test requires an actual
PostgreSQL lock wait before releasing the first transaction, so it cannot pass
by merely running two deliveries sequentially.

Implementers temporarily moved offset commit before scheduling and disabled the
Java case-status projection. Each caused its intended regression test to fail;
both mutations were restored. Task reports retain the commands and observations.
Additional controls omitted a dead-letter broker coordinate and removed the
controlled case-row lock; each failed its targeted assertion before restoration.
See the [worker task report](worker-task-report.md) and
[Java task report](java-task-report.md). These are agent-recorded negative
controls, not independent human validation. Root separately reran the final
focused suites; no temporary production mutation remains.

## Remaining evidence gaps

No operating-system process is killed by this batch. It does not establish
actual crash recovery after object upload, result commit, Kafka send or Java
commit; broker rebalance/restart; active-work database restart; object-store
timeout; orphan-object cleanup; or the complete lease-expiry crash matrix.
It does not execute 10,000 redeliveries, controlled query optimization,
sustained mixed load, full tracing/alerts/reconciliation, cloud deployment,
rollback or teardown. The [R3 map](../../r3-status.md) tracks these separately.

The older [20-redelivery broker probe](../2026-09-14-documents/replay.txt)
remains a separate observed result. Do not combine that small probe and these
fake-transport tests into a larger broker-delivery claim. R2 AI also remains
experimental under its [acceptance decision](../2026-09-16-r2/r2-acceptance.md).
