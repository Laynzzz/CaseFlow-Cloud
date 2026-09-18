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
| Recovery transactions | [17 actual business-boundary process-crash scenarios](recovery-matrix.md), including redacted dead letters, broker acknowledgements, upload/result selection and Java completion | Broader disaster recovery is not claimed |
| Broker redelivery | [10,000 injected duplicates plus one late failure](evidence/2026-09-17-r3/summary.md); both consumers caught up, one artifact and success audit, no added execution | This bounded duplicate gate passes; distinct active jobs and sustained arrivals remain separate load work |
| Dependency recovery | [Packaged PostgreSQL/Kafka outages](evidence/2026-09-17-r3/monitoring-recovery/summary.md): same API/worker processes recover, alerts resolve, selected artifacts verified | Cloud failure behavior remains unverified |
| Query optimization | [Controlled V13 index comparison](query-performance.md): 100,000/200-case tenants, repeated before/after plans, identical results, permission/cursor/N+1 checks and storage cost | This bounded optimization passes; sparse permission distributions, write cost and representative workloads remain unmeasured |
| Sustained load | [Bounded mixed load](../tests/load/results/2026-09-17T15-04-19-100Z/analysis.md): 420 iterations, 84 documents, zero errors/drops and drained backlog | Maximum throughput and cloud capacity are not measured |
| Operations | [Exported traces](evidence/2026-09-17-r3/telemetry/summary.md), fixed-label metrics, [alerts and compatible-image rollback](evidence/2026-09-17-r3/monitoring-recovery/summary.md), [reconciliation/cleanup](operations-runbook.md) | Actual AWS rollout/rollback is pending |
| CI and scans | [Local gate evidence](evidence/2026-09-17-r3/ci/summary.md): critical coverage, 60 Java/174 Python passing tests, reviewed scans | Hosted CI has not run; 44 worker OS findings across 8 CVEs have exact-version reviews expiring October 1 |
| Cloud release | USD 10 credit allowance approved; owner access grant verified; [DNS zone, protected remote state and empty image registries created](evidence/2026-09-17-r3/cloud-foundation/summary.md) | Registrar nameserver delegation; image publication; actual deploy/smoke/rollback/teardown |
| Portfolio | [Browser and clean checkout](evidence/2026-09-17-r3/demo/summary.md), [claim-to-evidence map](claim-to-evidence.md), architecture and learning notes | Cloud claims remain excluded; known UI and AI limitations recorded |

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
of the full running services. That batch did not implement garbage collection;
the fifth batch below adds a limited manual cleanup policy.

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

That dependency batch did not implement operations or performance features.
The detailed matrix still identifies narrower dead-letter and Java/full-service
recovery gaps.

## Fifth batch: detecting delayed work and cleaning abandoned files

The [operations evidence](evidence/2026-09-17-r3/operations/summary.md) records six
read-only finding types and a manual, job-scoped cleanup tool. Cleanup requires
a consistent successful document result, a 24-hour minimum grace, strict keys,
state/reference locks and a durable deletion journal. Selected and referenced
files remain protected. Two actual cleanup-process exits preserve uncertain
outcomes; these supplement the thirteen prior business-process boundaries.

The full regression suites passed 152 Python and 29 Java tests with no failures
or skips. V11/V12 applied through Flyway to the local database. A real read-only
report found two approved cases from before document jobs were implemented;
their original outbox records exist, but their durable generation requests do
not. They remain recorded findings rather than silently repaired history.

The [runbook](operations-runbook.md) explains report codes, investigation and
explicit cleanup. No demo file was deleted. Controlled-clock cleanup tests do
not prove a 24-hour soak or AWS behavior. Monitoring, broader reconciliation,
sustained load, cloud release and portfolio evidence remain. The next batch
addresses the bounded query-optimization requirement.

## Sixth batch: measured purchase-list optimization

The [query evidence](evidence/2026-09-17-r3/queries/summary.md) records a single
additive tenant/state/cursor index. On the synthetic large tenant, the selective
ACTIVE query drops from 1,281 buffer accesses to 29 in repeated comparisons,
with identical results. The common-state query slightly increases work and
unfiltered queries gain little. Storage grows by 7.41 MiB on this fixture;
write throughput is not measured.

Five new correctness checks protect role/tenant visibility, assignment isolation,
pagination under inserts and batched loading. Full suites pass 35 Java and 152
Python tests. V13 is applied locally and API/preview smoke checks pass. An earlier
parallel run hit socket-allocation failures; the revised benchmark pools its
connections and final suites ran serially. Failed evidence is retained.

This completes the controlled SQL comparison, not sustained mixed load or the
remaining monitoring, recovery, cloud rollback and portfolio release gates.

## Limits carried from R2

Extraction remains experimental: 164/240 fields (68.33%) in the new 60-case
held-out set, below the 90% goal. Review quality is AI-graded synthetic evidence,
not independent human validation. No human time savings or real adoption have
been measured. The shared USD 10 lifetime AI ledger accounts for USD 0.633975 at
the R2 handoff; this recovery batch makes no provider calls.

Cloud work has separate prerequisites and costs. The AI testing budget is not
authorization for paid AWS resources. Local recovery and performance work can
continue while cloud prerequisites remain unconfigured.

## Packaged baseline (local only)

[Actual packaged baseline evidence](evidence/2026-09-17-r3/release-baseline/README.md)
records immutable images, fresh isolated volumes, sign-in/approvals/document
completion, cross-tenant denial and download checksum/content checks. A repeat
smoke preserves the previous approved case and selected artifact. Candidate
rollback, monitoring/load and real AWS gates remain pending.

## Correlated telemetry batch

[Telemetry evidence](evidence/2026-09-17-r3/telemetry/summary.md) records 42 Java and
169 Python passing tests plus a real two-service trace across API/outbox/Kafka/job/
completion. Separate private metrics endpoints expose HTTP, pool/transaction,
queue/execution/outbox/lease, Kafka lag and durable AI ledger signals. Monitoring
unavailability is explicit. Full trace sampling was used only for this bounded
rehearsal; load/alert/rollback and AWS gates remain separately verified.

## Poison-message process recovery

[Four actual dead-letter interruption scenarios](evidence/2026-09-17-r3/deadletters/summary.md)
pass across Python/Java before submission and after acknowledgement. Original
coordinates replay, next offsets commit only after acknowledgement, diagnosis
fields remain redacted, and invalid records create zero business effects. This
closes the narrower dead-letter process gap; full-service/cloud gates are separate.

## Sustained mixed-load gate (local)

[Measured run](../tests/load/results/2026-09-17T15-04-19-100Z/analysis.md):30seconds
warmup +180seconds at2 mixed arrivals/s;420 iterations,84/84 documents including72
measured-phase documents. Zero workload errors/dropped iterations, peak observed
pending2 and final0, two verified downloads, clean release-fixture reconciliation.
Measured HTTP p95=10.458ms; polling-inclusive completion p95=3.835s. The report
retains sampled resource/lag evidence and excludes maximum-capacity/cloud claims.

## Monitoring, whole-service recovery and local rollback

[Actual evidence](evidence/2026-09-17-r3/monitoring-recovery/summary.md) records
healthy scrape targets, a provisioned 22-panel dashboard and collector privacy
checks. Stopping PostgreSQL and Kafka separately triggered diagnostic alerts;
the same API/worker processes recovered after dependencies returned. Documents
completed with one audit and verified checksums. Prior application images ran
against additive V14 and preserved four existing documents; restoring the
candidate also passed. These are local gates. Hosted CI, clean-checkout demo,
security scans and actual AWS deployment/rollback remain separately tracked.
