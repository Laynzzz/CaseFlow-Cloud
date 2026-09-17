# Process interruption and broker redelivery declaration

Declared September 17, 2026 UTC before these runs. Baseline `e06f1f1` on
`codex/r2-evaluation`. This is the next bounded R3 batch, not the entire release.

## Process scenarios

Use actual separately spawned Python processes and JVMs, real application
transaction code and disposable PostgreSQL databases. Pause at an explicit
boundary over IPC, then terminate only the child owned by the test. Require
evidence that the boundary was reached and the process was forcibly terminated;
ordinary exceptions and a normally exited child do not satisfy this declaration.

- Worker scheduling: before database commit and after database commit.
- Worker result selection: before database commit and after database commit.
- Document upload: after real local S3 upload, before result selection. Allow
  the real lease to expire; reclaim with a higher fence, select a new immutable
  output and reject the old owner's finalization. Check both object hashes.
- Java completion: before commit and after commit, then replay without a second
  audit/business effect.

Fixtures are synthetic. Child database names must match the existing guarded
`caseflow_test_<32 hex>` convention. Only fixture-specific local object keys
may be cleaned up; this is test cleanup, not production orphan collection.
No running demo process, database or Docker service is terminated by this batch.

## Broker delivery experiment

Extend the existing `services/worker/tools/replay_document.py` probe. First run
10 request plus 10 completion duplicates as a smoke test. Then run exactly
5,000 request and 5,000 completion duplicates, plus one separately counted late
failure event. Use the existing already successful synthetic document fixture.

Require all 10,000 callbacks to acknowledge actual Kafka topic/partition/offsets,
and both existing consumer groups to commit beyond all sent records. Observing
only producer acknowledgements or the late failure receipt is insufficient.
Use offset inspection without group membership, subscription or offset writes.
Before/after state must retain one selected artifact, its identity/checksum,
one success audit, successful job/case-document states and no added failure audit.
Keep any failed run output and use a new path for a rerun.

This is duplicate-delivery evidence for one completed document job on one local
broker, not 10,000 distinct purchases or a sustained-throughput benchmark.
Process probes and this broker run are separate experiments; do not infer that
the process kills occurred during the 10,000-delivery run.

## Costs and limits

No model calls, AI budget changes, cloud resources or paid services are needed.
The full publisher/offset crash windows, broker/database restart under active
work, object-store timeouts, reconciliation/garbage collection, query optimization,
mixed load, tracing/alerts, cloud rollout/rollback and final portfolio gates
remain separate work until actual evidence is recorded.
