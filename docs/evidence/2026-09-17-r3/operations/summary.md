# Operational reporting and document cleanup

Recorded September 17, 2026. Baseline `1e607d4`; reporting source `e917228`,
cleanup source `d0996f0`. This is local synthetic evidence, not an R3 release
completion or production deployment. No model calls, AI ledger changes, paid
resources or demo-object deletion occurred.

## Verified results

| Check | Observed result |
| --- | --- |
| Read-only report integration/CLI | 15 passed in 1.62s |
| Cleanup integration/CLI/process exits | 33 passed in 11.75s |
| Full worker regression | 152 passed in 65.79s; no failures/errors/skips |
| Full Java regression, Kafka process tests enabled | 29 passed; no failures/errors/skips; Gradle build 44s |
| Local Flyway upgrade | 12 migrations validated, V11/V12 applied from version 10 |
| Local report | Exit 2, two APPROVED_MISSING_REQUEST findings, no truncation |
| API/preview smoke after migration | `/api/v1/health` UP, preview HTTP 200 |

JUnit, console output, migration output and metadata-only investigation are
archived alongside this file. Cleanup's [detailed report](cleanup/README.md)
preserves initial failures, conditional-delete observations and test limitations.
The [manifest](manifest.json) hashes source at the recorded commit and archived
artifacts. Test counts include controls and earlier tests, not distinct crash
scenarios. Java emits existing Kafka deprecated-API warnings; the build passes.

## Decisions and verification

Reporting uses a restricted metadata view plus worker-owned tables in a
read-only transaction. Six findings distinguish delayed publication, overdue
queue entries, expired leases and missing approved-document requests/current
worker attempts. Output is bounded and explicitly reports truncation. CLI
failure messages omit raw driver errors. Parameters and role boundaries have
tests; the report does not automatically repair records or read business content.

Independent AI-assisted review found that an old failed worker attempt could
hide a missing new attempt. The retained `reconciliation-retry-red.xml` fails
the missing-retry assertion before the fix. The final implementation compares
attempt numbers and uses the current request update timestamp for its grace.
Initial missing-module evidence is separate from this behavioral regression.

Cleanup defaults to preview, requires an explicit tenant/job, and only considers
old canonical objects under a consistent successful document job. Selected,
referenced, fresh, changed, malformed or ineligible objects are retained. Apply
rechecks durable state and object identity. A job row lock plus narrow artifact
SHARE lock prevents selection races while unrelated heartbeats remain available.
The earlier broad jobs-table lock failed the heartbeat regression and was replaced.

Real local storage rejects an incorrect conditional-delete ETag with HTTP 412
and retains the bytes. The journal fsyncs intent before deletion; exceptions or
lost acknowledgements preserve pending/unknown outcomes. Two actual child exits
occur after intent/before delete and after delete/before result recording. The
selected artifact survives both, while the orphan's presence matches each
boundary. These are two cleanup-journal boundaries, separate from the thirteen
previous document/messaging transaction crash scenarios.

The root independently ran the entire 152-test worker suite after implementation.
Read-only AI-assisted review found no further actionable cleanup issue; it was
static review, not an additional independent test run or human sign-off.

## Live diagnosis: legacy approvals

The real local report found cases `926f812c-68a5-40a8-a39c-0d5b5059d1ad` and
`dd9ea9f0-9a3c-4eb9-82b7-eec798ae6de1`. Both are approved with document status
QUEUED and no core job requests. Their original document.requested outbox events
were published. Read-only investigation retained only IDs, states, timestamps,
audit event types and publication metadata.

They were approved at 2026-09-15 01:09:16Z and 01:19:41Z. Migration V3 and durable
document-request creation landed in `4e484a6` at 01:33:44Z. Inspection of the
earlier `91dd4a6` approval implementation confirms it created a generation ID
and outbox event without a core job request. That history supports diagnosing
these as legacy records from the initial implementation, not a new report bug.
Current approval calls `DocumentJobs.request` inside the transaction.

These findings remain visible. There is no fabricated immutable template/input
snapshot, silent suppression, automatic repair or claim that the report is
clean. The [runbook](../../../operations-runbook.md) explains investigation and
the authorized application retry path for actual failed jobs. Legacy records
without job requests require a separate explicit migration/recreation policy.

The one-off local upgrade used the API's locked Flyway runtime via the archived
`migrate-operations.gradle`, keeping the running API available. It performs only
normal versioned migration, with Flyway clean disabled and credentials inherited
from the ignored environment. The first smoke request accidentally used
`/api/health`, which correctly returned 401; the actual `/api/v1/health` check
then returned UP. No security configuration was changed.

## Reproduce

```powershell
. ./scripts/dev-env.ps1
$env:PYTHONPATH = (Join-Path (Get-Location) 'services/worker')
services/worker/.venv/Scripts/python.exe -m pytest services/worker/tests -q
$env:CASEFLOW_KAFKA_PROCESS_TESTS = '1'
./services/case-api/gradlew.bat -p services/case-api test --rerun-tasks --console plain
services/worker/.venv/Scripts/python.exe services/worker/tools/reconcile.py --age-seconds 300 --limit 100
```

Normal API startup applies pending migrations. The archived one-off runner can
also be invoked using Gradle `-I` with its repository path and task
`migrateLocalOperations` after sourcing the local environment. It targets only
the local development database. Repeating it after this upgrade applies zero
new migrations. Use a new output directory for new evidence.

## Limits and provenance

Python 3.12.10, Java 21, Windows and the existing Docker Desktop PostgreSQL 18.6,
Kafka 4.2.1 and SeaweedFS 4.47 services. Tests own disposable databases and object
prefixes; the live investigation is read-only. Object-age tests use an explicit
25-hour clock advance, not a 24-hour soak. The CLI offers no clock override.
SQL/S3 concurrency checks are real; the lost-delete-acknowledgement test uses a
wrapper that deletes through the real store and then raises a controlled timeout.

Artifact selection pauses globally during each candidate delete; socket and SQL
timeouts limit waits but are not wall-clock SLAs. Cleanup is manual and bounded,
does not enumerate bucket versions, and relies on immutable normal writer keys.
No AWS permission/versioning behavior, full monitoring, sustained throughput or
universal reconciliation coverage is established. See the [R3 map](../../../r3-status.md).

Archived text is normalized to UTF-8/LF with trailing whitespace removed and
JUnit hostnames normalized to local-test-host. Test outcomes, timestamps and
IDs are retained. Files are checked against ignored local credential values
before staging; the manifest excludes itself to avoid a circular hash.
