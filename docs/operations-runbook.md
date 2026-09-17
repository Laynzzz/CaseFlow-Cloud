# Local worker operations

These tools run on a trusted operator host with worker database/storage
credentials. They are not tenant-facing APIs. Reports expose identifiers and
operational metadata, not purchase, quote, policy or model contents. Protect
report files as internal operational records. Run the latest API migrations
through the normal Flyway startup before using the tools (V11 for reporting,
V12 for cleanup). Never paste credentials into command arguments or reports.

## Detect delayed work

From the repository root, with the local dependencies running:

```powershell
. ./scripts/dev-env.ps1
$env:PYTHONPATH = (Join-Path (Get-Location) 'services/worker')
services/worker/.venv/Scripts/python.exe services/worker/tools/reconcile.py --age-seconds 300 --limit 100
```

The command uses a read-only database transaction. Exit 0 means no findings
under these thresholds, 2 means findings, and 1 means the report failed. Invalid
CLI syntax also exits 2, with an argparse error rather than a JSON report.
`truncated: true` means additional findings were omitted; it is not a total
count. The maximum is 1,000 findings. Thresholds range from 60 seconds to 30
days; expired leases are reported immediately. Future scheduled retries are
not overdue. The report spans tenants because it is a platform operation.

| Finding | Meaning | Investigation |
| --- | --- | --- |
| EXPIRED_LEASE | A running job lost its lease | Check worker availability and repeated dependency failures; a healthy dispatcher should reclaim it with a higher fence. |
| OVERDUE_JOB | A queued/retry job is past its due time plus grace | Check worker health, capacity and dependency access; distinguish due work from intentional backoff. |
| API_OUTBOX_PENDING | A Java event remains unpublished past grace | Check publisher/broker health. A broker acknowledgement may have been lost; keep the original event ID. |
| WORKER_OUTBOX_PENDING | A worker event remains unpublished past grace | Check the worker publisher and broker, then rerun the report. |
| APPROVED_MISSING_REQUEST | An approved case has no matching document request | Preserve evidence and investigate the approval transaction/invariant. Do not fabricate input or repair with direct SQL. |
| APPROVED_MISSING_WORKER_JOB | The current document attempt has no matching worker attempt | Check request publication, consumer progress and dead letters; an older failed attempt does not satisfy this check. |

Use IDs to correlate existing logs and durable state. Restore failed dependencies
first and observe normal replay/reclaim. For a terminal failed job, use the
existing authorized, audited application retry action after addressing its
cause. This report does not republish, change status, repair records, detect
every completion mismatch, or replace monitoring. A missing attempt is aged
from the current request's updated timestamp so a fresh retry gets its grace.

## Preview abandoned document objects

Supply the exact tenant and successful document job from an investigation:

```powershell
services/worker/.venv/Scripts/python.exe services/worker/tools/cleanup_documents.py --tenant <tenant-uuid> --job <job-uuid> --grace-hours 24 --limit 100
```

Replace the angle-bracket placeholders with canonical lowercase UUIDs. Preview
is the default. It lists only that job's generated-document prefix, at most the
specified number of objects. `truncated` means the scan is incomplete; increase
the bound up to 1,000 if appropriate. There is no bucket-wide sweep or scheduler.
Templates, evidence sources and AI artifacts are outside this policy.

Only a SUCCEEDED document job with a consistent selected artifact is eligible.
Selected or otherwise referenced objects, malformed keys and fresh objects are
retained. Missing, active, failed or inconsistent jobs are ineligible. This
intentionally keeps some garbage rather than guessing that abandoned work is
safe. The minimum age is 24 hours, based on storage LastModified timestamps.

After inspecting a preview, an operator may explicitly apply it using a **new**
JSONL journal path; the CLI takes a fresh preview rather than trusting an edited
saved report:

```powershell
services/worker/.venv/Scripts/python.exe services/worker/tools/cleanup_documents.py --tenant <tenant-uuid> --job <job-uuid> --grace-hours 24 --limit 100 --apply --report output/cleanup-new-run.jsonl
```

Each candidate is rechecked against PostgreSQL and storage. A job row lock
prevents state changes, and a narrowly granted SQL function locks artifact
references while deletion is in flight. This temporarily blocks artifact
selection across jobs; unrelated lease heartbeats remain available. Storage
calls use short timeouts and one SDK attempt to limit blocking. Cleanup should
be run sparingly, not treated as a high-throughput background job.

The journal is exclusively created and flushed before each external deletion.
A durable DELETE_INTENT without a durable DELETE_RESULT, a truncated last line,
or an UNKNOWN result means the outcome is uncertain. Stop and inspect storage
plus current job/artifact state. Preserve the journal; never overwrite or
blindly resume it. PostgreSQL, S3 and a local file cannot commit atomically.
An acknowledged deletion describes that request, not an atomic cross-system
transaction. An interrupted run has no successful final record.

## Verification scope

Integration tests use disposable databases and owned synthetic objects. Cleanup
age tests use an explicit controlled clock; they do not claim a 24-hour soak.
Concurrency tests exercise real SQL locks and unrelated heartbeat progress.
Reports and cleanup are local operational capabilities, not proof of cloud
permissions, bucket versioning behavior, monitoring coverage or production
readiness. See the [R3 map](r3-status.md) for remaining release gates.
