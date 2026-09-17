# Claims supported by this project

CaseFlow is a synthetic portfolio/learning application for purchase approvals,
with an experimental AI review assistant. These are engineering measurements,
not claims of customer adoption, production traffic, time savings or compliance.

| Claim | Actual evidence | Boundary |
| --- | --- | --- |
| Built a working purchase-to-DOCX application | [Browser journey and clean checkout](evidence/2026-09-17-r3/demo/summary.md) | Local synthetic identities, two ordered approvals; cloud pending |
| Enforced role/tenant and stale-write boundaries | [Evidence index](evidence-index.md), [query correctness](query-performance.md) | Tested invariants, not a universal security guarantee |
| Preserved one selected output under duplicates/crashes | [Recovery matrix](recovery-matrix.md), [broker replay](evidence/2026-09-17-r3/summary.md), [dead-letter faults](evidence/2026-09-17-r3/deadletters/summary.md) | Seventeen business-boundary crash scenarios; no claim of exactly-once transport |
| Recovered from actual dependency outages and rolled back images | [Monitoring/recovery](evidence/2026-09-17-r3/monitoring-recovery/summary.md) | Local PostgreSQL/Kafka outages, compatible additive schema; no data-loss/disaster-recovery claim |
| Improved one measured SQL access pattern | [Query comparison](query-performance.md) | ACTIVE large-tenant buffer accesses 1,281 to 29; common-state trade-off and 7.41 MiB index cost; no write-throughput claim |
| Measured a bounded mixed workload | [Raw load analysis](../tests/load/results/2026-09-17T15-04-19-100Z/analysis.md) | 180 measured seconds at two arrivals/s; HTTP p95 10.458 ms and polling-inclusive completion p95 3.835 s; no maximum/cloud capacity claim |
| Added correlated tracing, metrics and diagnostic alerts | [Telemetry](evidence/2026-09-17-r3/telemetry/summary.md), [monitoring](evidence/2026-09-17-r3/monitoring-recovery/summary.md) | Sampling/export can lose traces; bounded metadata; generic Java framework span names |
| Implemented repeatable test, coverage and scan gates | [CI evidence](evidence/2026-09-17-r3/ci/summary.md) | Local commands verified; hosted workflow unexecuted; worker has expiring reviewed OS findings |
| Evaluated a grounded AI assistant honestly | [R2 acceptance](evidence/2026-09-16-r2/r2-acceptance.md) | 164/240 extraction fields = 68.33%, below 90%; AI grading is not independent human validation |
| Prepared AWS infrastructure and cost controls | [Rehearsal source/runbook](../infrastructure/terraform/rehearsal/README.md), [proposal](aws-deployment-proposal.md) | Offline validation only; do not say deployed to AWS until actual deploy/smoke/rollback/teardown evidence exists |

The shared lifetime AI test ledger records USD 0.633975 against the user's USD 10
ceiling at the R2 handoff. R3 reliability/demo checks made no provider calls.
AWS has separate prerequisites and costs; the AI allowance does not authorize it.

For interviews, start with the employee's purchase and the two human approvals,
then explain the durable handoff to document generation. Choose a failure case
and one measured result, including their limits. Use [interview preparation](interview-prep.md)
and [architecture teaching notes](teaching-guide.md), without claiming unperformed
cloud work or independent AI review.
