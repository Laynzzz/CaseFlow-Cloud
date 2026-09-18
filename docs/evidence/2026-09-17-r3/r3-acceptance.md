# R3 release acceptance

Decision date: September 17 local / September 18, 2026 UTC.
**R3 complete as a bounded learning/portfolio release.** The final cloud inventory
was verified at 01:41:56 UTC. Required release gates are linked below; missed AI
targets and remaining limits stay explicit.

CaseFlow's delivered product is a synthetic purchase request, two ordered human
approvals and an immutable downloadable Word document. The experimental AI
assistant proposes quote fields and a cited policy review; people check and
accept suggestions. It cannot approve purchases.

## Release decisions

| Release | Actual status | Evidence and boundary |
| --- | --- | --- |
| R1 — working product | Complete; local product and actual AWS workflow/teardown verified | [Local browser/clean checkout](demo/summary.md), [HTTPS browser and S3 document](cloud-deployment/summary.md). Cloud delivery was completed later than the original R1 sequence. |
| R2 — AI-assisted review | Functional/evaluation learning release complete; AI experimental | [Acceptance](../2026-09-16-r2/r2-acceptance.md). Extraction 164/240 fields (68.33%) misses 90%; synthetic AI grading is not independent human validation. |
| R3 — reliability and portfolio | Complete within the recorded evidence boundaries | Gate mapping below. No production-readiness, customer adoption or cloud capacity claim. |

## Plan gate mapping

| Required outcome | Observed evidence |
| --- | --- |
| Tenant/resource permissions, schema integrity and concurrency | [Evidence index](../../evidence-index.md), [query correctness and SQL comparison](../../query-performance.md), [declared critical coverage](ci/summary.md). Positive and negative integration checks use real SQL roles. |
| Idempotency, leases, fencing, completion and one selected output | [Recovery matrix](../../recovery-matrix.md): 17 actual business-boundary process-crash scenarios; [10,000 duplicates plus a late failure](summary.md); one selected artifact/audit and no extra execution in the duplicate run. |
| Explicit suggestion acceptance; scoped/versioned evidence; held-out metrics and manual fallback | [R2 decision and reports](../2026-09-16-r2/r2-acceptance.md), [actual assisted browser flow](../2026-09-16-r2/browser-journey/README.md). Rejected outputs count as failures; fresh split and prior baselines retained. |
| Bounded performance with workload, errors and queue health | [Mixed load](../../../tests/load/results/2026-09-17T15-04-19-100Z/analysis.md): 180 measured seconds at 2 arrivals/s, 420 total iterations/84 documents including warmup, zero errors/drops, drained queue. HTTP p95 10.458 ms; polling-inclusive document p95 3.835 s. Local measurements only. |
| Measured SQL improvement and trade-offs | [V13 comparison](../../query-performance.md): 100,000-case tenant ACTIVE query buffer accesses 1,281 to 29 with identical results. Common-state work slightly worsens; index adds 7.41 MiB; write throughput unmeasured. |
| Operations, alerts and dependency recovery | [Local monitoring and PostgreSQL/Kafka outages](monitoring-recovery/summary.md), [reconciliation and guarded cleanup](operations/summary.md). Same application processes recover; alerts resolve. Cloud monitoring separately verifies three private scrape targets and a 13-span Java/Python trace. |
| Build, test, coverage and scan gates | [Local CI execution](ci/summary.md): 60 Java tests pass plus one separately opt-in benchmark skip; 174 Python tests pass. Four declared critical modules exceed 80% branch coverage. Hosted GitHub execution is unverified. [Cloud image scans](cloud-deployment/summary.md) preserve the worker's reviewed exceptions. |
| Cloud deploy, migrations, health, smoke and rollback | [AWS session](cloud-deployment/summary.md): HTTPS/OIDC, actual RDS/S3, browser approvals, candidate and baseline-image rollout, full workflow after rollback and three preserved document checksums. All 14 migrations successful; readback over TLS 1.3. Cloud candidate changes configuration only; additive-schema rollback has separate local evidence. |
| Cloud teardown and retained-resource cost | [Final inventory](cloud-deployment/teardown-inventory.json): 82 Terraform resources removed, empty managed state, no workload compute/storage/snapshots. DNS/state, seven task definitions and seven pending-deletion secrets retained; [credit ledger](../../aws-credit-ledger.md) records costs and delayed credits. |
| Clean-checkout demo and honest self-test labels | [Clean checkout and browser](demo/summary.md), [demo instructions](../../demo-scenario.md), [nine synthetic workflow-comparison tasks](../2026-09-16-r2/workflow-comparison/README.md). Clean source packaging used existing isolated volumes; empty-schema deployment is separately proven. Zero human study participants. |
| Traceable portfolio claims and learning material | [Claim map](../../claim-to-evidence.md), [architecture](../../architecture.md), [teaching guide](../../teaching-guide.md), [interview preparation](../../interview-prep.md). Each claim retains its environment and limitations. |

## Remaining limitations

- AI extraction misses the declared target. Narrow synthetic retrieval/review
  results and AI grading do not establish real-world quality or human time savings.
  The lifetime AI ledger remains USD 0.633975 of USD 10; this cloud run used no AI.
- The worker scan has 44 HIGH package findings across eight unfixed CVEs, accepted
  only for exact versions until October 1, 2026. This is not zero vulnerabilities.
  Renewing deployment after expiry requires updated scans and adjudication.
- The cloud profile is temporary, Single-AZ and shares a host for Kafka, identity
  and monitoring. It is not highly available. Load and outage results are local.
- API startup still receives a dedicated migrator credential for Flyway; a
  standalone migration task is a future hardening option. Routine API/worker
  database access uses separate restricted roles.
- Hosted CI is prepared but unexecuted. Browser checks cover selected journeys,
  not every browser or a complete accessibility audit. Favicon 401 responses and
  in-memory organization selection remain recorded usability limits.
- An initial cloud authenticated request returned an empty 401 during service
  stabilization; subsequent unchanged authentication flows passed. Its cause is
  unproven. An initially empty trace search likewise does not prove export loss;
  direct trace lookup and attribute/parent checks passed.

The demonstrated outcomes justify a bounded learning/portfolio release. They do
not imply that every optional feature, future hardening item or quality target
is finished. No paid account upgrade, production users or adoption is claimed.
