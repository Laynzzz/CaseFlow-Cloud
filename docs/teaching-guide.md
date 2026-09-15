# CaseFlow: architecture and decision guide

This guide is maintained during implementation for teaching the project afterward.
Start with the product and system structure; only inspect code to explain an
important design choice. Implementation status is tracked in README and the
evidence index. Planned behavior is not proof of working behavior.

## Product and scope

A requester submits a purchase with a vendor quote. Assigned people review it in
order. Final approval queues an immutable Word document. AI will suggest quote
fields and cited policy findings; people accept suggestions and make decisions.
The product manages authorization to buy, not payments, ordering, or delivery.

## Component map

| Component | Language and framework | Runs in | Responsibility |
| --- | --- | --- | --- |
| `apps/web` | TypeScript, React, Vite | Browser; Vite is a local development server/build tool | Screens and user interactions |
| `services/case-api` | Java 21, Spring Boot, Spring Security, Spring Data JDBC | Backend server | Business rules, permissions, transactional state changes |
| `db/migrations` | SQL, Flyway | Applied to PostgreSQL by the migration account | Ordered schema changes and explicit privileges |
| `services/worker` (planned) | Python 3.12 | Background service | Documents, ingestion, AI, durable job execution |
| Kafka (planned) | Message broker | Infrastructure | Carries work and completion events |
| Object storage (planned) | S3-compatible service | Infrastructure | Immutable uploaded/generated files |
| Keycloak/OIDC (planned) | Identity provider and standard protocol | Separate identity service | Sign-in; the API still owns organization membership permissions |

## Implemented foundation

React calls `/api/v1/health`. Vite proxies it to Java during development. Java
reads a schema marker using the restricted API account and returns ready or 503.
The page renders checking, ready, and unavailable states with timeout and retry.
No purchase data, tenant access, or AI behavior is established by this check.

### Decisions and trade-offs

- **Java owns decisions; the browser requests them.** A caller can bypass a UI,
  so hiding buttons cannot provide authorization. Business routes are currently
  denied until server-side identity and membership checks are implemented.
- **Migrations rather than manual SQL setup.** Ordered files and checksums make
  setup repeatable and preserve history. Applied files should be followed by new
  migrations, not edited. This adds migration discipline but avoids schema drift.
- **Separate runtime and migration roles.** The API reads its marker without DDL
  access. The local process still receives migration credentials; cloud rollout
  must move migration execution to a dedicated step. Role separation is not
  protection against every process compromise.
- **Generated API types.** OpenAPI describes the response; TypeScript definitions
  reduce interface drift. Compile-time types do not validate untrusted runtime
  data. Tests and runtime checks are still necessary.
- **Pinned dependencies.** Wrapper/checksum, npm lock, Java lock, and image digest
  make dependency selection repeatable. Updates require deliberate compatibility
  checks. TypeScript 6 initially conflicted with the generator; 5.9.3 resolved it.
- **Host development plus a container database.** This gives fast frontend/Java
  iteration while exercising real PostgreSQL. It needs multiple processes today;
  containerized delivery remains planned.

### Evidence and limits

The 2026-09-11 foundation evidence covers three Java tests, frontend build,
first/repeated migration, real database grants, API/proxy smoke, and recovery
from a controlled database outage. See `evidence-index.md` for raw artifacts.
These results do not establish production readiness or tenant isolation.

## Planned architectural choices to revisit after implementation

- Separate approval state from document execution so rendering failure cannot
  undo a completed human decision.
- Commit state, audit, idempotency response, and outbox together; handle duplicate
  message delivery instead of assuming exactly-once transport.
- Use tenant-inclusive relationships and resource checks before SQL reads,
  downloads, retrieval, or model calls.
- Pin workflow/template/policy versions for reproducible historical review.
- Require explicit acceptance of revision-matched AI suggestions.
- Measure AI grounding and abstention on held-out synthetic examples, not only
  schema validity; synthetic results do not prove real-world usefulness.

## Teaching sequence after the build

1. Product journey and boundaries.
2. Component map and an ordinary request from browser to database.
3. Identity versus business permissions and tenant isolation.
4. Transactions, conflicting edits, and repeat submissions.
5. Approval-to-document flow and recovery from crashes.
6. Quote/policy ingestion, AI evidence, acceptance, and evaluation.
7. Deployment, observability, performance, cost, and rollback.
8. Interview walkthroughs grounded in actual tests and measured outcomes.

Extend each section as implementation lands with decision, alternative, trade-off,
failure example, implementation links, and verification evidence.
