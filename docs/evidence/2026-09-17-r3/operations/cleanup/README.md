# R3 document cleanup evidence — synthetic local integration

Recorded 2026-09-17T13:08:11Z on Windows with Python 3.12.10 and local Docker
Linux services. Base revision: `1e607d49e25553cb595edccaf1a8a330982e274f` plus
the cleanup and concurrent reconciliation working-tree changes. PostgreSQL image
ID: `1c59e2c3c818`; SeaweedFS image ID: `f83509b0721d`. These identify the local
test environment, not an AWS deployment.

Implemented in `services/worker/caseflow_worker/cleanup.py`, with the trusted-host
CLI `services/worker/tools/cleanup_documents.py` and migration
`db/migrations/V12__document_cleanup_lock.sql`. Tests are in
`services/worker/tests/test_document_cleanup.py`; actual process termination is
in `services/worker/tests/cleanup_process_probe.py`.

## Observed result

`final.txt` and `final.xml`: **33 passed in 11.75 seconds**, including real
PostgreSQL transactions and real objects in the local S3-compatible store.
Each database and tenant/job prefix is randomly generated and disposable. No
demo objects were passed to apply. No model calls or paid resources were used.

Object grace tests explicitly advance the cleanup clock by 25 hours while objects
are freshly uploaded. This proves cutoff logic; it is **not a 24-hour soak**.
The CLI has no clock override. Production defaults require at least 24 hours.

Actual child processes exit with code 73 at two boundaries: after fsynced intent
before delete, and after delete before its result record. Both journals retain
only START and DELETE_INTENT. The first orphan remains; the second is absent;
the selected artifact remains in both. These are pending/unknown outcomes, never
successful completion. JUnit properties preserve the boundary observations.

`conditional-delete.txt` records a real wrong-ETag conditional DELETE receiving
HTTP 412 and preserving bytes. The final suite repeats this check. Apply uses
IfMatch after checking the current HEAD ETag, length and modification timestamp.

## Reproduce

From the repository root in PowerShell:

```powershell
. ./scripts/dev-env.ps1
$env:PYTHONPATH = 'services/worker'
& services/worker/.venv/Scripts/python.exe -m pytest services/worker/tests/test_document_cleanup.py -q --junitxml=output/r3-cleanup/final.xml
```

This requires the existing local PostgreSQL and object-store services. The test
fixtures create and migrate isolated databases using migrator/admin credentials;
the cleanup implementation itself uses only the restricted worker connection.

Preview a specifically identified job (replace UUID placeholders):

```powershell
. ./scripts/dev-env.ps1
& services/worker/.venv/Scripts/python.exe services/worker/tools/cleanup_documents.py --tenant <tenant-uuid> --job <job-uuid>
```

Explicit apply adds `--apply --report <new-jsonl-path>`. The directory must exist;
an existing path is refused. No apply was run against the demo. Reports are
append-only: persist intent before delete, observed result afterward. A pending
intent or incomplete last JSON line requires inspection; never assume rollback
restored storage, and never overwrite the journal.

## Architecture and limits

- The module lists only `tenants/<canonical-tenant>/documents/<canonical-job>/`,
  at most the requested 1–1000 objects, with explicit truncation. It never lists
  the bucket or deletes templates, sources or AI output.
- Eligibility requires a SUCCEEDED DOCUMENT job and selected artifact with
  matching attempt/fence and exact canonical key grammar. Every apply candidate
  rechecks job state and all artifact references, plus current object identity
  and grace cutoff. Missing, failed, running, queued, malformed, selected,
  referenced, fresh and changed objects are protected.
- Apply first locks its job row, then obtains a SHARE lock on worker.artifacts
  via a fixed-search-path SECURITY DEFINER function. The function only takes a
  lock; PUBLIC execution is revoked and only worker execution is granted. No
  core table access or artifact UPDATE/DELETE grant is added. The lock lasts
  only until the caller transaction exits.
- Artifact selection is briefly blocked globally while one candidate is checked
  and deleted. Unrelated heartbeats remain available; the real concurrency test
  proves this while concurrent artifact insertion and same-job mutation time out.
  Dedicated storage calls use 2-second connect and 3-second read timeouts with
  one total attempt. These are socket timeouts, not a guaranteed wall-clock SLA.
  SQL lock acquisition retains the existing 3-second lock timeout.
- PostgreSQL and S3 have no shared atomic commit. Delete acknowledgement means
  the S3 delete was acknowledged; versioned buckets may retain older versions.
  This tool does not enumerate or purge versions. Timeout/acknowledgement loss
  records UNKNOWN and stops the remaining batch. Report-write failure stops
  immediately, leaving any durable earlier intent pending.
- Keys rely on the renderer's immutable IfNoneMatch upload contract. Privileged
  storage writers replacing identical bytes under the same key can preserve an
  ETag; IfMatch is not a universal transaction across database and storage.
- Truncation means the prefix was only partially inspected. A completed apply
  covers only its preview candidates; it is not a bucket health declaration.
  Cleanup remains manual, job scoped and unscheduled.

## Retained failures and iterations

- `red.txt`: initial missing cleanup implementation assertion.
- `first.txt`/`first.xml`: 24 passed, one fixture cleanup ordering failure
  (outbox FK prevented deleting the missing-job fixture). Fixed the test setup.
- `lock-red.txt`: regression checks rejected the initial broad jobs-table lock
  because it blocked unrelated heartbeats and lacked the narrow lock function.
- `second.txt`/`second.xml`: 27 passed after the narrow lock implementation.
- `third.txt`/`third.xml`: 32 passed with actual process-exit and object rechecks.
- `final.txt`/`final.xml`: 33 passed after real conditional DELETE and direct CLI
  invocation checks; the initial module-existence scaffold test was removed.

No AWS cleanup, long-running operational soak or release-completion claim is
established by these local tests.
