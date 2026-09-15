# CaseFlow interview preparation

Status: purchase approval checkpoint, September 14, 2026. Document execution,
AI and cloud remain planned. Use the evidence index before making claims.

## Explain the product in 30 seconds

CaseFlow lets an employee submit a purchase request, assign two reviewers and
track their decisions. For example, a $4,200 laptop request goes to a manager
then finance. Java enforces the order and records an audit trail. The browser
is React, and PostgreSQL stores the organization's records. Final approval
currently queues a document request; the document worker is not implemented yet.
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
The planned worker will consume it and report document status separately.

**Follow-up:** What if the server crashes after committing approval? The durable
outbox request survives. Delivery and worker crash recovery are still to be
implemented and tested; do not claim them as completed.

Read `services/case-api/src/main/java/dev/caseflow/cases/CaseController.java`.

## Money and published versions

**Question:** Why calculate totals on the server and freeze workflow versions?

**Answer:** A browser can send an incorrect total. Java uses BigDecimal and
currency minor units, rounds line totals HALF_UP, then sums them. Published
workflows are immutable; starting copies the workflow and freezes the purchase.
A later edit should not change what an earlier reviewer decided on.

**Follow-up:** What remains? Templates/policies need equivalent version pinning.
Taxes, exchange rates and actual payment settlement are outside this model.

Evidence: PurchaseTest covers fractional quantities, minor units and draft
versus complete validation. Read `services/case-api/src/main/java/dev/caseflow/cases/Purchase.java`.

## Testing and honest limits

Seven unit tests plus real PostgreSQL/Keycloak integration checks are targeted
evidence, not proof of comprehensive security or production reliability.
Browser inspection is currently an observed session rather than a committed
Playwright regression suite. No cloud smoke, crash matrix, AI evaluation,
performance benchmark, production users or adoption claims exist yet.

Later checkpoints will add worker fencing, retrieval, AI grounding and budget
controls, query measurements, deployment/rollback and failure diagnosis.
