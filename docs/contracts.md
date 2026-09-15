# Product contracts and gates

## Authentication and tenancy

Every product endpoint except GET `/api/v1/health` requires an OIDC access token.
Validate its signature, issuer, audience `caseflow-api`, expiration and not-before.
Identity is `(issuer, subject)`; never derive authority from display names or
token realm roles. `/me` registers the signed-in identity. A selected tenant is
an untrusted route parameter until the API verifies active membership.

Tenant resources use `/api/v1/tenants/{tenantId}/...`. A tenant administrator can
add a known signed-in identity by ID and manage memberships. A new tenant's
creator receives ADMIN and REQUESTER. Members with AUDITOR read without mutation.
Requester sees owned cases, approver sees assigned cases, admin/auditor see all
tenant cases. Missing and inaccessible resources both return 404. Invalid input
is 400, unauthenticated 401, insufficient role on an accessible resource 403,
stale state/version/idempotency mismatch 409, unavailable dependency 503.

## Commands

All tenant mutations accept an `Idempotency-Key` (8–128 characters) and JSON body.
Resource updates include `expectedVersion` (nonnegative integer). The canonical
request hash includes the route resource IDs and request body. Same scoped key
and hash returns the committed 200 response after current authorization is
rechecked. Different hash conflicts. Concurrent in-progress commands conflict
with a retryable 409. Retain receipts seven days; permanent business constraints
do not expire. Command, audit, receipt and outbox share one SQL transaction.

Cases are edited only while DRAFT. Start requires a published two-step workflow,
eligible assignments, complete purchase, and (Phase 2) a published template.
Start pins inputs. Only the current assigned approver can act, never the owner.
Reject/cancel are terminal. An owned rejected/cancelled case can seed a linked
new draft. Comments are audited, increment the optimistic version, and do not
advance state. Admin reassigns only uncompleted steps, with audit.

Quantity is a positive decimal; unit price is nonnegative. Currency must be an
explicit supported ISO code. Server computes line totals and total using decimal
arithmetic and currency minor units with HALF_UP rounding. No browser total is
trusted. Lists use descending `(created_at, id)` keyset pagination with tenant,
state and assignment permission predicates applied before LIMIT.

## Versioned events (document request example)

Envelope: eventId, eventType, schemaVersion=1, timestamp, tenantId, aggregateId,
aggregateType=case, aggregateSequence, jobId, attempt, correlationId, causationId,
traceContext (currently empty; propagation remains planned), and input reference/hash. Kafka key is tenantId:caseId.
Do not include raw quote/policy text. An event ID is deduplicated at each consumer.
Scheduling receipt and queued job commit before Kafka offset. Leases use monotonic
fencing tokens. Attempt-specific object keys prevent overwrites. Final result,
completion outbox and successful state commit together. Java alone updates case
and visible job state, checking tenant, job, attempt and prior success.

## Implemented document API

Templates: GET/POST /templates, PUT /templates/{id}/content (octet-stream),
POST /templates/{id}/finalize and /publish. Mutations require tenant ADMIN;
content upload is bounded at 10 MB, finalization/publication require a command
key and expectedVersion. Published versions are visible to tenant members.
Purchases include templateId, which must reference a published same-tenant
template before start. V3 adds immutable job input records and worker tables;
V4 enables the API's result-view schema access.

GET /cases/{id}/documents and /jobs/{id} require current case access.
POST /cases/{id}/documents/{jobId}/download-url returns a 60-second signed URL
only after both core success and a selected worker artifact are present.
Previously issued URLs remain valid until expiry. POST /jobs/{id}/retry requires
ADMIN, command key and expectedAttempt; only FAILED may retry, preserving job ID.

Worker completion types are document.running, document.retry_wait,
document.succeeded and document.failed, with status, attempt and fence. Request
topic is caseflow.jobs.v1; completion topic is caseflow.completions.v1. Invalid
envelopes/references produce a redacted pointer/hash in caseflow.deadletters.v1;
unknown future completions are recorded as quarantined. Full operator replay and
reconciliation are not implemented yet. Five automatic claims bound execution;
two local execution slots and at most two unexpired leases per tenant.

## Verification design

Phase 0: empty/repeated migrations, typed OpenAPI generation, web-to-API-to-DB,
synthetic fixture structure, and these contracts. Phase 1: actual JWT validation,
membership revocation, tenant constraints, resource denial, stale writes,
duplicate/concurrent commands, no self-approval, ordered approvals, reassignment,
terminal edits, money rounding and cursor behavior. Phase 2: object validation,
rendering, durable scheduling and baseline crashes. Later gates in plan.md remain
mandatory; no release is marked complete based on code volume.

Measurements record source hash/revision, UTC timestamp, fixture version,
environment and exact command. Load methodology will fix dataset/skew, warmup,
duration, concurrency, arrival rate, workload mix and queue health before runs.
AI development/held-out split is frozen before prompt optimization; live provider
scores and costs require actual configured provider runs.
