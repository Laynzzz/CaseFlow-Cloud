# CaseFlow interview preparation

Status: local purchase and document checkpoint, September 14, 2026.
AI and cloud remain planned. Use the evidence index before making claims.
The document checkpoint at the end records the asynchronous implementation.

## Explain the product in 30 seconds

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
