# Dependency-recovery batch

This batch tests failures of the worker's dependencies using synthetic local
fixtures. It is separate from the thirteen process-crash business boundaries
and the earlier 10,000-message duplicate experiment. It makes no model calls,
changes no AI budget and provisions no paid resources.

## Storage timeout results

Two actual SDK socket-timeout cases pass: template reading stalls, and an upload
reaches the real store but its acknowledgement is withheld. The existing worker
records a transient failure, waits for real backoff and selects one valid DOCX
on the second execution. The unconfirmed original upload remains unchanged and
unselected. The final focused run passed two tests in 9.10 seconds; the full
worker suite passed **104 tests in 54.72 seconds**, no failures/errors/skips.

[Storage details](storage.md) explain the real network failure, upstream-write
ordering, source code, negative control and limits. The test shortens SDK timeouts
and disables internal retry to exercise application recovery quickly. It does
not simulate an entire S3 outage or establish production recovery latency.

## Isolated restart design

`tests/resilience/compose.restart.yaml` creates a uniquely named disposable
Compose project with pinned Kafka and PostgreSQL images, loopback ports 19092
and 55432, and its own data volumes. The running `caseflow-local` project is not
stopped or reset. Every destructive command checks exact project labels and
resource names. Cleanup removes owned containers, volumes and network; there
is no global pruning or prefix-based deletion.

The Kafka scenario keeps a durable unpublished outbox row, stops the owned
broker, and observes a real `KafkaException` from the production publisher.
The same worker instance must recover after the same persisted container
restarts, publish the same event ID and mark that row only after acknowledgement.
The test independently reads the broker record and verifies the expected count.

The PostgreSQL scenario pauses production scheduling after its SQL changes but
before commit, then stops the owned server. It requires a real commit failure
and no offset advance. After restart, a separate connection observes rollback
before allowing the same consumer to retry. One durable job/inbox must result;
an additional delivery of the same event must not create another job/receipt.

Restart evidence checks the container ID, unchanged mount identities and changed
server start timestamp. Mounts are compared in canonical destination order,
because Docker may return the same mounts in a different list order.
The broker test interrupts a pending publish; the database test interrupts an
in-flight transaction. Neither starts a complete Java/browser deployment.

## Actual restart results

The independent final run, `parent-final`, passed **11 tests in 40.05 seconds**:
two actual restart scenarios plus nine harness/ownership checks, with zero
failures/errors/skips. The earlier final implementer run passed the same eleven
tests in 39.96 seconds. These are test-suite durations, not service recovery
SLAs. [Parent JUnit](restart/parent-final/junit.xml) and
[raw events](restart/parent-final/events.json) retain the observations:

- Kafka restarted the same container from start timestamp `12:32:04.486426977Z`
  to `12:32:27.381284042Z`. A real failed publish left the outbox unchanged.
  Recovery emitted event `c4d56865-7fab-4abd-9518-6607407f706c` once; one
  job, inbox receipt and published outbox row remained. The RUNNING job is a
  publisher fixture; no document rendering/completion is claimed for this case.
- PostgreSQL restarted the same container from `12:32:04.49747281Z` to
  `12:32:35.391286985Z`. The interrupted transaction left jobs/inbox/outbox empty
  and the consumer offset absent (`-1001`). The same consumer then handled
  offsets 0 and 1, committed next offset 2 and retained one queued job/receipt.
- The final event records removal of owned test resources. The normal local
  API and preview health checks also passed separately during this batch.

Both `negative-*` runs intentionally omitted stopping their selected dependency
and failed the required unavailable-operation assertion. The tests therefore
reject a run in which no real outage occurred. The default non-opt-in invocation
passes nine guard checks and skips the two restart scenarios; those skips are
not counted as recovery evidence.

## Test-harness failures retained

Failed setup and probe runs are retained instead of being counted as recovery:

- The initial Kafka health check used the externally advertised host port from
  inside the container. The internal listener is required there. The isolated
  health check was corrected after direct internal-listener verification.
- A temporary Python `AdminClient` was destroyed before its topic-creation
  future completed. Keeping the client alive fixes that harness lifetime error.
- Comparing Docker's raw mount list rejected unchanged mounts returned in a
  different order. Canonical comparison keeps the identity check without
  treating ordering as a resource change.

Read-only AI-assisted review covered resource ownership, secrets, real failure
boundaries and cleanup. Storage review reported no actionable issues. Restart
review prompted releasing test coordination gates before joining a worker on
failure. Event recording is serialized between test/worker threads; run directories
are exclusively reserved so failed evidence cannot be overwritten.

The Kafka image declares anonymous storage volumes as well as the intended data
volume. The final harness uses temporary memory mounts for its nondurable paths
and removes anonymous volumes only with their verified owned container. Four
earlier anonymous volumes were removed using exact recorded mount ownership and
checks that no other container used them; [cleanup commands](restart/anonymous-volume-cleanup.json)
are retained. The initial failed setup did not preserve their IDs, so two
anonymous volumes may remain; ownership could not be established and no broad
prune was attempted. This earlier cleanup limitation is separate from the
verified final runs' cleanup.

## Provenance and archive

Baseline `986154b`; storage source is `cf6555b`, restart source is `61449fd`.
Python 3.12.10, Windows, Docker Desktop Linux engine, Kafka 4.2.1,
PostgreSQL 18.6 and SeaweedFS 4.47; versions/digests and commands are in the
run manifests and pinned Compose files. The root [manifest](manifest.json)
hashes exact Git source bytes and every archived artifact, including the nested
run manifests. Original embedded worktree hashes are preserved and may differ
from Git bytes because of line endings.

Text is archived as UTF-8/LF with trailing whitespace removed; XML hostnames
are normalized to `local-test-host`, and `.log` files become `.txt`. No test
results, resource IDs, event coordinates or timestamps are changed. Failed setup,
negative-control and successful runs remain distinct. Credentials were checked
against the ignored local environment before staging; secrets are not evidence.

## Reproduce and limitations

```powershell
. ./scripts/dev-env.ps1
$env:PYTHONPATH = (Join-Path (Get-Location) 'services/worker')
services/worker/.venv/Scripts/python.exe -m pytest services/worker/tests/test_storage_timeout_recovery.py -q
$env:CASEFLOW_RESTART_TESTS = '1'
$env:CASEFLOW_RESTART_RUN_ID = 'run-' + [guid]::NewGuid().ToString('N')
services/worker/.venv/Scripts/python.exe -m pytest tests/resilience/test_restart_guards.py tests/resilience/test_dependency_restart.py -q
```

Keep the restart ports free and run only one suite at a time. Without the
explicit flag, restart cases are skipped and provide no recovery evidence.
The storage tests require the existing local PostgreSQL/S3 services; restart
tests create their own PostgreSQL/Kafka. Credentials are inherited from the
ignored environment, never passed as command arguments or printed.

These are local worker-component recovery observations, not multi-node failover,
production SLAs, Java database-pool reconnection, sustained throughput, cloud
smoke/rollback or production orphan collection. The full R3 acceptance gate
remains open in the [project map](../../../r3-status.md).
