# R3 Java completion JVM termination evidence

Observed 2026-09-17 UTC on Windows, Temurin Java 21.0.12.1 and committed Gradle wrapper 9.7.1. Baseline: `e06f1f1` on `codex/r2-evaluation`; these uncommitted test changes were present during the runs. Fixture version: completion-process-v1 (two owned Java test sources below). No production Java changes, broker interactions, object uploads, cloud operations, or model calls.

## Ready files

- `services/case-api/src/test/java/dev/caseflow/documents/CompletionProcessRecoveryTest.java`: JUnit owner of each disposable database and child JVM, IPC deadline, force termination, replay/state/audit/inbox assertions and cleanup.
- `services/case-api/src/test/java/dev/caseflow/documents/CompletionCrashProbe.java`: Java main executing real `CompletionHandler` and `Commands` in a Spring transaction using `caseflow_api`; boundary signal immediately before transaction completion or after commit returns.
- `services/case-api/build.gradle`: expose `sourceSets.test.runtimeClasspath.asPath` as a test system property, so the spawned Java 21 process can execute the real handler and JDBC driver. A temporary Java argument file avoids Windows command length limits; it contains no secrets and is removed after each test.

## Reproduction

From repository root in PowerShell, with the already configured local PostgreSQL service available:

```powershell
. ./scripts/dev-env.ps1
./services/case-api/gradlew.bat -p services/case-api test --tests dev.caseflow.documents.CompletionProcessRecoveryTest --tests dev.caseflow.documents.CompletionHandlerIntegrationTest --rerun-tasks --console plain
```

`--rerun-tasks` forces actual execution rather than reusing a prior passing result. `--tests` restricts the run to these two completion suites. The local loader reads ignored credentials without printing them; child credentials are inherited through environment variables, never command-line arguments. The new suite explicitly skips if `DB_ADMIN_PASSWORD` is absent and fails if the other required database credentials are missing. A skipped run is not evidence of recovery.

## Observed results

| Run | Tests | Failures | Errors | Skips | Outcome |
| --- | ---: | ---: | ---: | ---: | --- |
| Missing-commit negative control, 03:52:18 UTC | 2 | 1 | 0 | 0 | After-commit test rejected `QUEUED` when `SUCCEEDED` was required |
| Normal-exit negative control, 03:52:46 UTC | 2 | 2 | 0 | 0 | Both tests rejected exit code 0 as crash evidence |
| Restored implementation, first green | 7 | 0 | 0 | 0 | New process suite 2 + existing integration suite 5 |
| Final source with boundary/exit logging, 03:54:00–03:54:06 UTC | 7 | 0 | 0 | 0 | New process suite 2 + existing integration suite 5 |

Final raw evidence: `output/r3-java-process-green-final.txt`, `output/r3-java-process-green-final.xml`, `output/r3-java-completion-regression-green-final.xml`. Gradle exited 0. The final XML records AFTER_COMMIT child PID 46020 and BEFORE_COMMIT child PID 43984, each acknowledged at its boundary and then forcibly terminated with exit code 1. The tests assert the child is alive before `Process.destroyForcibly()`, require process death within 10 seconds, and reject normal exit. `git diff --check` on the owned paths produced no diagnostics.

Preserved initial green: `output/r3-java-process-green.txt`, `output/r3-java-process-green.xml`, `output/r3-java-completion-regression-green.xml`.

Negative control commands used only `--tests dev.caseflow.documents.CompletionProcessRecoveryTest` with the same wrapper, directory, rerun, and console flags:

1. Before the first green, the probe intentionally called `status.setRollbackOnly()` after applying the completion. The before-commit child was still killed; the after-commit child reached its marker without a durable commit. The after-commit business assertion failed: expected `SUCCEEDED`, observed `QUEUED`. Preserved `output/r3-java-process-red-missing-commit.txt` and `.xml`. The rollback control was then removed.
2. Temporarily replaced the single `child.destroyForcibly()` call in `forceKillOwnedChild()` with a `RELEASE` message to child stdin and flush. Both children exited normally after completing the transaction, and both tests failed with `Normal exit is not crash evidence`, exit 0. Preserved `output/r3-java-process-red-normal-exit.txt` and `.xml`. The real forced termination call was then restored. Cleanup's kill logic was never replaced.

No negative-control mutation remains in the final sources. The `RELEASE` IPC branch remains in the helper so the normal-exit control is reproducible.

## Invariants exercised

- Before commit: real child transaction has applied success, audit and APPLIED inbox changes; an independent observer still sees QUEUED/no audit/no inbox. Force termination leaves those observer states unchanged. Replaying success, the identical event, and a new success event leaves one success audit, one APPLIED inbox receipt, one STALE receipt and successful job/document status.
- After commit: forced termination preserves successful job/document status, one success audit and one APPLIED inbox receipt. Identical-event replay, a new success duplicate and a late failure leave success terminal, with exactly one audit total, zero failure audits, one APPLIED receipt and two STALE receipts.
- Child asserts its SQL role is `caseflow_api` and verifies the real handler has made transactional changes before emitting the boundary handshake. It executes production `Commands.audit`; no handler or SQL behavior is mocked.
- Disposable name guard is exactly `caseflow_test_[a-f0-9]{32}`. It is checked before database creation, before target JDBC URLs are constructed/used in parent and child, and before cleanup. Host/port are fixed at loopback `127.0.0.1:54320`. Provisioning/drop use the `postgres` maintenance database, not writes to the running demo database. Migrations/fixture seed use `caseflow_migrator`; actual completion/replay use `caseflow_api`.
- Each test owns one newly spawned process and uses that `Process` object for termination, never a discovered PID or another running service. Handshake timeout 20 seconds, child self deadline 45 seconds, termination 10 seconds, output-thread join 2 seconds, SQL socket timeout 10 seconds/connect timeout 5 seconds; JUnit test deadline 90 seconds. Cleanup always attempts owned argument-file removal and guarded database drop, including failure paths.

## Limits and parent integration

This proves actual child JVM termination with real PostgreSQL and real completion transaction code. It does not start or terminate the full Spring API server, consume Kafka, observe offset commits, or test a deployment restart. Replay is executed by the separate parent test JVM through the same real handler and fresh JDBC connections. Worker success/artifact metadata are synthetic seeded SQL rows; the Java test neither renders nor uploads a DOCX. Scheduling, worker result selection, S3 orphan/reclaim behavior, publisher/offset windows, broad restart/load evidence and release completion require their separate evidence.

The root task should preserve the selected raw artifacts under the R3 evidence directory, add this scope to teaching/interview/evidence documents, and serialize the commit after its own review. This subtask has not committed or pushed changes.

Needed from you: nothing right now.
