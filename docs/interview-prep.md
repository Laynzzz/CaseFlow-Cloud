# CaseFlow interview preparation

Status: local purchase, document and live AI checkpoint, September 15, 2026.
AI extraction, explicit acceptance and cited review run locally; held-out quality
and cloud gates remain open. Use the evidence index before making claims.

## Explain the product in 30 seconds

Latest AI checkpoint: real quote extraction, explicit selected-field acceptance,
and a cited policy review work locally. In the first ten development cases,
schema v3 produced 40/40 field matches and 8/8 relevant passages, but 3/8 answerable
reviews incorrectly flagged insufficient evidence. References and claim support
still need human review; these results do not establish held-out quality.

After clarifying missing facts versus missing policy evidence and constraining
the empty-evidence schema, the same ten development cases returned 40/40 field
matches, 8/8 retrieval, 2/2 correct abstentions and 0/8 false abstentions. Describe
this as a small development iteration; the preserved failures explain the
engineering decisions and are not evidence of broad model reliability.

- **Why use both a strict model schema and code validation?** The schema constrains
  decimal formats and allowed citation IDs; code still checks exact source quotes,
  arithmetic, permissions and draft versions. Live failures exposed a currency
  suffix and a malformed citation ID, both rejected before acceptance.
- **Does a valid citation make a claim true?** No. It proves the quoted text exists
  in authorized evidence. A person still needs to check whether the passage
  supports the whole claim. The release report keeps that measure ungraded.

CaseFlow lets an employee submit a purchase request, assign two reviewers and
track their decisions. For example, a $4,200 laptop request goes to a manager
then finance. Java enforces the order and records an audit trail. The browser
is React, and PostgreSQL stores the organization's records. Final approval
queues a document request; a Python worker renders it and records a downloadable
Word file. Inbox/outbox records and fenced leases handle duplicate delivery and
stale workers.
The planned AI assistant will extract quote details and cite policy evidence,
while people continue to accept suggestions and approve the purchase.

## Identity and tenant isolation

**Question:** Why does the API read memberships if the token already has roles?

**Answer:** Keycloak proves identity using a signed token with checked issuer,
audience and expiry. Application memberships determine access to each tenant.
Reading their current active status prevents an old token from retaining a
revoked membership. Queries also check case ownership or assignment, and SQL
foreign keys include tenant IDs to reject cross-tenant references.

**Follow-up:** Does a UUID protect a record? No. Authorization must precede reads,
updates, result replay and eventually download issuance.

Evidence: `tests/e2e/purchase-api.mjs` tests outsider reads, unassigned reviewers,
auditor mutations and deactivation. Implementation:
`services/case-api/src/main/java/dev/caseflow/identity/Access.java` and
`db/migrations/V2__purchase_domain.sql`. Token adversarial tests are still partial.

## Conflicts and duplicate requests

**Question:** What happens if finance clicks twice or two approvals arrive together?

**Answer:** Java locks the case and compares the expected version. Only one
conflicting transition can succeed. A scoped idempotency key stores the request
hash and response in the same transaction as the update, audit and outbox.
Repeating that key with the same body returns the original response after
checking current access. A changed body conflicts. The UI preserves a draft
editor's original version so background refresh cannot hide a conflict.

**Follow-up:** Is this exactly-once delivery? No. Receipts last seven days;
permanent business constraints still protect terminal state. Retries after
network failures can reach the server more than once. The draft key is held
in memory, so a page reload does not preserve it.

Evidence: concurrent final approval returns one success and one 409; duplicate
start/approval and hash mismatch assertions are in the API suite. Read
`services/case-api/src/main/java/dev/caseflow/common/Commands.java`.

## Approval and document execution

**Question:** Why not render the Word file inside the approval transaction?

**Answer:** Approval is a human business decision. Slow or failed rendering
should not keep a database transaction open or reverse that decision. The
implemented final approval commits a stable generation ID and outbox request.
The worker consumes it and reports document status through a completion outbox.

**Follow-up:** What if the server crashes after committing approval? The durable
outbox request survives. Duplicate delivery and lease recovery have targeted
tests; the complete crash matrix and cloud behavior are still unverified.

Read `services/case-api/src/main/java/dev/caseflow/cases/CaseController.java`.

## Money and published versions

**Question:** Why calculate totals on the server and freeze workflow versions?

**Answer:** A browser can send an incorrect total. Java uses BigDecimal and
currency minor units, rounds line totals HALF_UP, then sums them. Published
workflows are immutable; starting copies the workflow and freezes the purchase.
A later edit should not change what an earlier reviewer decided on.

**Follow-up:** What remains? Templates now pin a published version too; policies
still need version pinning when AI ingestion is implemented.
Taxes, exchange rates and actual payment settlement are outside this model.

Evidence: PurchaseTest covers fractional quantities, minor units and draft
versus complete validation. Read `services/case-api/src/main/java/dev/caseflow/cases/Purchase.java`.

## Testing and honest limits

Seven unit tests plus real PostgreSQL/Keycloak integration checks are targeted
evidence, not proof of comprehensive security or production reliability.
Browser inspection is currently an observed session rather than a committed
Playwright regression suite. No cloud smoke, crash matrix, AI evaluation,
performance benchmark, production users or adoption claims exist yet.

Later checkpoints will deepen failure tests and add retrieval, AI grounding and budget
controls, query measurements, deployment/rollback and failure diagnosis.

## New checkpoint: asynchronous documents

**Question:** What stops two workers from producing two final documents?

**Answer:** The logical job has a unique database key. A lease claim increments
its fencing token. Completion must match the current token, attempt, owner and
unexpired lease. The selected artifact has a unique tenant/job key and commits
with successful job state and completion outbox. Competing or stale workers can
upload unselected objects, but cannot choose another final artifact.

**Follow-up:** Is execution exactly once? No. Uploads and execution can repeat
after a crash. Garbage collection of unselected objects is still planned.

**Question:** How did you prove a delayed failure cannot undo success?

**Answer:** The worker rejects a failure update after successful finalization.
Java also checks current attempt, fence, stored worker state and prior success.
The broker probe publishes ten duplicate requests, ten duplicate completions
and a new delayed failure event. It asserts one selected artifact, one success
audit, and preserved SUCCEEDED status. That is targeted evidence, not a full
crash matrix or high-availability claim.

**Question:** What implementation failure did you diagnose?

**Answer:** Rendering succeeded but Java completion retried. PostgreSQL showed
permission denied for the worker schema. Granting SELECT on a view was not
enough; schema USAGE was also required. A new migration added USAGE while
preserving denied access to base tables. The durable event replayed successfully.

Supporting code: `services/worker/caseflow_worker/jobs.py`,
`services/worker/tests/test_jobs.py`, `services/worker/tools/replay_document.py`,
`db/migrations/V4__api_worker_view_access.sql`, and the document evidence folder.
# R2 evidence preparation checkpoint (2026-09-14)

- Why parse before calling AI? The assistant needs a bounded, immutable record of
  what the quote/policy says. Python extracts page text and hashes chunks so later
  citations can be checked against exact source versions. Follow-up: PDF text
  extraction can lose layout; source existence alone does not prove claim support.
- Why run a separate parser process? Memory/time limits contain oversized or
  pathological files without blocking the long-running worker. Follow-up: process
  limits are not a complete security sandbox; container restrictions remain work.
- Why freeze evaluation before prompts? A family-separated held-out split reduces
  tuning leakage. The 120 synthetic references currently await human review;
  there are no measured model-quality or user-time-saving claims.

Evidence: `services/worker/tests/test_parsing.py` (13 passing checks),
`docs/adr/0003-r2-evidence.md`, `evals/README.md`. Upload wiring and AI calls are
subsequent work; do not describe them as verified by these parser tests.
# R2 source integration checkpoint (2026-09-14)

- Why are policy jobs separate from cases? Policies belong to an organization and
  can support multiple purchases. Nullable case IDs plus explicit source owners
  model that relationship without fictitious cases. SQL checks and scoped event
  validation prevent attaching a job to the wrong owner.
- When is a policy usable? After immutable upload, successful bounded parsing and
  transactional chunk selection, Java records indexing success; an administrator
  explicitly publishes it. A failed parse cannot be published.
- Why does attaching a quote change the draft version but not purchase values?
  Evidence changes the input context. Incrementing the revision makes future
  stale AI suggestions detectable while preserving human control of purchase data.

Evidence: `tests/e2e/source-api.mjs`, `services/worker/tests/test_ingestion.py`,
`db/migrations/V5__evidence_sources.sql`. AI quality is not measured by these tests.
# R2 policy history checkpoint (2026-09-15)

- What happens when a policy changes? Upload/publish a new immutable version.
  Drafts explicitly refresh their selection; started purchases retain old pins.
  Deactivation excludes new use while preserving authorized historical evidence.
- Why PostgreSQL full-text search first? It is a small, inspectable baseline using
  the existing database and tenant/source filters. It may miss synonyms. The
  embedding/hybrid alternative must show improvement on identical frozen queries;
  no retrieval-quality improvement has been measured yet.
- Can a requester refresh policies during an approval? No. The Java command and
  SQL trigger reject pin changes outside DRAFT; this protects the review history.

Evidence: `tests/e2e/source-api.mjs`, `services/worker/tests/test_policy_pins.py`,
`db/migrations/V6__policy_pins.sql`, `PolicyPinController.java`.
# R2 AI contract checkpoint (2026-09-15)

- Does valid JSON mean reliable AI? No. Schema validation proves shape, citation
  validation proves a supplied passage contains the quote, and arithmetic checks
  prove numeric consistency. None alone proves that the passage supports the claim.
- How do you bound spend across retries? Reserve the worst-case cost before each
  call in a transaction. Unknown usage keeps the reservation; settled actual usage
  releases only unused budget. Concurrent reservations share a durable lock.
- What happens when access changes during a call? Recheck before sending and
  selecting the result. Stop further use after revocation; already-sent provider
  content cannot be recalled. SDK retries are disabled and no arbitrary tools exist.

Evidence: `test_ai_contracts.py`, `test_ai_budget.py`, `test_ai_provider.py` and
`docs/ai-provider.md`. Transport fixtures pass; application AI wiring and live
quality evaluation remain unfinished at this checkpoint.
# R2 human acceptance checkpoint (2026-09-15)

- How can you prove AI cannot silently change purchase data? Job results live in
  worker-owned storage. Only a separate authorized Java acceptance command writes
  chosen draft fields, with revision checks, decimal validation and an audit record.
- What if I click Accept twice? The same idempotency key replays the first response
  without another mutation. A new command using the old proposal is stale after
  the first acceptance increments the draft revision.
- What has actually been verified? Database-backed acceptance and access rules,
  worker eligibility/fencing and mocked transport contracts. Live AI quality and
  the full assisted browser journey have not yet been verified.

Evidence: Java `AssistantIntegrationTest` and Python `test_assistant.py`. The
running application explicitly leaves live AI disabled while budget/key setup is
pending. There is no production/adoption or measured time-saving claim.
# R2 evaluation accounting checkpoint (2026-09-15)

- Why include failed AI jobs in accuracy denominators? Users experience those
  failures. Dropping them would overstate successful task completion. A missing
  prediction also cannot masquerade as a correct null-valued extraction.
- Does a 100% fixture score establish model quality? No. Fixtures test the scorer.
  Actual provider outputs, verified references and semantic grading are separate
  evidence. The diagnostic scorer cannot mark the release complete.

Evidence: `evals/scoring.py`, `evals/test_scoring.py` (five passing checks), and
dataset checksum validation. Live runs and embedding comparison remain pending.
# Live-provider failure checkpoint — 2026-09-15

- **What happens if the AI provider rejects a request?** The worker records a
  failed job, the purchase stays unchanged, and manual entry remains available.
  Two real extraction attempts failed; the second recorded HTTP 429. This is
  failure-handling evidence, not AI-quality evidence.
- **Why reserve money before sending?** A shared PostgreSQL lock and ledger
  prevent concurrent workers spending the same allowance. Unknown usage retains
  its upper-bound reservation. The authorized USD 10 is global across runs;
  USD 0.039322 is currently reserved for two uncertain attempts, not proven billing.
  Follow-up: conservative reservations can exhaust the allowance earlier than
  actual provider billing; reconciliation needs evidence before releasing them.

Evidence: [provider contract](ai-provider.md),
[live test](../tests/e2e/assistant-live.mjs),
[safe diagnostic test](../services/worker/tests/test_ai_provider.py).
