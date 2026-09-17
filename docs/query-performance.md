# Purchase-list query performance

The purchase queue supports tenant permissions, state filtering, pending
assignments and descending `(created_at, id)` cursors. R3's first controlled
optimization adds `cases_state_queue(tenant_id, state, created_at DESC, id DESC)`.
The existing tenant/time index remains useful for lists without a state filter.
No API, permission predicate, cursor format or result mapping changed.

## Why this index

On the synthetic large tenant, ACTIVE cases are rare and spread through history.
The existing time-ordered index scans many cancelled cases to find one page of
active purchases. Equality on tenant and state followed by cursor order lets
PostgreSQL reach that subset directly. A state-only index would still need to
filter tenants and sort; an ACTIVE-only partial index would support fewer of the
existing state filters. The full composite index is a routine implementation
choice under the plan, not an architectural change.

The [recorded comparison](evidence/2026-09-17-r3/queries/summary.md) retains raw
plans, samples, result hashes, source provenance and failed controls. The index
adds storage and maintenance to inserts and state changes. Write throughput was
not measured. Unfiltered and common-state queries do not show a comparable gain.

## Reproduce safely

With the repository's local PostgreSQL running:

```powershell
. ./scripts/dev-env.ps1
$env:CASEFLOW_QUERY_BENCHMARK = '1'
./services/case-api/gradlew.bat -p services/case-api test --tests 'dev.caseflow.cases.CaseQuer*' --rerun-tasks --console plain
```

`CaseQueriesIntegrationTest` checks real API-role queries against a disposable
database. Its five checks cover tenant/role visibility, state/assignment filters,
cross-tenant assignment isolation, tied-timestamp cursors under newer inserts,
fixed query count and revoked membership. Nonempty lists execute three queries:
membership, cases and one batched assignment lookup. This counts the service
method's SQL, not JWT identity resolution or an entire HTTP request.

`CaseQueryPerformanceTest` is opt-in. Without the flag it is skipped, which is
not performance evidence. The test creates a fresh database, applies baseline
migrations through V12, seeds deterministic synthetic data, and runs
baseline/indexed/baseline/indexed. Only V13's index is created/dropped during
these read measurements. This happens inside the randomly named test database;
the demo schema, cases and queues are untouched. The fixture checks the exact
database name before dropping it, and records confirmed cleanup.

Every invocation reserves a new UUID directory under `output/r3-query`.
Failed runs retain observations too. Do not overwrite results when repeating.

## Measurement contract

- One tenant has 100,000 cases with 100 ACTIVE; another has 200 with 20 ACTIVE.
  All other cases are CANCELLED. Case IDs and timestamps are deterministic.
- Each active case has two pending assignments to the same synthetic approver.
  ACTIVE cases all belong to one owner. These exercise permission checks but
  do not measure sparse ownership/assignment selectivity; separate small tests
  verify denied access and foreign-only assignments.
- Seven reads cover large/small tenants, rare/common/no state filters, a deep
  cursor, owner permissions and assigned work. Page size is 25, with the usual
  extra row fetched to determine whether a next page exists.
- Each of four stages warms each workload three times, then takes fifteen
  samples. Concurrency is one. VACUUM ANALYZE runs before the stages. There is
  no cache flush, write probe or sustained arrival stream during measurement.
- Calls execute the real Java `CaseQueries.list` using the API database role.
  Captured SQL and bound values feed a separate `EXPLAIN (ANALYZE, BUFFERS,
  FORMAT JSON)` immediately after each call. Plan timings include EXPLAIN's
  instrumentation; they are not HTTP latency. Root buffer counts avoid summing
  inclusive child counts twice.
- Java client timing covers the service method using a small Hikari pool
  (one idle connection, maximum two), with PgJDBC defaults. It excludes HTTP
  authentication, browser rendering and network delivery to a user. EXPLAIN
  executes separately from the service query and is not proof of that query's
  cached custom/generic prepared plan. Keep client and EXPLAIN timings separate.
- Full result hashes must match for each workload across samples and all four
  stages. A structural gate requires at least five times fewer buffer accesses
  for the selective administrator query in both pairs. Millisecond timings are
  reported observations, not machine-independent CI thresholds.

These are local warm-cache observations on an intentionally skewed fixture.
Background development services remain running. They establish a narrow SQL
optimization, not a production speedup, sustained capacity or a cloud SLO.

## Migration and rollback considerations

V13 uses ordinary transactional CREATE INDEX through Flyway. That preserves the
existing migration model but holds a lock that can block writes during index
creation. The measured local build is small; do not assume that timing for a
  large production database. Schedule a maintenance window before deploying
  this ordinary index build to a populated shared system. A future large-table deployment would need a tested
concurrent-index migration strategy and lock/build monitoring.

The migration is additive, so older application code can use the expanded
schema. Keeping or later removing the extra index does not change results.
The benchmark's index drop is a disposable-database experiment, not evidence of
an application/cloud release rollback. Do not edit an already-applied migration.

Method references: PostgreSQL's [EXPLAIN guidance](https://www.postgresql.org/docs/18/using-explain.html)
and [multicolumn B-tree behavior](https://www.postgresql.org/docs/18/indexes-multicolumn.html).
