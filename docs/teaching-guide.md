# CaseFlow: architecture and decision guide

This guide is maintained during implementation for teaching the project afterward.
Start with the product and system structure; only inspect code to explain an
important design choice. Implementation status is tracked in README and the
evidence index. Planned behavior is not proof of working behavior.

## Product and scope

A requester submits a purchase with a vendor quote. Assigned people review it in
order. Final approval queues an immutable Word document. AI suggests quote
fields and cited policy findings; people accept suggestions and make decisions.
Its quality remains experimental. Start with [the current architecture map](architecture.md)
for a short overview; the dated sections below retain the implementation history.
The product manages authorization to buy, not payments, ordering, or delivery.

## Component map

| Component | Language and framework | Runs in | Responsibility |
| --- | --- | --- | --- |
| `apps/web` | TypeScript, React, Vite | Browser; Vite is a local development server/build tool | Screens and user interactions |
| `services/case-api` | Java 21, Spring Boot, Spring Security, Spring Data JDBC | Backend server | Business rules, permissions, transactional state changes |
| `db/migrations` | SQL, Flyway | Applied to PostgreSQL by the migration account | Ordered schema changes and explicit privileges |
| `services/worker` | Python 3.12 | Background service | Durable document execution, ingestion and AI jobs |
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

## R2 checkpoint: live AI works, and development failures guide fixes (2026-09-15)

After the user resolved billing, the real model returned a total formatted as
`4200.00 USD`; the numeric validator correctly rejected it. A later development
response invented part of a citation ID. The output schema now requires decimal
amounts and separate currency codes and restricts citations to the supplied IDs.
Post-validation remains the final check. Neither fix relied on held-out data.

Private call evidence in migration V9 preserves rejected model output and its
hashes without making it a business result or exposing it through API views.
This matters because debugging only successful output hides the failure modes.
The exporter scopes an evidence file to explicitly recorded synthetic job IDs.

The real API journey now extracts a quote, accepts selected fields, and generates
a cited review. Browser verification requested another extraction, accepted only
the vendor, observed the version advance from 3 to 4, and requested a new review.
Old proposals became stale. Line items display as readable quantities and prices
instead of JSON. All 42 worker checks and the frontend build pass.

The first 10 development cases under schema v3 completed: 40/40 reference fields,
8/8 relevant passages retrieved, 2/2 correct abstentions, and 3/8 false abstentions.
These are preliminary comparisons with generated references in one development
family. Human reference verification, claim support, held-out results, embedding
comparison and outcome measurements remain open. Do not describe this as a 100%
accurate system; the false-abstention result already demonstrates a limitation.

The next development iteration separated two meanings: a missing cost center is
missing purchase information, while no retrieved policy is missing evidence.
Prompt v4 makes that distinction; schema v4 forces abstention and empty findings
when no policy text exists. The same first ten cases then produced 40/40 field
matches, 8/8 retrieval, 2/2 correct abstentions and 0/8 false abstentions. Earlier
outputs remain available; this is development improvement, not a held-out claim.

`evals/score_run.py` scores the first-N scope selected in the run manifest before
calls, checks hashes/order, and keeps missing jobs in that scope's denominators.
The human review packet displays the 120 frozen sources and expected answers,
allows progress downloads, and never marks itself reviewed. A small Python
static-file server on loopback can preview it without adding an application
framework or sending review data to a backend. No human verification is claimed
from generating or viewing that packet.

## R2 architecture: comparing search and bounding AI calls

For a laptop purchase, the policy might say "portable computers" instead of
"laptop." PostgreSQL full-text search matches words; embeddings represent text as
numeric vectors so similar meanings can rank together. The Python worker now
offers an explicit comparison mode, keeping the same query and authorized policy
versions for full-text, cosine similarity and combined reciprocal-rank rankings.
The displayed review continues to use full-text evidence while the candidates are
evaluated. A candidate's relevant passage does not prove that a generated claim
would be supported.

`retrieval.py` is Python running in the background worker. Migration V10 is SQL
and adds immutable, tenant-scoped embedding cache rows. Java's assistant endpoint
pins the comparison flag into the job input and distinguishes it when deduplicating
requests. Embeddings share the same USD 10 lifetime budget as generation. Cached
passages save calls, but a new query still needs an embedding. Exact comparison
is limited to 200 chunks; pgvector indexing is a possible scaling step, not an
installed dependency or a demonstrated performance improvement. ADR 0004 records
the model/version/cache boundaries and alternatives.

`provider_transport.py` and `provider_process.py` are Python, also in the worker.
The former keeps control in the parent while the latter makes the HTTP call in a
disposable child. A network timeout alone is not an elapsed-time deadline: a slow
stream can keep delivering bytes. The parent stops the child after 30 seconds;
the trade-off is startup overhead and potentially discarding a billed answer.
Unknown cost stays reserved. Resource limits and removal of database/storage
environment credentials reduce exposure but do not constitute a general sandbox.
ADR 0005 records the exact boundaries and tests.

## R2 evidence: successful jobs can still give wrong answers

The first full 60-case development evaluation completed every job but matched
only 207/240 expected extraction fields (86.25%). Thirty supplier values were
wrong, often because the model dropped a number from the name or missed an
unlabelled heading. Three item descriptions included adjacent supplier/quantity
text. This explains why HTTP success and valid JSON are not measures of accuracy.
The generated references still need human verification. Prompt v5 addresses these
patterns and must be evaluated separately; previous outputs remain preserved.

All three retrieval methods found 48/48 expected passages in the simple full set.
Three supplementary nine-policy probes exposed the weakness hidden by those tiny
corpora: full-text found 0/3, semantic 3/3 and the initial hybrid 0/3. Rank fusion
can dilute a useful semantic-only match when irrelevant keyword matches rank
high. Three designed examples are insufficient to choose a general winner. Keep
the baseline product behavior while documenting this diagnostic failure.

The claim-review tool is an offline HTML/JavaScript form generated by Python from
real run artifacts. `claim_review.py` binds grades to exact dataset, prediction and
output-text hashes. A reviewer splits compound text into atomic claims, supplies
reasons, and confirms all claims are represented. Counting a citation as valid is
automatic; deciding whether it supports the entire claim is human evaluation.
Missing review outputs stay visible separately. No automated tool can certify
that a reviewer made a truthful judgment; that is an explicit limitation.

Operational reports use existing durable job/outbox timestamps rather than
inventing queue durations. The first full run contained two negative first-claim
intervals. Their cause is not established; timestamp anomalies remain visible in
the report and raw export. Percentiles exclude those invalid intervals with an
explicit sample count. Provider durations use the parent's monotonic elapsed
clock, while database wall-clock timestamps serve a different purpose. Neither
these local observations nor passing tests establishes a production SLA.

Parser hardening extends the same isolation principle to untrusted PDFs: the
child receives runtime paths but no database, storage or AI environment secrets.
A small compressed PDF expanding beyond the 8 MiB content-stream limit is rejected,
and a real resource-limited child refuses a 600 MiB allocation. The configured
512 MiB memory limit is containment, not a filesystem/network sandbox.

The React/TypeScript `Sources.tsx` screen now supports pasted plain text as well
as PDF/TXT files. Pasted text becomes a TXT `File` in the browser and uses the
same authenticated upload/finalize/index pipeline. Editing happens before upload;
indexed content remains immutable. No second storage format or server endpoint
was introduced. The real browser check uploaded a USD 70 quote, extracted it,
then accepted only the supplier name. The existing USD 4200 line items and total
stayed unchanged, demonstrating explicit field selection and revision checks.

Evidence hashes operate on bytes, not on visually identical JSON. Windows text
writes originally used CRLF while Git stored LF, making the new timing report's
call-file hashes differ after checkout. JSON/JSONL now use LF in Git attributes
and Python exports explicitly write LF. Derived hashes were corrected and checked
against committed Git bytes; the frozen datasets and prediction bytes did not
change. This is an example of reproducibility extending beyond model parameters.

## Delegating reference review without inventing human evidence

The user asked the assistant to perform the reference review. The resulting AI
audit checked all 120 sources and found the field references consistent, while
flagging one ambiguous laboratory policy appearing in eight cases. It records the
AI reviewer identity and frozen dataset hashes. It does not tick human-review
checkboxes, change the held-out prompt, or relabel AI work as independent human
verification. Source clarity matters: a benchmark can mark a reasonable answer
wrong when its question or policy is ambiguous. Proposed source corrections must
be versioned so older reported results keep their original meaning.


## Accepted delegation and versioned reference corrections

Under ADR 0006 the assistant may perform reference review for the learning
project. AI review is an explicit evidence tier, not independent human validation.
The corrected v2 snapshot changes eight policy sentences while keeping v1 bytes
and historical runs reproducible. Python audits source meaning and consistency;
Node validates review coverage and case/file hashes before live execution.
An explicit profile prevents an AI artifact passing the human-review path.
These hashes detect accidental drift, not dishonesty by a reviewer.

The numerical targets and product prompt remain unchanged. Removing the user's
manual grading bottleneck does not make the evaluation independent or demonstrate
production quality. Reference correctness, prediction accuracy and supported
claims are three different questions. See ADR 0006, evals/dataset.mjs and the
v2 audit summary. Four official curated skills were installed as development
helpers; docs/development-skills.md records their purposes and source revision.


## Held-out evidence reveals the limits (2026-09-16)

For a purchase request with blank supplier/items and recorded zero total, the
assistant sometimes correctly cites the cost-center rule but then invents extra
requirements in its summary. The saved draft and the quote are different inputs:
extracted proposals are not automatically accepted. A zero draft total therefore
cannot be silently replaced with the quote total or declared invalid by a policy
that only mentions cost centers.

Full held-out extraction was 221/240, while AI-reviewed factual support was 360/412
(87.38%), below 95%. All 48 dedicated finding texts were supported; unsupported
claims were in summaries. Strict JSON and valid citation identifiers protect the
response structure but do not guarantee the full narrative is supported. Two
reviews also marked evidence insufficient despite providing supported findings.
These are separate quality dimensions, not interchangeable success flags.

Python claim-review tooling binds every output and reviewer type to exact hashes.
The repeated-run comparator scores the same ten cases in both runs: 35/40 → 37/40,
with four vendor changes. It excludes tenant-specific citation IDs from wording
comparison, verifies source content and purchase inputs, and keeps missing jobs
in their denominator. Missing input provenance is explicitly unverified. A text difference need
not change truth; the comparison does not claim to grade semantics.

The browser test used a real file-input chooser event and synthetic TXT upload,
then simulated only the assistant endpoint returning 503. A manual cost-center
change persisted at version 2 with its USD 70 total unchanged. Provider failure
does not disable the ordinary purchase editor. This was automated browser
verification, not a user pilot, OS-dialog mouse test, or production outage.

See docs/evidence/2026-09-15-r2/heldout-summary.md for commands, counts, costs,
limitations, and remaining work. Preserve frozen results and review provenance;
never lower targets or relabel old held-out data to hide an evaluation miss.

## Narrow an AI task and validate observable facts (2026-09-16)

A review can correctly quote a cost-center rule and still invent requirements in
its summary. The v5 development failures showed that asking for missing purchase
information did not sufficiently separate observations from policy obligations.
Review prompt v6 now states that boundary explicitly; extraction instructions
remain unchanged. This is prompt guidance, not proof that every sentence is true.

One prompt-only development response still listed the already populated
description as missing. That does not need an AI judge: the saved purchase
provides a direct answer. Review schema v5 supplies the allowed empty-field names
to the provider, and the worker rejects any false report after generation. A
recorded zero remains present. The rejected response and its cost are retained;
the system does not silently edit it into an apparently valid model result.

This is an implementation choice within the planned pipeline, not a new agent
framework or service. The trade-off is less flexible interpretation of "missing"
and possible failed reviews, in exchange for a checkable list. It does not decide
which fields policy requires or force the model to mention every empty field.
The manual editor remains the fallback.

Versions are specific to each task. Hashes cover the instructions and dynamic
schema actually sent, and input admission includes their size. Repeat evaluation
accepts separate extraction/review versions while rejecting an unexpected change.
Different tenant-specific citation IDs are expected across synthetic runs, so
raw prompt/schema hashes alone cannot be used to declare configuration drift.

See [the quality evidence and commands](r2-review-quality.md), the Python
[provider adapter](../services/worker/caseflow_worker/ai_provider.py), and
[validation contracts](../services/worker/caseflow_worker/ai_contracts.py).
Unit tests check application behavior; graded development output measures the
model on those examples. Neither substitutes for a fresh held-out assessment.
# Restart configuration: import only the intended identity file

`compose.yaml` is YAML read by Docker Compose on the developer's machine.
Keycloak owns sign-in; the application still owns purchase permissions.
Its import mount now exposes only the generated realm JSON. Mounting the entire
generated directory was convenient, but later demo-result JSON files caused
Keycloak to fail on restart. A narrow file mount keeps those unrelated outputs
outside the import boundary. Local restart and OIDC sign-in were verified;
see `docs/evidence/2026-09-16-r2/local-restart.md`.
## What the complete browser journey proves

The local browser check follows the product boundaries in order: administrator
publishes configuration; requester uploads a quote and accepts selected AI
fields; Java computes the total; cited review points to missing details; the
requester supplies them; manager and finance decide; Python renders the approved
snapshot; Java authorizes the download. The downloaded document matched the
stored checksum and displayed purchase. Evidence is in
`docs/evidence/2026-09-16-r2/browser-journey/README.md`.

The AI suggestions remain separate until acceptance. After the purchase changes,
the original result becomes stale. This preserves both the original advice and
the person's later correction rather than rewriting history. The trade-off is
more visible versions and occasional retries on conflicts. The check exercised
a real HTTP 409 when actions overlapped and confirmed no stale write occurred.
## Comparing workflows without inventing user impact

The JavaScript/Node runner `tests/e2e/workflow-comparison-live.mjs` calls the real
Java API locally. It compares three identical synthetic tasks under manual entry,
extraction-only, and extraction plus policy review, rotating their order. All
nine saved correct drafts. It separates successful assistance from a correct
draft obtained through fallback. Evidence and exact inputs are in
`docs/evidence/2026-09-16-r2/workflow-comparison/README.md`.

Its manual path already knows the answer. A 20 ms API save therefore cannot
represent a person's reading and typing. The trade-off is reproducible integration
evidence without the stronger usability evidence of an actual participant study.
Model calls also add waiting even when they reduce the information a person must
type. Human benefit remains unmeasured.
## R2 release status versus model quality

The fresh held-out run exposed the cost of strict literal citations: the model
sometimes joins separated text or changes whitespace, so ordinary Python
validation rejects the entire extraction. Nineteen rejected jobs reduce the
score to 164/240 (68.33%), even though all accepted fields matched references.
This is a reliability limitation in the assistant, not permission to bypass
the source checks. Three repetitions also varied between rejection and success.

The review pipeline separately scored 463/463 supported assertions under AI
grading. These are narrow synthetic results with correlated cases and reviewer
limitations. A strong review score does not repair extraction or establish
real-world quality. All previous baselines remain preserved.

R2's plan defines delivery as working assisted/manual paths and published actual
evaluation. Its provisional targets still apply; the missed extraction goal keeps
AI experimental. The manual approval/document product remains usable. See
`docs/evidence/2026-09-16-r2/r2-acceptance.md` for the exact gate mapping and
`heldout-v3-summary.md` in that directory for measured limits. R3 adds recovery
and operational evidence; it must not silently relabel experimental AI as proven.

## R3: why recovery has several boundaries

Finance approval means the purchase is approved even if document generation
temporarily fails. The application must preserve the document request, show its
execution status separately, and eventually select one valid result. A retry
must not create another approval or let an older failure replace success.

The Python worker's `caseflow_worker/jobs.py` runs in the background worker and
uses psycopg, a PostgreSQL client. Its transaction stores a consumed-event receipt
and a durable job together. A receipt means the work is saved, not finished.
`caseflow_worker/runtime.py` handles Kafka acknowledgements and execution. It
commits the consumed offset only after scheduling or an acknowledged dead-letter
record, and retries the current record when either boundary fails.

Java's `CompletionHandler.java` runs inside the Spring Boot API. It checks the
tenant, request attempt, worker ownership token and durable result before
changing the visible status. Status, audit and the event receipt belong to one
database transaction. Keeping Java responsible for that transaction preserves
the business-data ownership boundary even though Python performed the work.

The two publishers acknowledge Kafka before marking an outbox row published.
A failure between those steps can send the same event again. This deliberately
trades duplicate delivery for durable retry; consumer receipts and state checks
must make repeated effects harmless. Broker producer idempotence alone does not
make the SQL transaction and message send atomic.

The first R3 test batch injects controlled exceptions around real database
transactions and substitutes the Kafka transport. This makes exact boundaries
repeatable without timing guesses. Its limitation is equally important: a fake
acknowledgement is not a broker restart, and an exception is not a process kill.
The [R3 map](r3-status.md) keeps those required evidence tiers separate. The
existing small broker replay remains useful, but does not establish the planned
10,000-redelivery or complete crash-matrix result.

The recorded batch added six Python and five Java checks. Review strengthened
two of them: dead-letter payloads must match the exact allowed fields, and the
Java concurrency test must observe a database lock wait before releasing the
first transaction. Merely starting two threads would allow a sequential run to
pass. A privileged read-only test observer sees the lock state; the actual
handler transactions retain their restricted API role. See
[the commands and measured scope](evidence/2026-09-16-r3/recovery-contracts.md).
