# ADR 0001: Begin with a small connection through the planned stack

Date: 2026-09-11. Status: accepted for the Phase 0 foundation milestone.

## Context

The user is learning while building the purchase approval product in `plan.md`.
Before adding business behavior, verify that a React page can call Java and that
Java can read a database initialized by versioned SQL. This is a milestone within
Phase 0, not a declaration that the full phase or R1 is complete.

## Decision

Preserve the plan's React/TypeScript, Java 21/Spring Boot, PostgreSQL, Flyway,
and Gradle choices. Run Java and Vite on the host for immediate source feedback;
run PostgreSQL in Docker Compose, bound to loopback. Add the other planned
services as the corresponding Phase 0 contracts are introduced.

Use one public GET `/api/v1/health` endpoint with no business data. It reads a
schema marker with the restricted API role. Unknown/missing schema or database
failure returns 503 with a generic problem response. All other HTTP routes are
denied by Spring Security until Phase 1 adds OIDC and resource authorization.

Flyway connects separately as `caseflow_migrator`. That role owns DDL in `core`
and `worker`. The API can select only the current metadata table; the worker
has no table privileges yet. Later migrations must grant explicitly scoped
privileges. This establishes role boundaries, not tenant isolation: no tenant
or purchase tables exist yet. Runtime migration credentials currently coexist
in the local Java process; a dedicated release migration step will remove that
requirement for cloud deployment.

Generate TypeScript API types from an authored OpenAPI document and use
`openapi-fetch` as the typed transport. Types do not validate server output at
runtime; the smoke check and status checks cover this small contract. Add Zod
validation and richer contract tests with business request schemas.

Pin direct frontend packages and commit npm's dependency lock. Pin Gradle with
the wrapper and distribution checksum; record Java dependency resolution in
Gradle's lockfile. Pin the database image by version and manifest digest.

## Alternatives and consequences

- An in-memory database would be easier to run but would not exercise PostgreSQL
  permissions and SQL behavior. Keep PostgreSQL for integration verification.
- Manually creating database tables would avoid Flyway initially, but would make
  reproducible setup and migration history harder. Keep SQL in `db/migrations`.
- Dockerizing every component immediately would offer a single start command,
  at the cost of more setup before the first lesson. Host development does not
  replace the planned container builds and cloud delivery.
- A hand-maintained frontend response interface is smaller but can drift from
  the API contract. Generate it instead.
- The page is explicitly a development preview. It does not accept purchases
  or simulate working approvals or AI.

## Verification

See `docs/evidence-index.md` for actual results and limitations. No performance,
tenant isolation, or production-readiness claims follow from this milestone.
