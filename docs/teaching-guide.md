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
| Keycloak/OIDC | Identity provider and standard protocol | Separate identity service | Sign-in; the API still owns organization membership permissions |

## Historical foundation (September 11)

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

## Purchase workflow checkpoint (September 14)

The browser now supports a $4,200 synthetic laptop request, two assigned reviews,
and a recorded final approval. Real Keycloak sign-in supplies identity; Java
checks current organization membership in PostgreSQL for every business request.
The former health demonstration page has been replaced with product screens.
This checkpoint still cannot generate or download a document.

### Architecture and important decisions

- **Identity is separate from authorization (plan choice).** Keycloak proves
  who signed in with code + PKCE. Java uses issuer/subject to identify the person
  and current SQL memberships to decide what they can do. Realm roles do not
  grant purchase permissions. This allows immediate membership revocation on
  subsequent API requests, at the cost of database reads. Signed URLs, when
  introduced, will require a separate expiry discussion.
- **One Java business service (plan choice).** Controllers handle request shapes;
  shared access and command components enforce recurring rules. PostgreSQL
  transactions span the case, audit, response receipt and outbox. Microservices
  would add distributed coordination without helping this initial workflow.
- **Multiple tenant checks (plan choice).** Every query scopes by organization;
  composite foreign keys reject cross-tenant relationships as well. Neither
  unguessable IDs nor hidden buttons are security boundaries. App audit grants
  permit append/read, but privileged DB administrators can still alter records.
- **Version check plus row lock (implementation choice).** A request supplies
  the version it read; Java locks the case, compares that version and writes
  atomically. A concurrent losing reviewer receives 409. The frontend retains
  the editor's original version even when cached data refreshes, so an old form
  cannot silently overwrite a newer record. Users must reconcile conflicts.
- **Idempotency receipts (plan choice).** Commands bind a scoped key to a
  canonical hash and seven-day stored response. PostgreSQL advisory transaction
  locks return a retryable conflict for an in-flight matching key; the receipt
  primary key is the durable uniqueness boundary. Replays still recheck access.
  The draft form retains its key when retrying unchanged content within that
  mounted editor. Reloading the page does not preserve that key.
- **Money stays decimal (plan choice).** The browser sends decimal strings.
  Java BigDecimal validates currency minor units, rounds each computed line
  HALF_UP, sums the lines and stores the computed total. No binary floating
  point total from the browser is trusted. The current implementation does not
  model tax, exchange conversion or accounting settlement.
- **Immutable published routing (plan choice).** A workflow has exactly two
  named steps. Publishing freezes it; starting a case copies that snapshot and
  freezes purchase inputs. Templates and policies still need equivalent pinning
  in their phases. Correcting a terminal case creates a linked new draft.
- **Approval and rendering are separate (plan choice).** Final approval commits
  APPROVED and a stable generation ID plus an outbox event together. QUEUED
  means there is a durable request, not that a worker has produced a document.
  Kafka delivery, leases, artifacts and completion are the next implementation.
- **Frontend state boundaries (implementation choice).** React renders screens;
  TanStack Query caches server data under tenant/resource keys; React Hook Form
  holds unsaved input. Changing tenant or case remounts local editors. Sign-out
  clears cached data. Server authorization remains necessary on every request.

### Evidence and reading map

Seven Java unit tests cover readiness and monetary validation. The executable
`tests/e2e/purchase-api.mjs` uses real PKCE, PostgreSQL and Keycloak to exercise
isolation, stale edits, duplicate commands, ordered approvals, concurrent final
approval, access revocation and pagination under inserts. Results are in
`evidence/2026-09-14-purchases/api-tests.txt`. These are targeted tests, not proof
of complete security, full coverage, crash recovery or production readiness.

Read `services/case-api/src/main/java/dev/caseflow/common/Commands.java` for the
transaction boundary and `db/migrations/V2__purchase_domain.sql` for constraints.
For frontend structure start with `apps/web/src/AppShell.tsx` (TypeScript/React),
then the pages directory. The goal is to explain the boundaries and decisions;
there is no need to memorize individual functions.

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
