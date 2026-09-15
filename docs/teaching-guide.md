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
| `services/worker` | Python 3.12 | Background service | Durable document execution; ingestion and AI still planned |
| Kafka | Message broker | Infrastructure | Carries work and completion events |
| Object storage | SeaweedFS locally, S3 planned in AWS | Infrastructure | Immutable uploaded/generated files |
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

## Document generation checkpoint (later September 14 work)

The local product now produces and downloads an approved Word file. Java owns
template validation, published versions and permission checks. Final approval
creates an immutable rendering snapshot and a durable outbox event in the same
transaction. Kafka delivers IDs and hashes; Python reads the restricted input
view, renders with docxtpl, writes an immutable object and records its result.
The worker's completion outbox eventually lets Java update visible status and
append the system audit. Neither message delivery nor storage success alone
counts as completed business-state handling.

### Choices, alternatives and failure cases

- **Templates are deliberately restricted.** Administrators can use ten named
  placeholders, with no loops, attribute access or arbitrary expressions.
  Validate archive bounds, XML namespaces/attributes, external references and
  placeholder syntax. Rendering also uses a Jinja sandbox, StrictUndefined and
  XML escaping. This limits template flexibility and makes the supported surface
  easier to reason about; it is not a claim that parsing untrusted files is free
  from risk. Resource-limited worker containers remain to be added.
- **Copy validated bytes, not a mutable reference.** Upload through an
  authenticated API endpoint with a 10 MB bound, then finalize by checking the
  exact bytes and copying them to a random immutable key. Finalization currently
  holds a database lock during bounded storage I/O. That is simpler but can hold
  a connection for up to the storage timeout; a staged validator would reduce
  this cost. Failed transactions can leave unreferenced objects for later GC.
- **A lease is temporary ownership.** A worker claims a job with a 30-second
  lease, renews it every five seconds, and increases the fencing token each time
  ownership is assigned. Completion checks attempt, owner, token and lease.
  If a paused worker resumes after another took over, its file stays unselected.
  Each attempt/token gets a different object key, so stale uploads cannot replace
  the chosen file. Garbage collection of unselected files remains planned.
- **Scheduling receipt differs from completion.** Inbox receipt and queued job
  commit together before Kafka offset acknowledgement. Execution then happens
  outside a transaction. Failure before offset commit repeats the event; durable
  uniqueness avoids another logical job. A consumer retries the same failed
  database record instead of committing a later offset past it.
- **Bounded retries.** Automatic execution is limited to five claims with
  exponential delay and jitter. A tenant administrator can retry a failed job;
  its logical ID stays fixed and attempt increases. Successful jobs are terminal.
  This avoids unbounded retries but leaves exhausted jobs needing attention.
- **Separate schemas need explicit view access.** Worker may read immutable
  core inputs; Java may read a result view. Neither may write the other's tables.
  Integration exposed a missing schema USAGE grant despite SELECT on the view.
  V4 fixes it; the worker-role tests also verify access to base tables is denied.
- **Signed download links are short-lived bearer capabilities.** Permission is
  checked before issuance. Links remain usable for 60 seconds even if membership
  changes; an authenticated streaming proxy would enable checks on every fetch.
- **One local broker and storage node.** SeaweedFS supplies the tested local S3
  subset; AWS S3 is still the cloud target. Kafka has no local high availability.
  Process restart can wait for consumer-group reassignment before delivery
  resumes. These local tests do not establish AWS operation or scalability.

### Evidence and reading map

`tests/e2e/document-api.mjs` completes real approvals, waits for generation,
verifies denied outsider download, checks SHA-256/size and parses the downloaded
DOCX. Browser inspection also received a download event from the product button.
Seven worker tests use separate disposable PostgreSQL databases to verify
duplicate scheduling, competing claims, expired leases, stale fencing, retry
attempts, role boundaries and XML-safe rendering. The broker probe repeats ten
requests and ten completions and injects a delayed failure: one artifact and one
success audit remain. This is baseline evidence, not the full plan crash matrix.

Read `services/worker/caseflow_worker/jobs.py` (Python, durable scheduling and
fencing) and `services/case-api/src/main/java/dev/caseflow/documents/CompletionHandler.java`
(Java, visible result-state ownership). The component split matters more than
memorizing the individual SQL statements. See the document evidence directory.

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
# R2 checkpoint: evidence parsing and evaluation setup (2026-09-14)

User behavior being built: attach a vendor quote or an organization policy, then
see suggestions supported by that exact document. The first implemented piece is
the Python parser, not yet an AI result or a browser upload flow.

`services/worker/caseflow_worker/parsing.py` is Python: text extraction and
deterministic page chunks. pypdf reads embedded PDF text; OCR is a separate,
deferred capability. A child process enforces 512 MiB memory and 20 seconds wall
time. Windows uses a Job Object; Unix uses resource limits. If limits cannot be
installed, parsing fails instead of running unbounded. This does not constitute
a complete network/filesystem sandbox.

Checksums identify the immutable source bytes and extracted chunks. Citation
offsets identify exact characters in extracted page text, not PDF binary offsets.
Overlapping fixed-size chunks are reproducible but can split tables/sentences;
quality evaluation must determine whether a different strategy is worthwhile.

`evals/manifest.json` fixes the initial 60/60 synthetic family split and targets.
References are generated and await human verification. No AI quality score exists
yet. The user authorized R2 implementation while R1 deployment gates remain open.

Verification: `$env:PYTHONPATH='services/worker'; services/worker/.venv/Scripts/python.exe -m pytest services/worker/tests/test_parsing.py -q`
passes 13 cases covering actual PDF text, character offsets/hashes, encrypted or
empty PDFs, malformed/binary input and size/page limits. `-q` prints a concise
result. See ADR 0003 for decisions and limits.
# R2 checkpoint: upload to indexed evidence (2026-09-14)

Behavior now implemented: requesters attach PDF/TXT quotes to owned drafts;
administrators upload policies, inspect their extracted text, then publish or
deactivate them. File failures explain why indexing failed. Manual purchase data
does not change when a quote is attached.

Architecture: React `Sources.tsx` calls Java `SourceController.java`; Java copies
the temporary upload into an immutable object, records its hash and a job in the
same database transaction as an outbox event. Python checks the source hash,
parses in a limited child process, and atomically selects chunks with a completion
event. Java consumes the completion before marking the source indexed. Policy
jobs use policy aggregates and nullable case IDs; no fake purchase cases exist.

The worker still owns its tables. Java reads designated result/chunk views;
tenant and resource checks precede evidence reads. SQL composite foreign keys
and source/job ownership checks reject mismatched references. A quote finalization
locks the draft and checks its version; it increments the draft version so older
suggestions can later be detected as stale. Published source bytes cannot change.

Trade-offs: API-mediated uploads use Java bandwidth and bounded storage I/O inside
the command transaction. Failed/interrupted UI uploads currently need a fresh
upload; unfinished temporary uploads are retained pending garbage collection.
Lists are capped at 100 sources. Policy pinning, retrieval and AI are subsequent
work; source text preview is not an AI-generated interpretation.

Verification commands: `node tests/e2e/source-api.mjs`,
`node tests/e2e/document-api.mjs`, `node tests/e2e/purchase-api.mjs`,
`npm --prefix apps/web run build`, and the complete worker pytest suite.
The source suite checks real Keycloak/PostgreSQL/Kafka/storage integration,
publication gates, owner/tenant denials, stale draft versions, unchanged purchase
data and malformed-PDF failure. Existing approval-to-DOCX regression still passes.
Worker checks total 22 at this checkpoint. Browser upload interaction still needs
its own verification; a frontend build alone does not prove the browser journey.
# R2 checkpoint: pinned policies and scoped search (2026-09-15)

Purchase behavior: the requester explicitly refreshes the published policy
selection while the case is a draft. Starting selects policies if none were
selected yet. After starting, SQL prevents replacement or deletion of the pins.
Deactivated policies disappear from new selections and draft searches, but remain
readable/searchable through purchases that already started with them. A draft
containing a deactivated selection must refresh before starting.

Java `PolicyPins.java` handles the selection; `PolicyPinController.java` authorizes
the purchase before searching its pinned source chunks. PostgreSQL full-text
search matches normalized words and ranks up to five passages. It is a measured
baseline candidate, not semantic AI or evidence of retrieval quality. The later
embedding comparison must use the same frozen queries. No passage is returned
from an unpinned or unauthorized tenant merely because it matches the words.

Decision: store policy source IDs and publication versions rather than copying
policy text into every purchase. Immutable source bytes keep historical citations
reproducible. Shared policy locks serialize pinning with deactivation; the case
lock serializes refresh/start with purchase changes. Explicit refresh increments
the purchase revision and will invalidate older AI suggestions.

Verified: `node tests/e2e/source-api.mjs` now covers refresh, scoped retrieval,
denied cross-tenant search, no refresh after start, and historical reads/search
after deactivation. `test_policy_pins.py` verifies publication/immutability SQL
constraints in disposable databases. The complete worker suite has 23 passing
checks, and approval-to-DOCX regression and frontend build still pass.
# R2 checkpoint: AI validation and durable spending limits (2026-09-15)

The Python provider adapter now defines extraction proposals and policy review
briefs as strict data structures. It validates supplied chunk IDs, exact quoted
text and decimal arithmetic. It cannot invoke approval actions or arbitrary tools.
These modules are not yet wired to application AI job/acceptance screens.

Decision: reserve worst-case API cost in PostgreSQL before calling the provider.
A transaction lock serializes competing reservations; global and tenant-day
ceilings both start at zero. If a timeout hides token usage, keep the reservation
charged. Otherwise a retry could repeatedly incur costs while appearing free.
Disable SDK retries so retry/billing behavior stays explicit. Recheck permission
before sending and before returning a result. A call already sent cannot be
retracted when a permission changes.

Trade-offs: conservative reservation may stop testing earlier than actual billing
requires. Structured JSON and valid citations still cannot establish that a claim
is true or supported; human grading and held-out runs remain required. The initial
model is a pinned baseline, not a proven optimal choice. No live provider calls
have run. See `docs/ai-provider.md` for limits, checked sources and dated prices.

Verification: the full worker suite has 37 passing checks, including deterministic
transport fixtures. These test engineering behavior, not AI quality.
# R2 checkpoint: application AI jobs and human acceptance (2026-09-15)

Behavior now wired: a requester can choose an indexed quote and request field
suggestions; eligible case participants can request a policy brief. The UI shows
queued/failed/complete states and cited text. Suggestions show current versus
proposed values and require explicit field selection. Live jobs currently remain
disabled because the durable budget is zero; this is visible in the UI alongside
manual purchase entry and policy search.

Java owns AI job admission, access checks and acceptance. Python loads only the
requested quote or pinned policy passages, rechecks current access/revision,
reserves spend, calls the provider, validates output and selects a fenced result.
The standard completion event updates Java's job status. SQL eligibility views
avoid giving the worker general membership/case write access.

Acceptance locks the draft and verifies the purchase revision again. Java applies
only vendor, currency and/or line items selected by the requester, runs bean and
decimal validation, calculates the total, increments the revision and audits
before/suggested/accepted values. A changed draft, an already started case or a
revoked membership prevents acceptance. Quote currency must match accepted items.
Accepting one subset makes other proposals from the old revision stale.

Evidence: 40 worker checks pass; three new Java integration checks use fresh
disposable PostgreSQL databases and synthetic model-result fixtures. They verify
selected acceptance, idempotent replay, stale protection, unsupported fields,
membership revocation and disabled-budget admission. The real source API suite
and approval-to-DOCX regression pass. Model-result fixtures never enter the running
demo database and do not measure AI quality.

Remaining: live provider and positive assisted browser checks, embedding candidate
comparison, human annotation review and held-out report. The application remains
experimental. A development preview blanked because Vite cached an empty module
during formatting; an owned-server restart restored the current source module.
# R2 checkpoint: trustworthy evaluation denominators (2026-09-15)

The offline Python scorer now validates the frozen dataset and scores recorded
extraction/review jobs. Failed or absent jobs remain in accuracy denominators;
otherwise dropping a difficult timeout could make the assistant appear more
accurate. Missing reference values count as correct only when a successful result
explicitly proposes null. Decimal formatting differences do not change meaning.

Citation support remains ungraded until a person checks the generated claim
against the passage. The tool creates an inventory for that review and keeps the
release flag false. Provider usage on failed calls is not assumed free: successful
result cost is explicitly a subtotal pending spend-ledger reconciliation.

Verification: `python evals/scoring.py --validate-dataset` confirms 60 development
and 60 held-out cases with disjoint families and unchanged hashes. Five scorer
tests pass, covering failed/missing records, decimal normalization, retrieval
rank limits, duplicate IDs and missing cost/support evidence. No live quality
evaluation was run. The user's R2-to-R3 continuation instruction is recorded in
AGENTS.md and CLAUDE.md; R3 starts after R2's gates pass without another request.

## R2 checkpoint: live provider failure and the shared budget (2026-09-15)

The user authorized USD 10 total and configured the ignored local key. Two actual
extraction requests failed, with HTTP 429 recorded on the second after adding safe
diagnostics. No suggestion was accepted or model quality score produced. The
purchase remains editable manually. The evidence preserves these failures rather
than replacing them with mock successes.

The budget is a shared lifetime ceiling across tenants and test runs. An unknown
provider charge retains its worst-case reservation: USD 0.039322 across these two
attempts. This is conservative accounted cost, not confirmed billing. Releasing
unknown charges as zero would allow repeated failures to bypass the ceiling.
`ai_budget_status.py` reads totals and allowlisted failure codes without printing
keys, provider bodies, or headers. Five provider tests now pass, including the
safe error-code and unknown-cost regression.

## R2 checkpoint: collecting evaluation evidence (2026-09-15)

The Node evaluation runner uses the application's ordinary sign-in, upload,
asynchronous job and result endpoints. Each synthetic case gets its own tenant
so its policy corpus exactly matches the annotations, while every call still
uses the same global spending ledger. It stops the suite on provider failures
and saves partial records instead of quietly omitting difficult cases.

Two decisions prevent misleading results. Extraction receives quote evidence
without existing draft defaults, so the draft's USD selection cannot fill a
currency absent from a quote. Retrieval saves a ranked ID array separately from
the evidence object: PostgreSQL JSONB can reorder object keys, so iterating that
object would not recover the actual search ranking. The prompt input version is
now v2; the earlier failed attempts retain v1 history.

The runner's held-out guard requires a real human reference-review record with
matching dataset hashes and full reviewed counts. The schema guard is not itself
proof that someone did the review. Dry validation and automated tests pass; a
successful live run and quality results still await provider access and review.
