# State-filtered purchase queue comparison

September 17, 2026. Baseline source `4f816a8`; implemented source `0748861`.
The only production change is V13's composite index on tenant, state and
descending cursor order. The Java query, permission checks and API stay the
same. This is a controlled local SQL comparison, not sustained load or an R3
release-completion claim. No AI calls or paid resources were used.

## Final results

The primary pooled run is `9ac7421a-1fd5-476d-a57f-ec43ef0a2f43`. It uses one
100,000-case tenant with 100 ACTIVE rows and one 200-case tenant with 20 ACTIVE
rows. The test alternates baseline/indexed/baseline/indexed with three warmups
and fifteen samples for each of seven workloads per stage. Dataset, query,
binds and permission roles remain fixed; only the index changes.

| Workload | Representative buffer accesses, before → after | Server median ms, pair 1 | Server median ms, pair 2 |
| --- | --- | --- | --- |
| Large ACTIVE, administrator | 1,281 → 29 | 2.262 → 0.045 | 2.161 → 0.029 |
| Large ACTIVE, deep cursor | 3,886 → 29 | 6.430 → 0.062 | 13.204 → 0.028 |
| Large, unfiltered | 5 → 5 | 0.022 → 0.022 | 0.017 → 0.021 |
| Large, common CANCELLED state | 5 → 6 | 0.023 → 0.028 | 0.021 → 0.028 |
| Small ACTIVE | 13 → 11 | 0.040 → 0.023 | 0.035 → 0.038 |
| Large ACTIVE, owner | 1,281 → 29 | 7.229 → 0.050 | 6.926 → 0.035 |
| Large ACTIVE, assigned | 406 → 109 | 0.430 → 0.260 | 0.345 → 0.219 |

The main selective administrator query uses **44.17 times fewer buffer
accesses** in both pairs. Identical result hashes across all stages verify
unchanged returned rows, assignments and cursor. Unfiltered reads gain little;
the common-state query adds one buffer access. The small tenant's tiny timing
differences should not be generalized.

Server values come from separate EXPLAIN ANALYZE executions, including its
instrumentation. Full Java list-method median time for the administrator
ACTIVE workload was 6.551 → 2.285 ms, then 4.409 → 1.495 ms. That includes three
queries using the test pool. It excludes HTTP/authentication/browser work and
is not directly comparable to an individual EXPLAIN or its cached prepared plan.
All raw samples and plans are retained rather than only favorable medians.

V13 uses **7,766,016 bytes (7.41 MiB)** on this fixture. Total case-index bytes
increase from 17,440,768 to 25,206,784, about 44.5%. Primary index builds took
79.8 and 91.6 ms. Inserts and state transitions must maintain this index;
write-throughput cost is **not measured**. Ordinary CREATE INDEX blocks table
writes while building; these local timings do not predict cloud lock duration.

## Verification and deployment

- Five API-role database tests pass: permissions and tenant boundaries, exact
  assignment isolation with duplicate case IDs across tenants, state/pending
  filters, equal-time cursors under new inserts, fixed query count, membership
  revocation and invalid cursor rejection.
- The comparison passes. A second pooled run,
  `3f995fcf-5dfe-4081-a7cb-d845e5d0bd50`, also passes in the final Java suite.
- Full Java regression: **35 passed, zero failures/errors/skips**, including
  Kafka process tests and the benchmark; build 47 seconds. Existing Kafka
  deprecated-API warnings remain.
- Full worker regression: **152 passed in 72.64 seconds**, no failures/skips,
  including fresh-schema migration through V13.
- Flyway validated 13 migrations and applied V13 to local schema version 12.
  The API returned UP and browser preview HTTP 200 afterward.
- A read-only database check confirms all six recorded benchmark databases
  were removed. No demo rows were seeded or removed.

Read-only AI-assisted review prompted stronger foreign-assignment checks and
per-run source fingerprints. Review confirmed the comparison and trade-offs;
it is not independent human validation. The root ran both final suites.

## Retained failures and harness changes

The first two comparison runs have `candidatePresent: false` and intentionally
fail the buffer-reduction assertion. Stages named indexed in these negative
controls do **not** contain the candidate; those names describe the comparison
slot. They prove the gate rejects an unchanged schema. The first exploratory
harness ran rolled-back write probes between stages, creating dead tuples that
could contaminate reads. Those probes were removed before the second negative
control and all successful comparisons. Initial source/output remain historical;
none of those write timings is a claimed result.

The first successful comparison and an intermediate full run used a new
DriverManager connection for every query. Concurrent full Java/worker runs
then each failed one test with Windows socket bind/allocation errors:
`Address already in use`/`BindException`. An observation found about 2,800
TIME_WAIT connections to the local database. That supports connection churn
as a contributing condition; it does not establish an exact OS exhaustion
threshold or a database outage.

The query fixture now uses HikariCP with minimum one idle connection and maximum
two. The final dedicated comparison and serial full suites pass. Unpooled
timings remain separate and are not combined with the pooled table above.
No global Windows networking settings or production configuration changed.
Failure logs redact credential-bearing DSN fields, including truncated fragments.

## Reproduction, environment and limits

See [query-performance.md](../../../query-performance.md) for commands,
measurement contract, alternative indexes and deployment considerations.
PostgreSQL 18.6 runs in the existing local Docker service; Java 21.0.12.1 runs
on Windows 11. Manifests include PostgreSQL planner settings, host CPU visibility,
pool configuration, SQL/binds, source hashes, index size and build time.
The environment record includes the container image/digest and limits.

There are 420 measured list calls per comparison, plus 84 warmups and separate
EXPLAIN executions, at concurrency one. No cache flush or sustained arrivals
are used. Background development services remain running. All ACTIVE cases
belong to the same owner and approver, so sparse ownership/assignment performance
is unmeasured. Correctness for foreign assignments is tested separately.
No representative production distribution, cold-cache result, HTTP throughput,
write capacity, saturation or cloud rollback is claimed.

The [manifest](manifest.json) hashes exact Git source bytes and normalized
artifacts. Per-run fingerprints retain original worktree bytes, which may differ
from Git bytes due to line endings. Text is UTF-8/LF with trailing whitespace
removed; JUnit hostnames are normalized and credential fields redacted. Raw
sample values, outcomes and observed identifiers are unchanged. Earlier negative
runs lacked per-run source fingerprints; their provenance is limited to the
retained exploratory source, commands and documented iteration sequence.
