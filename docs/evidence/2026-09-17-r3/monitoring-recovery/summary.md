# Local monitoring, dependency recovery and rollback

Actual Docker Desktop rehearsal on September 17, 2026. These results cover the
isolated `caseflow-release` project; no AWS deployment or availability claim follows.
Artifacts are indexed with original and normalized archive hashes in
[archive-manifest.json](archive-manifest.json).

## Monitoring

The pinned Collector, Prometheus, Tempo and Grafana configurations validate and
run. The captured target response shows all three scrape targets healthy; the
captured Grafana API response contains the provisioned 22-panel dashboard.
The integrated trace is also linked from the separate telemetry report.

The collector privacy probe sent three synthetic spans and exported two:
the secret sentinel and events were absent, fixed operation and parent IDs were
retained, dynamic names were normalized, and the unsupported linked span was
dropped. The initial OTTL runtime failure is preserved alongside the final proof;
configuration parsing alone did not catch that runtime error. See the
[operating runbook](../../../runbooks/observability.md) for current limitations,
including generic names for Java framework spans and sampling/export loss.

## Whole-service faults

Two dependency scenarios were run twice; repetitions are not additional crash
boundaries. The final runs explicitly compare application container IDs, start
times and restart counts before and after dependency recovery:

- PostgreSQL stopped: API health returned 503, the database-unavailable alert
  fired, PostgreSQL restarted, the same API/worker processes recovered and an
  approved request produced its verified DOCX.
- Kafka stopped: finance approval committed while the job remained queued, the
  Kafka-metrics-unavailable alert fired, Kafka restarted, and the same API/worker
  processes completed the existing logical job.

Both alerts resolved. Each resulting case retained one completion audit and a
download matching its selected artifact checksum. This tests reconnection after
a bounded dependency outage, not database corruption, broker data loss, regional
failure or high availability. The fault helper verifies exact Compose ownership
before stopping only PostgreSQL or Kafka and attempts restoration in `finally`.

## Prior-image rollback

The actual helper switched from `telemetry-candidate` to `release-baseline` while
keeping additive migrations through V14. The older images completed a new
approval/document smoke. A separate check verified all four existing fault-test
documents retained APPROVED/SUCCEEDED state, identical bytes/checksums and one
completion audit. Restoring `telemetry-candidate` passed a new smoke and repeated
preservation checks. Logs record exact image IDs; this is application-image
rollback with compatible schema, not reversal of migrations or database restore.

Ordinary trace sampling was restored to 10%. The later security candidate is a
different build and must pass its own tests/scans; these artifacts are not
relabeled as evidence for that image.

## Reproduce

From the repo root after the packaged release is deployed with observability:

```powershell
node --test tests/resilience/release-guards.test.mjs
node tests/resilience/release-recovery.mjs postgres
node tests/resilience/release-recovery.mjs kafka
node scripts/release.mjs rollback
node tests/resilience/verify-release-preservation.mjs rollback
node scripts/release.mjs deploy telemetry-candidate --observability
node tests/resilience/verify-release-preservation.mjs restored
```

Use existing owned release manifests or build uniquely named candidates first.
Rollback selects the prior manifest; confirm it is the intended compatible image.
Local generated credentials and tokens are excluded from the archive.
