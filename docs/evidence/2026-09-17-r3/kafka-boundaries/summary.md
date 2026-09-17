# Real Kafka process-boundary results

This R3 batch adds **six business-boundary process-crash scenarios**: four
Python and two Java, against actual local Kafka and PostgreSQL. Together with
the preceding seven process scenarios, the project has thirteen distinct
business-boundary proofs. Repeated runs, cleanup kills and detector controls
are not additional business scenarios. R3 remains in progress.

## Product outcome and scope

If finance approves a purchase and a process stops in the gap between Kafka
and PostgreSQL, the pending work must survive without duplicate business
effects. These probes confirm the specified local component boundaries:

| Component / forced-kill boundary | Observed restart |
| --- | --- |
| Worker after scheduling commit, before request offset commit | Same broker coordinate redelivered; one durable job/inbox, then offset advances |
| Worker after request offset commit | Next broker event consumed; one logical job, separate receipt for the new event |
| Worker after broker acknowledgement, before outbox mark commit | Same event ID appears at two distinct broker offsets; one published outbox row |
| Worker after outbox mark commit | No additional broker record on restart |
| Java after request publication acknowledged, before outbox mark commit | Same event ID at offsets 0 and 1; restart persists published marker |
| Java after completion SQL commit, before Kafka offset commit | Same broker coordinate replayed; one success audit/inbox, then committed offset 1 |

Every crash test observes a live owned child at the intended boundary, forcibly
terminates it and requires nonzero exit. Recovery starts a fresh process. The
worker loops and Java messaging component are actual production code, using
real database roles and broker clients. Tests redirect identities to random
single-partition test topics/groups and migrated disposable databases. The
running demo's topics, groups and data are untouched.

Java gained a small internal constructor accepting producer/consumer interfaces
and topic names, while its public Spring constructor preserves production
defaults. This enables observation of real client boundaries without reimplementing
the loop. The Java child applies Spring transaction interception to the real
completion handler. No application state-machine or retry-policy changes were
made. Python production code is unchanged.

These are component subprocesses, not complete application deployments or
machines. The Java completion fixture contains synthetic worker result metadata;
the Python publisher fixture sends a RUNNING status event. This batch does not
render documents, restart dependencies, measure sustained load or prove
exactly-once delivery. The previous upload test supplies separate object-byte
evidence; the earlier 10,000-redelivery run is not rerun or pooled here.

## Verification and controls

The [worker report](worker.md) records seven focused tests and the full
**102-test worker suite**, passing in 46.54 seconds with zero failures/skips.
The **29-test full Java suite** passed with zero failures/errors/skips; Gradle
reported 34 seconds. The [Java report](java/README.md) records the focused
suites, controls and cleanup regression. Full Java results are in `java/TEST-*.xml` and
`java/java-full.txt`; totals are mechanically checked in [manifest.json](manifest.json).
Compiler deprecation/unchecked warnings and the existing JVM class-sharing
warning remain visible in the raw output; they did not fail the tests.

Python's normal-exit and early-offset mutations failed the intended assertions
and were restored before final runs. Java retains normal-release controls,
early-offset and omitted-completion-persistence detector checks. Temporarily
removing the production publisher's database update caused the durability
assertion to fail; the source was restored. Failed runs remain in this archive.

Independent AI-assisted reviews covered both implementations. Python review
reported no actionable issues. Java review found that a killed consumer could
remain a group member until its session expired, causing immediate cleanup to
fail and skip topic deletion. A regression reproduced `GroupNotEmptyException`.
The fix retries that condition for a bounded period and attempts topic cleanup
independently. The dedicated regression checks the owned group and topics are
absent after cleanup. This is test-infrastructure hardening, not a change to
production consumer recovery.

## Reproduce

Use the repository's existing local setup with Kafka/PostgreSQL running; the
full worker suite also requires object storage. The Java Kafka process tests
are explicit opt-in; a skipped suite is not crash evidence.

```powershell
. ./scripts/dev-env.ps1
$env:PYTHONPATH = (Join-Path (Get-Location) 'services/worker')
$env:CASEFLOW_KAFKA_PROCESS_TESTS = '1'
New-Item -ItemType Directory -Force output | Out-Null
services/worker/.venv/Scripts/python.exe -m pytest services/worker/tests/test_kafka_process_recovery.py -q --junitxml=output/worker-kafka.xml
services/worker/.venv/Scripts/python.exe -m pytest services/worker/tests -q --junitxml=output/worker-full.xml
./services/case-api/gradlew.bat -p services/case-api test --rerun-tasks --console plain
```

The environment loader reads ignored credentials without printing them.
`--rerun-tasks` forces actual Java test execution. Verify zero failures, errors
and skips, and inspect boundary/PID/offset records in JUnit. Tests use shortened
six-second consumer membership timeouts to bound crash recovery; production
timeouts remain unchanged. Exact random identities and PIDs vary on each run.

## Provenance

Observed September 17, 2026 UTC, Windows 11; local Kafka 4.2.1/PostgreSQL 18.6,
Python 3.12.10 and Java 21/Gradle 9.7.1. Baseline `5f58535`; worker source is
`cfaa52b`, Java integration is `803f83a`. The integrated source revision and exact Git-byte source hashes are
in [manifest.json](manifest.json), alongside archived artifact hashes and full
suite totals. Earlier raw worktree hashes in the Java task record remain
unaltered and can differ because of CRLF line endings and removal of an extra
blank line at the Java test file's end before commit. That whitespace-only
normalization followed the full Java run; no executable code changed afterward.

Archive normalization: UTF-8/LF, XML hostnames replaced with `local-test-host`,
trailing whitespace removed (including embedded XML logs), `.log` files renamed `.txt` so
they are tracked. Java README log references follow the archive names; embedded
historical capture paths retain their original locations. Test results, broker
coordinates and timestamps are unchanged. The manifest excludes itself.

No model calls, AI budget changes, paid cloud resources or shared dependency
restarts were needed. See the [recovery matrix](../../../recovery-matrix.md) for
remaining crash/dependency coverage and [R3 map](../../../r3-status.md) for
performance, operations, cloud delivery and portfolio gates.
