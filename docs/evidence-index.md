# Evidence index

## 2026-09-15: R2 implementation checkpoint (release still open)

Commits through this checkpoint add bounded PDF/TXT parsing, immutable quote and
policy uploads, indexed publication, case policy pins, scoped full-text search,
AI output contracts, durable spending limits, application AI jobs and selected
suggestion acceptance. Live calls remain disabled; no AI quality is claimed.

| Claim | Check | Evidence |
| --- | --- | --- |
| Source upload/index/publication and owner/tenant boundaries | Real local API suite, including malformed PDF and stale draft | [Observed API checks](evidence/2026-09-15-r2/api-checks.txt) |
| Started policies remain accessible historically after deactivation | Refresh/search/start/deactivation API checks | Same API output and `tests/e2e/source-api.mjs` |
| Parser bounds, SQL ownership, fencing, AI schemas/budgets and eligibility | 40 pytest checks; disposable databases and synthetic transport fixtures | [Worker report](evidence/2026-09-15-r2/worker-tests.xml) |
| Explicit selected-field acceptance, replay, stale/revoked access and zero-budget admission | Three Java integration checks on disposable PostgreSQL | [Java report](evidence/2026-09-15-r2/assistant-java-tests.xml), hostname generalized |
| Existing approval-to-DOCX still works | Real document regression after R2 migrations | [Observed API checks](evidence/2026-09-15-r2/api-checks.txt) |

Browser checks observed policy source text, historical policy search and the
disabled-live-AI manual fallback on the running React app. Upload file-picker and
positive model-to-acceptance browser regression still need verification. A Vite
transform cached an empty new module during formatting; restarting this project's
development server restored it without changing product code.

Outstanding R2 gates: provider key and explicitly authorized live-test budget,
positive provider/assisted browser checks, embedding comparison, reference review,
held-out reports and repeated-run/user-outcome measurements. R1 cloud/operations
gates remain open by the user's authorized sequencing. See `docs/ai-provider.md`.

## 2026-09-14: local approved-document checkpoint

Revisions: templates `4e484a6`, worker `b371906`, completion/download API
`3603851`, browser `a1630ae`, validator hardening `14ec8f8`. PostgreSQL 18.6,
Kafka 4.2.1, SeaweedFS 4.47, Python 3.12.10; other versions below. Synthetic data.

| Claim | Check | Evidence |
| --- | --- | --- |
| Real asynchronous document pipeline and authorized download | `node tests/e2e/document-api.mjs`; validates SHA-256, size and parsed DOCX text | [Pipeline output](evidence/2026-09-14-documents/pipeline.txt) |
| Scheduling/fencing, retry and schema permissions | Seven pytest checks in disposable PostgreSQL databases, all pass | [JUnit report](evidence/2026-09-14-documents/worker-tests.xml) |
| Broker redelivery and delayed failure do not duplicate final effects | Ten request redeliveries, ten completion redeliveries, one late failure | [Replay output](evidence/2026-09-14-documents/replay.txt) |
| Product download button works | In-app browser on an assigned approved case; received browser download event | [Observed page](evidence/2026-09-14-purchases/browser-document.txt) |
| Restricted DOCX validation and template publication | Four Java validator tests plus live template-api script | Sources in Java documents tests and tests/e2e/template-api.mjs |

The final template API run is also captured in
[template output](evidence/2026-09-14-documents/templates.txt).

The first completion attempt failed because API role lacked USAGE on worker
schema. V4 fixes this while preserving base-table restrictions; pending completion
then applied. Restarting the worker caused a temporary consumer-group reassignment
delay; a newly approved queued job subsequently completed. This is an observed
restart, not an exhaustive fault-injection matrix. A Vite transform briefly cached
an empty file during formatting; restarting the development server restored it.
The Java SDK's default chunked transfer also exposed a SeaweedFS payload-checksum
failure at a chunk boundary. Disabling chunked encoding and sending an explicit
whole-file SHA-256 checksum resolved the upload check. The final template and
pipeline outputs reflect this adapter correction; AWS remains unverified.

Unfinished: complete admin-to-download browser regression, full crash matrix,
resource-limited containers, unselected-object garbage collection, operational
reconciliation, full traces/metrics, cloud, AI and performance gates. R1 is not
complete until its remaining acceptance criteria pass. Legacy purchases approved
before template pinning have no renderable snapshot and are identified in the UI.

## 2026-09-14: earlier purchase approval checkpoint

Backend revision `91dd4a6`; browser revision `2e35f6d`. Windows, Java 21,
PostgreSQL 18.6, Keycloak 26.7.3, Node 22.20.0. Real local database and OIDC;
synthetic organizations, users and purchase records. This is not completed R1.

| Claim | Executed check | Evidence |
| --- | --- | --- |
| Domain access, ordering, conflict and duplicate protections | `node tests/e2e/purchase-api.mjs` | [Raw API assertions](evidence/2026-09-14-purchases/api-tests.txt) |
| Seven Java unit tests and application package pass | `gradlew.bat test bootJar` | Test sources and local Gradle reports; four Purchase tests plus three readiness tests |
| Browser builds and uses consistent formatting | `npm run build`; `npm run format:check` in apps/web | TypeScript compilation and Prettier passed at browser revision |
| Browser-to-real-API journey | Requester signs in, creates $4,200 laptop, assigns manager/finance, submits; manager then finance sign in and approve | [Final DOM](evidence/2026-09-14-purchases/browser-approved.txt) |
| Separate approved and queued-document states | Observed final detail after finance approval | Same DOM; no download shown or claimed |
| Narrow layout | Temporary 390x844 viewport override, actual DOM viewport 312 CSS px; scrollWidth equals clientWidth | [Screenshot](evidence/2026-09-14-purchases/browser-approved-narrow.jpg); override reset |
| Development proxy readiness | `node scripts/smoke.mjs http://127.0.0.1:5173` | PASS; unauthenticated /me returns 401 |

Browser evidence is an observed session using the in-app browser, not an
automated Playwright regression suite. It verifies requester and both approval
screens; administrator screens and the full accessibility gate still need
browser checks. Draft retries retain their key within the mounted form, not
across reloads. Security adversarial JWT checks and comprehensive domain tests
remain partial. No worker crash, cloud, AI or performance result is claimed.

Resolved during this checkpoint: Jackson 3 imports/HTTP status typing and
generated-client required idempotency headers caused compile errors, then were
corrected. A build must not overwrite a JAR used by a running process; the local
API now runs from a copied artifact. Docker image pull returned a temporary 502;
retry succeeded. The prior foundation sections below are historical snapshots.

## 2026-09-11: Phase 0 foundation milestone

This is a completed connection milestone within an unfinished Phase 0. It is
not an R1 release, tenant-isolation demonstration, AI evaluation, or load test.

Environment: Windows 11 x64, Java 21.0.12.1, Node 22.20.0, Gradle 9.7.1,
Docker Engine 29.0.1 through Docker Desktop, PostgreSQL 18.6. Synthetic fixture
specification: `docs/demo-scenario.md` version 1; no business records seeded.
Source revision: base commit `61c1be5` plus uncommitted implementation;
the evidence directory contains a source hash manifest. No commit was made.

| Claim | Executed verification | Evidence |
| --- | --- | --- |
| Java compiles and packages | `gradlew.bat test bootJar --write-locks` | Packaged JAR hash in manifest; [JUnit report](evidence/2026-09-11-foundation/java-tests.xml) |
| Ready, unexpected schema, and JDBC failure paths work in isolation | Three JUnit tests; zero failures | Same JUnit report; JDBC is mocked |
| Locked frontend installs and builds | `npm ci --ignore-scripts`; `npm run build` | [Build output](evidence/2026-09-11-foundation/web-build.txt) |
| First startup applies V1 | Start JAR against empty Compose database | [Flyway log](evidence/2026-09-11-foundation/migration-first.jsonl) |
| Another startup does not rerun V1 | Start same JAR on 8081 against existing database | [Flyway log](evidence/2026-09-11-foundation/migration-repeat.jsonl) |
| API and Vite proxy match readiness contract; business routes denied | `node scripts/smoke.mjs` on 8080, 5173, and temporary 8081 | [Smoke output](evidence/2026-09-11-foundation/smoke.txt) |
| Runtime privileges and schema boundaries hold | Execute `tests/security/foundation-privileges.sql` in PostgreSQL | [Database output](evidence/2026-09-11-foundation/database.txt) |
| Database outage returns generic 503 and API recovers | Stop local PostgreSQL; run smoke with `--unavailable`; restart and run normal smoke | Same smoke output |
| Browser state and responsive layout inspected | In-app browser: initial missing API, connected, database outage, retry/recovery; narrow viewport with no horizontal overflow | [Browser observations](evidence/2026-09-11-foundation/browser.txt) |

The extra API on port 8081 was stopped after the repeat-migration check.
The development page and API on 5173/8080 and PostgreSQL remain running for
the user. Stop instructions are in the README.

## Failures preserved and resolved

- The terminal initially lacked Java on PATH although Java 21 was installed.
  Used existing machine JAVA_HOME; no JDK installation was necessary.
- TypeScript 6.0.3 conflicted with openapi-typescript's TypeScript 5 peer range.
  Changed the project pin to 5.9.3; dependency installation then passed.
- A clean npm installation while Vite was running failed with Windows EPERM
  on its loaded native module. Stopped this project's Vite process, completed
  `npm ci`, rebuilt, and restarted Vite.
- Docker Desktop failed on inaccessible `dockerInference` and `engine.sock`
  runtime files. Exact file rename also failed. With Docker stopped and contents
  inspected, renamed the socket-only runtime directories to dated backups;
  Docker then started. No factory reset, volume deletion, or configuration
  change was performed. Backups remain in the user's local application-data
  Docker directory (`run.caseflow-backup-20260911` and
  `run.caseflow-backup-20260911-2`) and alongside the secrets-engine directory
  (`docker-secrets-engine.caseflow-backup-20260911-2`). These contain old sockets,
  not project data. Do not make this repair a routine startup step.
- [Failure excerpts](evidence/2026-09-11-foundation/failures.txt) preserve the
  relevant error messages. Machine paths are redacted in the committed excerpts.

## Historical limits at the September 11 checkpoint

The schema contains a readiness marker only. Tenant/resource security,
transactions for purchases, OIDC, concurrency, jobs, Kafka, the worker, AI,
cloud, full telemetry, CI gates, load tests, and rollback are not proven here.
The public health route and restricted database role are a starting boundary,
not a complete security implementation. Local startup still gives the Java
process migration credentials. Browser verification is a recorded manual
automation session, not a committed Playwright regression suite. Linux command
equivalents have not been executed. No timing here is a performance benchmark.

Finish executable fixtures, domain/API/event contracts, measurement design,
and remaining local-service foundations before marking Phase 0 complete.
