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
| Recovery transactions | [13 actual business-boundary process-crash scenarios](recovery-matrix.md), including real Kafka publish/offset gaps, upload/result selection and Java completion; earlier deterministic checks retained | Dependency restarts, dead-letter crash windows, full-service recovery and operational reconciliation |
| Broker redelivery | [10,000 injected duplicates plus one late failure](evidence/2026-09-17-r3/summary.md); both consumers caught up, one artifact and success audit, no added execution | This bounded duplicate gate passes; distinct active jobs and sustained arrivals remain separate load work |
| Dependency recovery | [Actual isolated broker/database restarts and two storage timeout cases](evidence/2026-09-17-r3/dependencies/summary.md); same worker recovers durable state | Java connection-pool/full-deployment recovery, longer outages and sustained workloads |
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

## Second recovery batch: actual process interruption and broker replay

The [September 17 evidence](evidence/2026-09-17-r3/summary.md) records five
Python child-process and two JVM terminations around real production transaction
code. One Python case uploads actual DOCX bytes before termination, waits for
real lease expiry, and verifies a higher-fenced replacement plus the unchanged
orphan. These are test children invoking production components, not termination
of the full running services. Garbage collection remains unimplemented.

A separate run delivered 5,000 request and 5,000 completion duplicates for one
already successful synthetic job, plus one late failure. All broker coordinates
were acknowledged and both existing consumer groups committed beyond them.
Baseline and final business state matched. This was not concurrent with the
process-kill experiment and is not a throughput benchmark. Full suites passed
95 Python and 22 Java tests. No AI provider calls or cloud resources were used.

## Third recovery batch: Kafka acknowledgements

[Six more business-boundary process-crash scenarios](evidence/2026-09-17-r3/kafka-boundaries/summary.md)
exercise the actual worker/Java messaging loops with real local Kafka and SQL.
Pending outbox records replay with the same event ID at a new broker offset;
durably handled messages replay without another job or audit when offset commit
was interrupted. Each test owns temporary topics/groups and a disposable
database. The running demo's groups and topics are unchanged. A cleanup
regression also covers Kafka retaining a killed member until session expiry.
Full regression suites passed 102 Python and 29 Java tests without failures/skips.

These are component subprocesses, not full deployment or broker/database
restarts. See the [boundary-by-boundary matrix](recovery-matrix.md) for coverage
and remaining work. No model calls, AI ledger changes or paid resources.

## Fourth recovery batch: dependencies

[Dependency evidence](evidence/2026-09-17-r3/dependencies/summary.md) adds real
Kafka/PostgreSQL stops and restarts on disposable services, plus socket timeouts
before template reading and after a successful object write. The same worker
recovers pending publication/interrupted scheduling; storage retry selects one
valid document and leaves the unconfirmed upload unselected. Full worker tests:
104 passed. The independent opt-in resilience suite: 11 passed, including two
restart scenarios and nine harness guards. Failed setup and negative controls
remain published, including the earlier anonymous-volume cleanup limitation.

These results do not implement reconciliation, production orphan collection,
monitoring, query optimization, sustained load or cloud release. Those remain
the next major workstreams; the detailed matrix still identifies narrower
dead-letter and Java/full-service recovery gaps.

## Limits carried from R2

Extraction remains experimental: 164/240 fields (68.33%) in the new 60-case
held-out set, below the 90% goal. Review quality is AI-graded synthetic evidence,
not independent human validation. No human time savings or real adoption have
been measured. The shared USD 10 lifetime AI ledger accounts for USD 0.633975 at
the R2 handoff; this recovery batch makes no provider calls.

Cloud work has separate prerequisites and costs. The AI testing budget is not
authorization for paid AWS resources. Local recovery and performance work can
continue while cloud prerequisites remain unconfigured.
