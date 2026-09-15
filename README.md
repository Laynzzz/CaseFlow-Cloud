# CaseFlow Cloud

A purchase approval application: employees explain a purchase, two assigned
reviewers decide in order, and the system records the decision and its history.
The planned document worker will produce the approved Word document. The planned
AI assistant will suggest quote fields and cite purchasing policies; people
accept suggestions and make approval decisions.

## Current status

Implemented: real OIDC sign-in, organizations and memberships, published two-step
workflows, purchase drafts, decimal totals, assignments, ordered approvals,
rejection/cancellation, comments, audit, correction drafts, cursor pagination,
optimistic concurrency, transactional command receipts and approval outbox.
React provides requester, reviewer and administrator screens.

Verified against local PostgreSQL and Keycloak: tenant/resource access,
deactivation, stale writes, duplicate commands, concurrent final approval,
ordered decisions and cursor behavior. See [evidence](docs/evidence-index.md).

**R1 is unfinished:** template uploads, asynchronous document execution,
downloads, cloud deployment and full release gates remain. An approved purchase
currently shows a queued document; there is no running document worker.
R2 AI and R3 reliability/portfolio gates are also unfinished. No production
readiness, adoption or measured AI quality is claimed.

## Run locally (PowerShell)

Prerequisites: Java 21, Node 22.12+ within Node 22, Docker Desktop Linux engine.
Run from the repository root:

```powershell
node scripts/init-local.mjs
node scripts/generate-demo.mjs
docker compose up -d --wait postgres keycloak
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
./services/case-api/gradlew.bat -p services/case-api test bootJar
node scripts/generate-contract.mjs
npm --prefix apps/web run generate:api
npm --prefix apps/web run build
node scripts/smoke.mjs
node scripts/smoke.mjs http://127.0.0.1:5173
node tests/e2e/purchase-api.mjs
docker compose config --quiet
```

The API suite needs running services and seeded identities. It creates synthetic
cases and temporarily deactivates/restores the demo requester. Use a dedicated
demo session while running it. Unit tests and UI inspection do not replace these
integration assertions. The contract generator owns OpenAPI; regenerate browser
types after changing it. A passing build alone does not complete a release gate.

Stop host services with Ctrl+C, then docker compose stop. This preserves volumes.
Never overwrite a JAR while a process is running from it; stop that API instance
before replacing its artifact.

## Project map and later learning

| Directory | Technology | Purpose |
| --- | --- | --- |
| apps/web | TypeScript + React | Browser interface |
| services/case-api | Java 21 + Spring Boot | Permissions, purchase rules and transactions |
| db/migrations | SQL + Flyway | Schema, constraints and role privileges |
| infrastructure/local | Docker, shell, Keycloak fixtures | Development services |
| contracts/openapi | OpenAPI | Shared request/response definition |
| tests/e2e | Node scripts | Real identity/database integration checks |

Architecture, decisions, alternatives and limitations are recorded in the
[teaching guide](docs/teaching-guide.md). See [interview preparation](docs/interview-prep.md)
and [plan.md](plan.md) for interview answers and the remaining acceptance gates.
