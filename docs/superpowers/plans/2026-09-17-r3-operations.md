# R3 reconciliation and document cleanup

User authorization: continue R3, with routine engineering decisions delegated.
This is an extension of the plan's worker operations, not a new public API.

## Design

Reconciliation is read-only. A narrowly granted operational core view exposes
IDs, status/timestamps and missing-generation references, without purchase,
quote, policy or user contents. A worker operator CLI flags expired leases,
old queued/retry work, old unpublished API/worker outbox rows, and approved cases
without a current generation request or scheduled worker job. Bounded results
and explicit truncation keep reports manageable; no flags means only no findings
under those thresholds, not guaranteed health. Existing audited business retry
commands remain the mutation path.

Document cleanup is an explicit, job-scoped operator CLI, preview by default.
Require tenant/job UUIDs; inspect only the exact generated-document prefix,
strict canonical key grammar and a minimum 24-hour object grace period. Only
SUCCEEDED document jobs with a selected artifact are eligible; never delete the
selected key, foreign/malformed keys, fresh objects, or objects from active,
failed, missing or inconsistently described jobs. Recheck durable state before
deletion; do not infer safety from S3 listing alone. Do not collect templates,
sources or AI artifacts. Conservative scope intentionally leaves other garbage
for a later policy extension.

Every apply operation requires a new report file; persist deletion intent before
the external delete and the observed result afterward. A crash leaves an honest
unknown/pending outcome, not a false success. S3 and PostgreSQL do not share an
atomic commit. Do not automatically schedule deletion or execute it on demo data.

## Implementation batches

- [x] Add narrow operational SQL views, read-only reconciliation module/CLI and
  isolated DB tests for each finding, clean/recent states, role permissions,
  thresholds and bounded reports.
- [x] Add safe cleanup module/CLI with isolated real object-store tests,
  selected/fresh/malformed/active protection, state recheck, report persistence
  and failure paths. Tests may use an explicit controlled age clock, labeled.
- [x] Independently review each change, run relevant full suites/migrations,
  update runbook/teaching/interview/evidence/status and commit cohesive batches.

No model calls, paid cloud resources, new HTTP mutation endpoint or broad
storage sweep. Preserve the separate core/worker ownership boundary and existing
role credentials. Local operator access requires a trusted host/environment;
this is not a tenant-facing authorization surface.

Implemented lock policy: lock the successful job row, then obtain an artifact
table SHARE lock through a fixed-search-path SECURITY DEFINER function with
PUBLIC execution revoked. Worker gets no artifact UPDATE/DELETE grant. This
blocks artifact selection briefly during one bounded storage operation while
allowing unrelated heartbeats. A broad jobs-table lock was rejected by a
failing concurrency test. Short socket timeouts are not a wall-clock SLA.

Review corrected a missing-current-attempt detection gap; its regression failed
before the fix. Full results: 152 Python and 29 Java tests passed; V11/V12 applied
via Flyway. The live report diagnoses two preserved pre-document-job cases.
See the operations evidence and runbook for scope and remaining limitations.
