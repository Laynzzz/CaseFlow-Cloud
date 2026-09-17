# CaseFlow Cloud

A purchase approval application: employees explain a purchase, two assigned
reviewers decide in order, and the system records the decision and its history.
The document worker produces the approved Word document. The experimental
AI assistant suggests quote fields and cites purchasing policies; people
accept suggestions and make approval decisions.

## Current status

Implemented: real OIDC sign-in, organizations and memberships, published two-step
workflows, purchase drafts, decimal totals, assignments, ordered approvals,
rejection/cancellation, comments, audit, correction drafts, cursor pagination,
optimistic concurrency, transactional command receipts and approval outbox.
React provides requester, reviewer and administrator screens. Administrators
upload and publish validated DOCX templates; requests pin a template before
submission. Java and Python exchange durable jobs/completions through Kafka.
The worker renders into S3-compatible storage; authorized users download a
checksum-verified document through a link that expires after 60 seconds.

Verified against local PostgreSQL and Keycloak: tenant/resource access,
deactivation, stale writes, duplicate commands, concurrent final approval,
ordered decisions and cursor behavior. See [evidence](docs/evidence-index.md).

**R1 remains unfinished:** the local admin-to-DOCX browser journey now passes,
but cloud deployment/smoke and remaining delivery checks are open. Existing
duplicate/lease tests are not the full recovery matrix.

**R2 is locally complete as an experimental learning release.** Assisted and
manual paths work, actual held-out results and three fixed-subset repetitions
are published, and nine automated workflow-comparison tasks completed correctly.
This meets the plan's functional/evaluation deliverable; it does **not** mean
all AI quality targets passed. See the explicit
[acceptance decision](docs/evidence/2026-09-16-r2/r2-acceptance.md).

The fresh 60-case v3 run scored **164/240 extraction fields (68.33%)**, below 90%:
19 outputs were rejected for nonliteral citations. Retrieval was 48/48, correct
abstention 12/12, false abstention 0/48. AI grading found 463/463 supported review
assertions in this narrow synthetic set; there is no independent human review
or real-world quality guarantee. Earlier baselines remain preserved. The shared
USD 10 lifetime ledger accounts for USD 0.633975, including old unknown usage.
No human time savings, production readiness or adoption is claimed.

See [fresh results](docs/evidence/2026-09-16-r2/heldout-v3-summary.md),
[browser evidence](docs/evidence/2026-09-16-r2/browser-journey/README.md),
[R2 map](docs/r2-status.md), and [architecture](docs/architecture.md).
R3 reliability and operations are now in progress; see the
[remaining-work map](docs/r3-status.md). Actual process-crash scenarios
and 10,000 broker redeliveries now pass locally; the full recovery matrix,
performance, operations and cloud gates remain open. See the
[latest recorded scope and results](docs/evidence/2026-09-17-r3/kafka-boundaries/summary.md).

## Run locally (PowerShell)

Prerequisites: Java 21, Python 3.12, Node 22.12+ within Node 22, Docker Desktop Linux engine.
Run from the repository root:

```powershell
node scripts/init-local.mjs
node scripts/generate-demo.mjs
docker compose up -d --wait postgres keycloak kafka object-store
py -3.12 -m venv services/worker/.venv
services/worker/.venv/Scripts/python.exe -m pip install -r services/worker/requirements.lock
services/worker/.venv/Scripts/python.exe services/worker/tools/create_template.py
. ./scripts/dev-env.ps1
./services/case-api/gradlew.bat -p services/case-api bootRun
```

Setup preserves existing passwords and creates ignored synthetic identity
fixtures. Compose runs services in the background. Keycloak's HTTP discovery
endpoint must be ready before sign-in; realm import can take longer than
container startup. The environment script loads credentials without printing
them. Flyway uses the migration role; requests use the restricted API role.
Cloud migration separation remains planned.

In another terminal:

```powershell
node scripts/seed-demo.mjs
npm --prefix apps/web ci --ignore-scripts
npm --prefix apps/web run dev
```

Run the worker in a third terminal:

```powershell
./scripts/run-worker.ps1
```

The worker's FastAPI endpoint at 127.0.0.1:8090/health is operational only;
business requests always go to Java. Kafka uses 127.0.0.1:9092 and local S3
uses 127.0.0.1:8333. Keep these development services on loopback.

Seeding signs synthetic users in through authorization code + PKCE and creates
Acme Studio, Northstar Workshop and Manager then Finance. It is safe to rerun.
Open [the app](http://127.0.0.1:5173). Demo usernames are requester, manager,
finance, admin, auditor and outsider. Their local password is DEMO_PASSWORD in
your ignored .env; inspect it locally when signing in. Never commit or paste
that file into logs.

Vite proxies /api to Java on 127.0.0.1:8080. PostgreSQL uses 127.0.0.1:54320;
Keycloak uses 127.0.0.1:8180. These are development settings. Keep .env with its
database volume: editing the file does not rotate existing database passwords.
Stop Vite before a clean npm reinstall on Windows.

## Verify

```powershell
. ./scripts/dev-env.ps1
$env:CASEFLOW_KAFKA_PROCESS_TESTS = '1'
./services/case-api/gradlew.bat -p services/case-api test bootJar
node scripts/generate-contract.mjs
npm --prefix apps/web run generate:api
npm --prefix apps/web run build
node scripts/smoke.mjs
node scripts/smoke.mjs http://127.0.0.1:5173
node tests/e2e/purchase-api.mjs
node tests/e2e/template-api.mjs
node tests/e2e/document-api.mjs
$env:PYTHONPATH = (Join-Path (Get-Location) 'services/worker')
services/worker/.venv/Scripts/python.exe -m pytest services/worker/tests -q
New-Item -ItemType Directory -Force output | Out-Null
services/worker/.venv/Scripts/python.exe services/worker/tools/replay_document.py --output ("output/replay-" + [guid]::NewGuid() + ".json")
docker compose config --quiet
```

The API suite needs running services and seeded identities. It creates synthetic
cases and temporarily deactivates/restores the demo requester. Use a dedicated
demo session while running it. Unit tests and UI inspection do not replace these
integration assertions. The contract generator owns OpenAPI; regenerate browser
types after changing it. A passing build alone does not complete a release gate.

The worker integration suite needs local PostgreSQL, Kafka and object storage.
The Java Kafka process suite requires `CASEFLOW_KAFKA_PROCESS_TESTS=1`; verify
it ran rather than accepting skipped tests as recovery evidence. Process tests
terminate only their own disposable test children and use temporary topics/groups.
See the [boundary-by-boundary recovery map](docs/recovery-matrix.md).
Replay needs the API,
worker and broker running plus the fixture created by `document-api.mjs`; its
default sends 20 duplicates and one late failure, recording a new output file.

Stop host services with Ctrl+C, then docker compose stop. This preserves volumes.
Never overwrite a JAR while a process is running from it; stop that API instance
before replacing its artifact.

## Project map and later learning

| Directory | Technology | Purpose |
| --- | --- | --- |
| apps/web | TypeScript + React | Browser interface |
| services/case-api | Java 21 + Spring Boot | Permissions, purchase rules and transactions |
| services/worker | Python 3.12, docxtpl, psycopg, FastAPI | Durable document jobs, lease recovery and results |
| db/migrations | SQL + Flyway | Schema, constraints and role privileges |
| infrastructure/local | Docker, shell, Keycloak fixtures | Development services |
| contracts/openapi | OpenAPI | Shared request/response definition |
| tests/e2e | Node scripts | Real identity/database integration checks |

Architecture, decisions, alternatives and limitations are recorded in the
[teaching guide](docs/teaching-guide.md). See [interview preparation](docs/interview-prep.md)
and [plan.md](plan.md) for interview answers and the remaining acceptance gates.
