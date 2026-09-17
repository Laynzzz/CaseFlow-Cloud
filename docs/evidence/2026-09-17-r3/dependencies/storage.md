# Object-storage timeout recovery

Observed September 17, 2026 UTC on Windows with real local PostgreSQL and
S3-compatible SeaweedFS. Two new component integration cases passed in the
final focused run (9.10 seconds). Production Python behavior is unchanged.

## Failure boundaries

1. **Template read stalls.** A test-owned loopback HTTP endpoint accepts the
   actual SDK GET request but sends no response. Botocore raises a real
   `ReadTimeoutError`. The worker stores `RETRY_WAIT` with
   `DEPENDENCY_UNAVAILABLE`, clears its lease, emits one retry event and selects
   no artifact. After the actual database backoff expires, a higher-fenced
   execution reads the real template, renders and selects one DOCX.
2. **Upload succeeds but its acknowledgement is lost.** The test endpoint
   receives the actual SDK PUT body, verifies the fixture bucket/key and
   conditional-create header, and writes those bytes through the real local S3
   client. It then withholds the HTTP response. The test records that upstream
   acknowledgement preceded the SDK read timeout. One object exists but is
   unselected. After real backoff, the next execution selects a new immutable
   key. The first object's checksum remains unchanged, stale finalization is
   rejected, and a delayed failure cannot reverse success.

Both cases call production `Runtime.execute`, rendering, failure recording,
claiming and finalization. They require exactly the observed network timeout
class, one retry event, zero early artifacts/success events, and rejection of an
immediate retry before `available_at`. Recovery does not rewrite SQL clocks.
The second execution retains the logical attempt, increments execution count
to two, and obtains a higher fencing token. The selected object is downloaded,
its checksum verified, and DOCX content checked for the synthetic vendor,
USD 70.00 total and absence of unresolved placeholders.

## Harness and isolation

Python `storage_timeout_probe.py` uses the standard HTTP server on an ephemeral
loopback port. It is a controlled response-withholding endpoint, not an outage
or restart of the object-storage server. Template reads in the second case go
directly to the real store; only PUT acknowledgement is withheld. Production
settings remain unchanged. The test SDK uses a one-second read timeout and one
total attempt to reach the application retry boundary quickly; this does not
measure production timeout latency or its internal SDK retry schedule.

The existing disposable database/document fixture supplies random tenant/job
keys and a random template key. The helper rejects a nonlocal upstream endpoint
or nonfixture database before serving requests. It uses synthetic signing
credentials against its own endpoint; the actual upstream client uses ignored
local credentials. The handler suppresses access logs and records no request
signatures. Cleanup releases and joins the owned HTTP server and deletes only
the fixture's template/document objects. This is test cleanup, not production
orphan garbage collection.

## Sensitivity, evidence and reproduction

The initial missing-helper collection failure is retained as
`r3-storage-red.txt`; it is not behavioral failure evidence. After the first
passing run, a temporary test-only wrapper forced timeout failures to be marked
permanent. Both cases failed at `FAILED` versus expected `RETRY_WAIT`, proving
the transient-retry assertions reject that classification. The wrapper was
removed before final verification. Raw negative-control text/XML and initial
green text/XML are preserved alongside final focused reports. JUnit properties
record the selected/orphan hashes, fencing tokens, status, elapsed time and
acknowledgement-before-timeout assertion.

```powershell
. ./scripts/dev-env.ps1
$env:PYTHONPATH = (Join-Path (Get-Location) 'services/worker')
services/worker/.venv/Scripts/python.exe -m pytest services/worker/tests/test_storage_timeout_recovery.py -q --junitxml=output/storage-timeouts.xml
```

These are synthetic component tests, not full browser approval journeys,
concurrent distributed writes, load results, production S3 guarantees or cloud
validation. They use no model calls or paid resources. Independent AI-assisted
review and full regression results are recorded in the batch summary.
