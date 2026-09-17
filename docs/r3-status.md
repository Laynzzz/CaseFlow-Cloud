# R3 reliability and portfolio status

R3 is in progress. R2's [local experimental acceptance](evidence/2026-09-16-r2/r2-acceptance.md)
is recorded; R1 cloud delivery remains incomplete. This map tracks observed
evidence, not an estimated percentage or a production-readiness claim.

## Product outcome

After finance approves a purchase, temporary failures should not lose the
document request, create two selected documents, or let an old failure replace
a completed document. Operators should be able to explain and recover stuck
work. Performance and cloud claims need reproducible measurements.

| Workstream | Current evidence | Required next evidence |
| --- | --- | --- |
| Recovery transactions | [11 new recovery checks](evidence/2026-09-16-r3/recovery-contracts.md), including rollback/replay, acknowledgement ordering and observed Java row-lock contention; existing lease/fencing checks | Actual process-crash matrix, including object-upload/result-selection boundaries |
| Broker redelivery | [10 request and 10 completion redeliveries plus one late failure](evidence/2026-09-14-documents/replay.txt) preserved one artifact and one success audit | 10,000 injected broker redeliveries with recorded counts and one logical selected output |
| Dependency recovery | Local dependency startup/recovery recorded during R2 | Controlled broker/database restarts and object-store timeouts during active work |
| Query optimization | Tenant/permission predicates and cursor implementation | Skewed synthetic tenants, baseline query plans, one controlled change, identical-workload rerun and trade-offs |
| Sustained load | Functional journey and AI latency records | Workload/environment declaration, sustained mixed arrivals, errors/dropped work, backlog and saturation |
| Operations | Structured worker logs and health endpoints | Correlated exported traces, bounded-cardinality metrics, reconciliation, alerts and runbooks with diagnosed failure |
| Cloud release | Planned AWS architecture; no deployed evidence | Account/region/identity/cost prerequisites, Terraform, actual deploy/smoke/rollback/teardown |
| Portfolio | Local browser flow, synthetic AI evaluation and architecture/learning notes | Clean-checkout demo, final claim-to-evidence table and release limitations |

## First recovery batch

The [bounded implementation plan](superpowers/plans/2026-09-16-r3-recovery.md)
used real isolated PostgreSQL databases and controlled failures at transaction
and Kafka acknowledgement boundaries. The tests exercised the production worker
and completion handler with their application roles. Fixture setup uses the
migrator; the running demo database is not cleared.

Injected exceptions and fake Kafka acknowledgements do not prove recovery from
an actual killed process, restarted broker, lost network or cloud outage. These
evidence tiers stay separate even when they test the same invariant.

## Limits carried from R2

Extraction remains experimental: 164/240 fields (68.33%) in the new 60-case
held-out set, below the 90% goal. Review quality is AI-graded synthetic evidence,
not independent human validation. No human time savings or real adoption have
been measured. The shared USD 10 lifetime AI ledger accounts for USD 0.633975 at
the R2 handoff; this recovery batch makes no provider calls.

Cloud work has separate prerequisites and costs. The AI testing budget is not
authorization for paid AWS resources. Local recovery and performance work can
continue while cloud prerequisites remain unconfigured.
