# CaseFlow Cloud — SWE / AI-SWE implementation plan

Status: revised specification; implementation and measurements not yet completed  
Revision: 2026-09-11  
Primary target: backend/full-stack SWE and applied AI software engineering  
Product: multi-tenant purchase approvals with an evidence-grounded AI review assistant  
Delivery: three demonstrable releases with explicit acceptance gates

## 1. Product description

CaseFlow helps a small operations team turn a purchase request into an approved document. A requester enters purchase details and attaches a vendor quote. Reviewers check it against their organization's purchasing policies. An AI assistant proposes extracted fields and produces a cited review brief. People accept or correct suggestions and make decisions. After final approval, a background worker renders the approved snapshot into a versioned DOCX.

Example: an employee requests a synthetic $4,200 equipment purchase. A quote supplies vendor, items, and price. The assistant highlights a missing cost center and cites the relevant purchasing-policy passage. It does not invent the missing value or approve the purchase. V1 uses a configured two-step approval workflow; AI does not dynamically create approval routing.

The project demonstrates shipping a useful application, correct Java/SQL backend behavior, evaluated AI integration, cloud delivery, and recovery from asynchronous failures. Use synthetic identities, quotes, policies, and values. Do not claim production adoption or procurement/legal compliance.

## 2. Market rationale and resume priorities

The supplied Layne_Xia_Project_Portfolio_with_Recruiter_Wants.xlsx summarizes 167 selected SWE roles (84 full-time, 83 internships). Counts below come from SWE Wants A9:I54. They are historical sample mention counts, not a representative estimate of the entire market; overlapping categories must not be summed.

| Signal | Roles / 167 | Evidence to build |
| --- | --- | --- |
| Build and ship production systems | 117 | Working product, release and demo |
| Python | 78 | Tested document and AI worker |
| Java | 36 | Domain model, APIs, transactions |
| Design systems and architecture | 35 | ADRs, boundaries and recovery contracts |
| Databases | 28 | Constraints, migrations and access patterns |
| Algorithms/data structures | 26 | Explain pagination/retrieval choices and complexity |
| Performance improvement | 24 | Controlled before/after optimization |
| SQL | 22 | Query plans, indexing, stable pagination |
| Testing/software quality | 21 | Concurrency, integration and fault tests |
| React | 18 | Usable reviewer interface |
| AWS | 17 | Deploy, operate, roll back |
| TypeScript | 15 | Typed frontend and generated client |
| Agentic AI / LLMs | 13 / 11 | Grounded assistant and held-out evaluation |

The workbook's Skill Audit marks Java and AWS as skills-only and SQL as partial evidence in the earlier resume audit (A8:H11, A35:H35). Recheck the actual resume before writing final bullets. Prioritize evidence for these gaps, full-stack ownership, useful AI, and reliability.

Do not force every workbook keyword into the project. Claude Code/Codex use belongs in development-process notes; it does not replace proof of engineering ability. This plan does not claim new verification of the underlying 167 JDs.

## 3. Releases and scope

| Release | Deliverable | Exit gate |
| --- | --- | --- |
| R1: working SWE product | Two tenants, roles, purchase cases, approvals, asynchronous DOCX, basic cloud deployment | Browser journey completes; tenant/concurrency and baseline crash tests pass; cloud smoke succeeds |
| R2: AI-assisted review | Quote extraction, policy retrieval, cited brief, explicit suggestion acceptance, evaluation | AI journey and manual fallback work; held-out results are published |
| R3: reliability and portfolio | Full crash matrix, query optimization, operations, rollback and evidence package | Repeatable load/failure results, demo and claim-to-evidence mapping |

A completed R1 is useful SWE evidence independently. Do not claim AI implementation before R2. Every release includes tests, logs and basic traces; R3 deepens these.

Required: OIDC, server RBAC, memberships, linear versioned workflows, DOCX templates, purchase drafts, assignments, comments, approvals/rejection/cancellation, immutable approved inputs, audit, downloads, and browser UI. R2 adds text-based PDF/TXT policies and quotes, extraction, retrieval and review.

Deferred: arbitrary workflow graphs, e-signatures, billing, collaborative editing, scanned-document OCR, email integrations, custom identity, multi-region, Kubernetes, model training/fine-tuning, multiple providers, multi-agent frameworks, unrestricted agent tools, and a separate vector database.

Redis caching and separately deployed outbox publisher are optional. Add them only for a demonstrated need. A managed Kafka cloud deployment is an optional extension, not an R1 prerequisite.

## 4. Users and business rules

| Role | Authority |
| --- | --- |
| Tenant administrator | Memberships/roles, workflow/template/policy versions, tenant cases |
| Requester | Owned drafts and cases, suggestion acceptance, start/cancel eligible cases |
| Approver | Assigned cases, comments and current-step approval/rejection |
| Auditor | Tenant cases, documents and audit; no mutation |
| Platform operator | Metrics and authorized retry commands; no business-content access |

Users may hold multiple roles, but a requester cannot approve their own case. Assignments require active approver membership in the same tenant. Deactivated members lose future access/actions. Administrators may reassign uncompleted steps; audit the change.

Policies are visible to tenant members in v1. Cases/quotes are visible only to owner, assigned approvers, administrator and auditor. Retrieval and result reads enforce these resource permissions before giving content to the model or user.

Purchase data includes vendor, description, line items, currency, total, cost center and justification. Use explicit currency codes and decimal arithmetic; compute totals and rounding server-side.

Drafts are editable with optimistic concurrency. Starting pins the purchase, workflow, template and policy versions. Approved inputs are immutable. Rejected/cancelled cases are terminal; a correction creates a new draft linked to the original. AI never independently approves, rejects, changes assignments or roles.

## 5. User journeys and UI

1. Sign in, create an organization or choose an authorized membership.
2. Administrator adds known signed-in identities, assigns roles, uploads a template and publishes a two-step workflow. Seed demo identities; implement actual membership UI/API. Invitation email is deferred.
3. Requester creates a purchase draft and assigns two eligible approvers.
4. R2: upload a text quote, review extracted fields, explicitly accept selected values, and inspect cited policy findings.
5. Start the case; approvers review and act in order.
6. Final approval starts document generation. Download the approved DOCX and inspect its audit/version history.
7. Demonstrate another tenant being denied access.
8. Demonstrate unavailable AI and continue the manual workflow.

Required screens: tenant selection, filtered work queue, draft form, case detail with approval/audit/document panels, workflow/template/policy administration, evidence panel with source passages and suggestion diffs, and authorized failed-job retry view.

Represent loading, empty, queued/running/succeeded/failed, unauthorized and stale-version states. Poll asynchronous jobs with backoff and cleanup. Do not silently lose input on conflict. Require keyboard access, labels, visible validation, focus handling and usable narrow-screen layouts.

The case detail shows source page/section next to each AI finding. AI suggestions are stored separately until acceptance. Historical results remain inspectable but cannot mutate a newer draft.

## 6. Architecture and pinned choices

React/TypeScript -> Java API -> PostgreSQL and object storage.
Java outbox module -> Kafka -> Python worker -> object storage/PostgreSQL.
Worker completion outbox -> Kafka -> Java completion consumer.
Python AI handler -> one hosted model/embedding provider.
Both services emit correlated logs, metrics and traces.

Use one modular Java deployment and one Python deployment. Java owns business decisions; Python executes document, ingestion and AI jobs with bounded concurrency. Keep the publisher and completion consumer inside the Java deployment initially. FastAPI serves worker health/operational endpoints only.

| Area | Choice |
| --- | --- |
| Frontend | React, TypeScript, Vite, React Router, TanStack Query, React Hook Form, Zod |
| Java | Java 21, compatible supported Spring Boot, Spring Security, Spring Data JDBC, Flyway, Gradle Wrapper |
| Data | PostgreSQL; evaluate pgvector for R2 alongside PostgreSQL full-text retrieval |
| Python | Python 3.12, docxtpl/python-docx, text-PDF parser, provider SDK, Pydantic, pytest |
| Messaging | Kafka, transactional outboxes, durable job scheduling, idempotent consumers |
| Storage | S3 in AWS; compatible local object store behind an adapter |
| Identity | Standard OIDC; Keycloak for local fixtures |
| Testing | JUnit, Testcontainers, Vitest/Testing Library, Playwright, k6 |
| Cloud/delivery | Docker Compose, GitHub Actions, ECR, ECS/Fargate, RDS, S3, ALB, Secrets Manager, Terraform |
| Observability | OpenTelemetry, structured JSON logs, collector, Grafana and selected trace/metric backends |

Verify compatibility using official documentation at kickoff. Pin versions, images, lockfiles, Gradle Wrapper and model/embedding identifiers. Installed global tooling does not establish compatibility. Do not add languages/frameworks solely for keywords.

## 7. Data ownership and invariants

Use one PostgreSQL instance with separate schemas and roles:
- Java owns core: identities, tenants, memberships, workflows/templates/policies, source metadata, cases, assignments, audit, command idempotency, API inbox/outbox.
- Python owns worker: jobs/leases, generated artifacts, parsed chunks/embeddings, AI results, worker inbox/outbox.
- Java may read explicitly exposed worker result views after authorization. Python reads narrowly scoped immutable job-input views. Neither writes the other's tables.
- Centrally ordered Flyway migrations manage both schemas through a dedicated migration role.
- Java alone changes case state. Its completion consumer validates tenant/job/attempt and atomically updates visible status, audit and inbox.

| Entity | Required constraints |
| --- | --- |
| Identity | Unique issuer + subject; no local passwords |
| Membership | Unique tenant/user, active status and roles |
| Workflow/template/policy version | Editable draft with expected version; immutable published snapshot |
| Case | Tenant, owner, pinned versions, snapshot, optimistic version |
| Assignment | Tenant/case/step, eligible member, one terminal step outcome |
| Source | Tenant, case/policy owner, immutable object version/checksum, validation state |
| Job | Stable logical request ID, input revision/hash, attempt, lease, fencing token |
| Artifact | Unique logical generation request; selected immutable object key/checksum |
| AI result | Case/source/policy/model/prompt/schema versions, citations and usage |
| Command record | Scoped key, request hash, committed response, expiry |
| Inbox/outbox | Unique consumer/event receipt or event ID, publish state |

Use composite tenant-inclusive keys and foreign keys for case-to-workflow/template, assignments-to-memberships, source-to-case and result relationships. Tenant context comes from verified membership, not trusted request-body data. Every repository access is scoped. UUIDs/object prefixes are not access control.

Audit is append-only for application roles. Explain that privileged database administrators can still modify storage; do not call it cryptographically tamper-proof.

## 8. API surface and command semantics

Product routes use /api/v1, OpenAPI-generated TypeScript clients and structured problem details. Define exact schemas/methods and authorization tests before implementing each group.

| Route group | Operations |
| --- | --- |
| /me, /tenants | Identity/memberships; create tenant; authorized selection |
| /tenants/{id}/memberships | List/add known identity/change roles/deactivate |
| /workflows and versions | Create, edit draft, validate/publish |
| /templates and versions | Initiate upload, finalize/validate, publish |
| /policies and versions | R2 upload/ingest/publish indexed immutable version |
| /cases and /cases/{id} | Create/list/detail/update owned draft |
| /cases/{id}/assignments | Assign/reassign uncompleted steps |
| /cases/{id}/start and /actions | Start/approve/reject/comment/cancel |
| /cases/{id}/sources and /sources/{id}/finalize | Allocate upload, pin validated object, ingest |
| /cases/{id}/ai/extractions and /ai/reviews | Create revision-pinned jobs |
| /cases/{id}/ai/results/{resultId} | Read authorized result/citations |
| /cases/{id}/ai/results/{resultId}/accept | Accept selected fields into matching draft |
| /cases/{id}/documents and download-url | Read authorized metadata/download |
| /cases/{id}/audit and /jobs/{id} | Paginated audit and permitted job status |
| /jobs/{id}/retry | Audited authorized retry of eligible failed job |

Comments are audited commands but do not advance approval state. Mask inaccessible-resource existence consistently. Recheck current access before replaying an idempotent response.

Idempotency applies to case creation, state transitions, upload finalization, AI job creation, suggestion acceptance and retry:
- Scope by tenant, actor, operation and key. Bind to canonical request hash including resource IDs and expected version.
- Same key/hash after commit returns original status/body subject to current authorization; different hash is a conflict; in-progress concurrent requests receive a retryable conflict.
- A unique database constraint serializes keys. Mutation, audit, response record and outbox commit together. Rollback removes all of them.
- Default retention seven days, documented in API contract. Business constraints remain permanent after key expiry.
- Draft changes/transitions require expected version. Return conflict rather than silently overwrite.

## 9. State machines and versioning

Separate business state from document execution:

Case: DRAFT -> ACTIVE -> APPROVED or REJECTED.
DRAFT/ACTIVE -> CANCELLED.
Document: QUEUED -> RUNNING -> SUCCEEDED.
RUNNING -> RETRY_WAIT -> RUNNING, or FAILED.
FAILED -> QUEUED via an authorized retry.

Final approval atomically records APPROVED, immutable rendering inputs, stable generation request ID and outbox event. Rendering failure never reverses approval. The UI shows approval and document status separately.

A successful job is terminal. Retrying a failed job preserves its logical request ID and increments attempt. Policy updates do not silently change active cases. A draft can explicitly refresh pinned policies, invalidating older AI output. Stale AI results cannot be accepted.

## 10. Events and crash recovery

Envelope: event ID/type/schema version, timestamp, tenant, aggregate ID/type/sequence, logical job ID, attempt, correlation/causation IDs, trace context and validated references. Prefer IDs to raw document text. Partition by tenant + case. Consumers also validate state/attempt because separate topics/publishers do not guarantee global ordering.

Events cover case transitions; document requested/completed/failed; ingestion requested/completed/failed; AI extraction/review requested/completed/failed. Version JSON Schemas and compatibility fixtures.

Execution protocol:
1. On request consumption, atomically insert inbox receipt and durable QUEUED job if absent. Commit Kafka offset only after that transaction. Receipt means durable scheduling, not finished work.
2. Dispatcher leases a queued job with an increasing fencing token. Heartbeat; expired leases are reclaimable. Run rendering/model calls outside a DB transaction.
3. Write results to immutable attempt-specific object keys and compute checksum. A stale attempt must not overwrite another attempt's binary.
4. Conditional on the current fencing token, atomically finalize result metadata, mark SUCCEEDED and insert completion outbox. A stale worker cannot finalize. Garbage-collect unselected objects after a grace period.
5. Publish completion and mark published only after broker acknowledgement. Duplicates after acknowledgement/mark crashes are expected.
6. Java validates tenant, job and current attempt; atomically records inbox receipt, visible result status and audit; then commits offset. Old failure events cannot overwrite success. Quarantine unexplained future/out-of-order events for reconciliation.

Transient execution failures use bounded exponential backoff/jitter (initial default five attempts). Validation failures are permanent. Model-call retries have a separate small bound and budget. Exhaustion creates durable FAILED status/event. Poison envelopes go to a redacted dead-letter topic with replay instructions.

Test crashes before/after scheduling commit, before offset commit, after object upload, after result transaction, after event publish, during lease expiry and after Java update. Test concurrent workers, stale fencing tokens, delayed failure after success, broker/database restart and object-store timeout.

Reconciliation flags expired leases, old queued jobs, unpublished events and approved cases missing current jobs. Operator retry is audited. Do not claim exactly-once transport or model billing: calls may repeat after a crash even when business effects are idempotent.

## 11. AI assistant implementation

The assistant is a fixed asynchronous pipeline, not an unrestricted agent. It cannot approve/reject, change roles, execute arbitrary code/URLs or read unscoped content. Manual review remains usable if the provider fails.

Ingestion:
- Initially support text PDF/TXT, maximum 10 MB and 50 pages (configurable).
- Reject scanned-only, encrypted, malformed or unsupported sources clearly.
- Parse in a resource-limited worker; preserve source/page/section offsets and hashes.
- Store parser/chunking/embedding versions and dimensions.
- Publish policies only after indexing succeeds. Deactivated versions are excluded from new case retrieval; active cases retain explicitly pinned historical policy access under tenant permissions.

Extraction schema:
- case revision, source version, proposed fields with typed value or null, supporting quote, page/span reference and warnings.
- Fields: vendor, line items, currency, total. Missing values remain null.
- Validate arithmetic/currency in ordinary code. Model self-confidence is not a calibrated probability.
- Keep suggestions separate; accepting selected fields requires a matching draft version and records before/suggested/accepted values in the audit.

Review pipeline:
1. Load authorized case snapshot and pinned policies.
2. Retrieve eligible policy chunks; baseline PostgreSQL text search, candidate embedding/hybrid retrieval on the same evaluation queries.
3. Send bounded facts/evidence to one provider with a versioned prompt and schema.
4. Produce summary, missing_information, policy_findings, citations and insufficient_evidence. Every finding references a retrieved passage.
5. Validate schema, source IDs and access before display. Surface invalid/unavailable results; do not silently turn unsupported output into facts.

Citation existence is checked in code; whether it supports a claim requires evaluation. Treat source instructions as untrusted text. Include adversarial documents and permission revocation in tests.

Record model/prompt/schema versions, input hashes, timing, tokens, estimated cost using dated pricing configuration, retries and errors. Set per-job token/time limits, per-tenant concurrency and daily spend ceiling. Unknown usage cost is not zero. Do not log raw source content or secrets.

Start with final validated responses and polling, not streaming. No orchestration framework is required. A later read-only tool-call experiment must demonstrate task improvement before joining core scope.

## 12. AI evaluation and release gates

Create evals before prompt optimization. Initial target: 120 synthetic cases, 60 development and 60 held-out. Split by policy/template family to reduce near-duplicate leakage. Include missing facts, conflicting quotes, insufficient policy evidence and malicious instructions. Add separate tenant/access-revocation tests.

Manually verify reference fields/passages/expected abstentions. Version annotations and rubric. If tuning uses held-out examples, retire them into development and create a new test version. Do not describe synthetic results as real-world validation.

| Measure | Method |
| --- | --- |
| Extraction | Normalized exact match by field, denominators and missing-value accuracy |
| Retrieval | Recall@5 against annotated relevant passages |
| Grounding | Claim-level citation support and unsupported claims with manual rubric |
| Abstention | Correct/false abstention on answerable and unanswerable cases |
| Output validity | Schema/citation checks for all displayed results; surface failures |
| Isolation | No unauthorized passages/results in the named test suite |
| User outcome | Completion time, corrections and completion rate with/without assistance |
| Operations | Queue/end-to-end/model p50/p95, retries, tokens and cost per review |

Compare manual, extraction-only and grounded-review workflows. Compare text retrieval baseline to the chosen candidate. Repeat a fixed subset to quantify model variability. Store raw outputs under controlled synthetic-only fixtures.

Provisional targets to freeze before first held-out evaluation: at least 90% extraction match on supported fields, 90% Recall@5 and 95% supported cited claims. These are project goals, not industry standards. Report counts, category failures and actual scores. Missed gates leave AI explicitly experimental; the manual product can still ship.

Aim for a 3–5 participant synthetic-task pilot, counterbalancing manual/assisted order where practical. Record consent and method. Author-only testing is a self-test. Never invent users or time savings.

## 13. Security and upload lifecycle

Use OIDC code + PKCE and server issuer/audience/expiry validation. Recheck active membership for mutations and sensitive reads. Separate API/worker/migration permissions and least-privilege IAM. Store secrets in environment stores.

Upload sequence: authorize temporary key -> upload with size bounds -> validate actual type/checksum/archive structure -> pin or copy immutable validated object -> expose to jobs. Never validate one object then consume a replaceable version. Restrict DOCX placeholders and template expressions; reject archive bombs and unsupported expressions.

Authorize every download before short-lived URL issuance. Document that an already issued bearer URL remains valid until expiry; use authenticated proxy downloads if immediate revocation becomes required.

Use durable job admission/concurrency limits for expensive operations. If Redis is added, document fail-closed versus bounded fallback behavior per endpoint; cache failure must not remove AI spend limits or corrupt state.

Threat model includes tenant bypass, object references, malicious uploads, prompt injection, secret leakage and repeated expensive jobs. Run secret/dependency/container scans. Use synthetic data and keep personal resumes/application histories outside this project.

## 14. SQL, performance and observability

Build a tenant-scoped work queue filtered by status/assignee, ordered by created_at plus id, with consistent cursor semantics. Include permission predicates, composite indexes, pagination-under-inserts tests and N+1 checks.

Required optimization: record baseline query plan/latency; change one index/query choice; rerun identical workload/environment; report improvement or regression and write/storage trade-offs. Seed small and skewed tenants at sufficient size to expose actual plans.

Separate HTTP acknowledgement, document queue/execution/completion, and AI queue/model/completion latency. Specify workload mix, payloads, tenant distribution, dataset size, cache state, warmup, duration, environment, revision, concurrency and arrival rate. Record dropped iterations, errors, backlog growth and saturation. Fast acknowledgements with unbounded backlog are not sustainable throughput.

Metrics: HTTP rate/errors/latency, DB pool/transactions, outbox age, Kafka lag, queue age, leases/retries/dead letters, document duration, AI tokens/cost/validation. Correlate traces across outbox, broker and worker using context or span links. Avoid tenant/case IDs as unbounded metric labels.

Full tracing is appropriate for bounded demo tests; document load/cloud sampling. Do not promise universal 100% export. Alerts for old jobs/outbox, repeated failures and latency link to runbooks. Show one diagnosed failure and fix.

## 15. Tests and CI

| Layer | Required evidence |
| --- | --- |
| Unit/domain | Transitions, permissions, validation, retry decisions |
| Contract/API | Generated client, errors, stale writes, idempotency hash mismatch |
| DB integration | Tenant constraints, concurrent writes, inbox/outbox atomicity |
| Worker | Rendering, leases, stale fencing, object finalization and completion |
| Browser | Admin-to-download, manual fallback, suggestion acceptance, accessibility |
| AI | Versioned held-out metrics, access tests, adversarial cases |
| Resilience | Every section 10 crash boundary, duplicates and reordering |
| Performance | Query before/after and mixed sustained workloads |
| Deployment | Empty/prior-schema migrations, smoke, rollback and teardown |

PR gates: formatting/lint/typecheck, unit/contract tests, targeted integration, image build, secret/dependency scans, Terraform validation. Broader load/crash suites run on release or scheduled workflows.

Mock model responses in routine CI; budget live eval runs and record provenance. Target 80% branch coverage in explicitly declared critical domain modules plus invariant tests; percentage and test count alone do not establish quality.

## 16. Cloud delivery and cost

R1 uses ECS Java/Python, RDS, S3, TLS, identity, secrets and basic monitoring; serve the built frontend from the application or static hosting. A short-lived single-node Kafka VM is acceptable initially with an ADR explicitly documenting no broker high availability. Managed Kafka is an optional R3 profile. Redis/ElastiCache is not required.

Before provisioning, choose region, supported messaging profile and identity configuration; estimate costs using current pricing. Budget alerts do not cap spending. Credentials/account authority are prerequisites.

Terraform covers networking, services, storage and roles. Document bootstrap of remote state, credentials and external identity separately. A clean-account deployment claim requires these prerequisites.

Release: immutable images -> backward-compatible migrations -> health-gated update -> workflow smoke -> evidence record. Rollback restores prior images and depends on expand/contract schema compatibility. Execute the rollback test.

Teardown verifies remaining resources and documents intentionally retained state/logs/backups and their costs. Do not delete user data implicitly.

## 17. Phases and planning estimate

Working estimate: 200–320 focused hours for the complete project, to recalibrate after R1. At 15–20 hours/week, roughly 10–22 weeks. This is an estimate, not a deadline; maintain useful milestones.

| Phase | Work | Exit criterion |
| --- | --- | --- |
| 0 | Fixtures, ADRs, versions, Compose, schemas, OpenAPI and measurement design | Web calls API, DB migrates, key contracts documented |
| 1 | Auth/memberships, drafts, assignments, approvals, audit, idempotency and UI | Two isolated tenants complete approvals; concurrency tests pass |
| 2 | Uploads, durable jobs, rendering, completion outbox, basic AWS/CI | R1: browser-to-DOCX local/cloud with baseline duplicate/crash proof |
| 3 | Freeze eval split; policy/quote ingestion, extraction and acceptance | Auditable suggestions, unsupported-input and stale-result handling |
| 4 | Retrieval, grounded review, budgets and held-out evaluation | R2: assisted/manual paths work; actual quality report exists |
| 5 | Full recovery matrix, 10,000 injected redeliveries, query optimization, operations | Named invariants pass; before/after and rollback evidence exists |
| 6 | Pilot/self-test, demos, documentation and resume evidence | R3: clean demo and traceable public claims |

Introduce tests, telemetry and docs as each feature lands. Release completion depends on its gate, not elapsed time or generated code volume.

## 18. Repository and evidence layout

- apps/web
- services/case-api (domain, HTTP, outbox publisher, completion consumer)
- services/worker (documents, ingestion, AI, leases, worker outbox)
- db/migrations (ordered core/worker migrations)
- contracts/openapi and contracts/events
- evals/datasets, evals/runners, evals/reports
- tests/e2e, tests/security, tests/resilience, tests/load
- infrastructure/terraform and infrastructure/observability
- scripts (seed/reset/benchmark/replay/evidence)
- docs/adr, docs/evidence-index.md, architecture, threat-model, runbook, benchmark-methodology and demo-script
- .github/workflows, compose.yaml, README.md, lockfiles and Gradle Wrapper

Document Windows-friendly local commands and Linux CI equivalents. Each result includes command, revision, fixture version, environment, timestamp, raw output, analysis and limitations. Preserve failed runs.

## 19. Demo and feature-to-resume mapping

Five-minute product demo: synthetic request/quote -> extracted suggestions -> missing field -> cited policy brief -> human correction -> two approvals -> DOCX/audit. Show insufficient evidence and manual fallback.

Separate engineering walkthrough: denied tenant access, duplicate/crash recovery, one logical output, trace, SQL optimization, evaluation report and deployment rollback.

| Capability | Evidence before a resume claim |
| --- | --- |
| Java/backend | Domain/API code, authorization/concurrency tests, ADR |
| SQL | Migrations, tenant constraints, query plans and measured optimization |
| React/TypeScript | Browser journey, generated client, error/accessibility tests |
| AWS/CI | Terraform, deployed revision, smoke/rollback and cost record |
| Distributed processing | Inbox/outbox, leases, duplicate/crash reports |
| Applied AI/RAG | Authorized retrieval, structured results/citations, held-out report |
| Product impact | Actual pilot results, or explicitly labeled self-test |
| Debugging | Failure diagnosis linked to telemetry, fix and regression test |

Future bullet templates; replace placeholders only with actual results:
- Built a multi-tenant purchase approval platform using Java, React, PostgreSQL and AWS, measuring [throughput/p95] under [workload/environment].
- Implemented durable asynchronous processing with transactional outboxes and fenced leases; observed [outcome] across [count] duplicate deliveries and [named crash cases].
- Integrated a policy-grounded AI assistant with typed extraction and citations; measured [quality] on [held-out synthetic case count], at [latency/cost].

Choose two or three strongest outcomes for the relevant resume. Do not claim real production traffic, universal security or model-training expertise from this application.

## 20. Definition of done

- [ ] Each release has a separately recorded actual status.
- [ ] Tenant/resource permissions and schema integrity have positive/negative tests.
- [ ] Idempotency, leases, fencing and completion recovery contracts work.
- [ ] One immutable output is selected per logical request despite retries.
- [ ] Suggestions require acceptance and stale results cannot mutate new drafts.
- [ ] AI inputs are scoped and versioned; citations and quality are evaluated.
- [ ] Manual workflow survives provider errors.
- [ ] Held-out results and baseline comparisons exist without tuning leakage.
- [ ] Performance includes workload, environment, errors and queue health.
- [ ] Cloud deploy/smoke/rollback/teardown were executed.
- [ ] Clean-checkout demo uses synthetic data and documented prerequisites.
- [ ] User evidence is correctly labeled pilot or self-test.
- [ ] Every resume claim maps to observed evidence; missed targets remain visible.

Control scope, cloud/model expense, provider variability, crash gaps and synthetic-evaluation bias through release gates, bounded budgets, explicit recovery, held-out data and a working product before optional infrastructure.

## 21. Instructions for the implementing coding agent

- Read this plan and preserve CLAUDE.md's learn-while-build guidance. Explain new tools, purposes and trade-offs, and show where core concepts are enforced.
- Work phase by phase and demonstrate exit criteria before marking completion.
- Create an ADR before changing a pinned architecture decision. Routine implementation choices do not require confirmation unless they materially change scope, cost authority or product behavior.
- Use official documentation for compatible versions; commit wrappers and lockfiles.
- Keep changes reviewable and maintain docs/evidence-index.md linking claims to code, tests and raw artifacts.
- Never fabricate benchmarks, evaluations, users or adoption.
- Use synthetic data; do not add credentials, personal resumes, contact details, tokens or real application data.
- At phase end update README status, known limits, one or two files the user should read, and the next reproducible command.
