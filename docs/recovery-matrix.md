# Recovery evidence map

For an approved purchase, the required outcome is one selected immutable document
and one visible completion audit, even when messages or execution repeat. This
map follows section 10 of `plan.md`. Each row states the evidence tier; passing
one row does not prove all dependency failures or production readiness.

| Boundary / failure | Observed evidence | Remaining scope |
| --- | --- | --- |
| Before/after worker scheduling commit | Actual Python child termination; rollback or durable job/inbox, replay once | Whole-deployment termination under sustained arrivals |
| Before/after worker request offset commit | Actual Python messaging-loop child termination with real Kafka and PostgreSQL; replay before commit, resume after commit | Broker outage/rebalance during active multi-worker load |
| Lease expiry and stale ownership | Real five-second expiry after killed worker; higher fence selects replacement, old finalization rejected | Long dependency outages and exhausted retries |
| After object upload, before result selection | Actual local S3 DOCX exists unselected; replacement has different immutable key; both byte hashes checked; timeout after durable upload also verified | Production orphan collection and broader storage outages |
| Before/after worker result commit | Actual Python child termination; atomic artifact/status/outbox, one result after recovery | Dependency restart during that transaction |
| Worker completion publish before/after outbox mark commit | Actual Python child termination after real broker acknowledgement; same event republished at distinct offset only when mark did not commit; pending publish recovers after real isolated broker restart | Sustained load, multi-broker failures and wider timing combinations |
| Java request publish after broker acknowledgement | Actual JVM termination; restarted publisher emits same event ID at a new broker offset and persists published mark | Broker restart during publish |
| Before/after Java completion transaction commit | Actual JVM termination; status/audit/inbox atomic, stale failure cannot undo success | Dependency restart during completion |
| Java completion before Kafka offset commit | Actual JVM termination after SQL commit; restarted consumer receives same broker coordinate, retains one audit and commits offset | Whole-service recovery and broader event ordering |
| Duplicate messages and delayed failure | 10,000 broker duplicates for one completed job plus one stale late failure; both consumer groups caught up | Distinct active jobs and sustained workload measurements |
| Contention, future events and poison payloads | Real PostgreSQL lock contention and deterministic exception/transport-double tests | Process interruption in dead-letter publish/offset window, broader ordering cases |
| Broker/database restarts and object-store timeout | [Two actual isolated server restarts plus two SDK socket-timeout cases](evidence/2026-09-17-r3/dependencies/summary.md); same worker recovers pending publish/interrupted scheduling, storage retry selects one DOCX | Java connection-pool/full-deployment recovery, longer outages and sustained workloads |
| Reconciliation and orphan collection | Planned | Detection/repair policy, grace periods, guarded cleanup and operational evidence |

Sources: [transaction contracts](evidence/2026-09-16-r3/recovery-contracts.md),
[first process/broker batch](evidence/2026-09-17-r3/summary.md), and
[real Kafka process boundaries](evidence/2026-09-17-r3/kafka-boundaries/summary.md).
There are thirteen distinct business-boundary process-crash scenarios across
those two process batches. Cleanup/negative-control cases and repeated runs are
not counted as additional business-boundary coverage.

These tests run local components and synthetic fixtures. The plan's cloud
smoke/rollback/teardown, tracing, query optimization and sustained load gates
remain separate. At-least-once delivery can repeat computation and model billing
even when database effects are idempotent.
