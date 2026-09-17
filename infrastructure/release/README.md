# Isolated local release rehearsal

This profile packages the React app and Java API together and runs the Python
worker separately, as pinned by `plan.md`. It uses its own Compose project,
network and four persistent volumes. The existing development stack stays on
its original ports and data. This is a local release rehearsal, not AWS delivery
or an assertion of production readiness.

Prerequisites: Docker Desktop with Linux containers and sufficient available
memory (allow at least 4 GB for this stack), Node 22.12+ within major 22, Git,
and network access to the pinned container registries/package repositories.
Java and Python build tools run inside containers. Windows PowerShell and Linux
use the same commands from the repository root:

```text
node scripts/init-release.mjs
node scripts/release.mjs build release-a
node scripts/release.mjs deploy release-a
node scripts/release.mjs build release-b
node scripts/release.mjs deploy release-b
node scripts/release.mjs rollback
node scripts/release.mjs status
node scripts/release.mjs stop
```

Build once per unique name. Build records full source revision, dirty-worktree
status, a SHA-256 digest of source inputs, and immutable local image IDs in
ignored `generated/<name>.json`. The build fails if source inputs change while
the two images are being built.
Deployment uses those IDs, waits for container health, then runs the complete
synthetic workflow smoke. `current.json`/`previous.json` move only after smoke
succeeds. Rollback restores the previous image pair and reruns the workflow;
it never rolls SQL backward or replaces persistent volumes. Repeated builds of
identical source with distinct release labels exercise image selection and
process replacement only; they do not prove compatibility between different
application revisions. Record that limitation if used for a rehearsal.

The API applies centrally ordered Flyway migrations during startup. Each
candidate must remain compatible with the previous application image while its
migrations are present (expand/contract). A destructive migration invalidates
an image-only rollback; do not rely on this script to make it safe. On a failed
health or smoke gate the deployment command exits nonzero and leaves the
observed containers available for diagnosis; no success pointer is written.
Redeploy the last known manifest explicitly after diagnosing the failure.

When the monitoring overlay is available, use
`node scripts/release.mjs deploy release-b --observability`. The selected overlay
is retained in deployment history and restored with the previous image pair
during rollback. Overlay-free deployment does not remove existing monitoring
containers or their retained data. See `compose.observability.yaml` for its
separate local ports and documented limits.

| Purpose | Host URL | Container address |
| --- | --- | --- |
| Web and API | `http://127.0.0.1:18080` | `api:8080` |
| OIDC | `http://127.0.0.1:18180/realms/caseflow` | `keycloak:8080` |
| Signed DOCX download | `http://127.0.0.1:18333` | `object-store:8333` |
| Worker operations | `http://127.0.0.1:18090/health` | `worker:8090` |
| API management | `http://127.0.0.1:18081` | `api:9091` |

The browser has the public OIDC URL compiled by Vite. Java validates that exact
issuer but obtains verification keys through the internal JWKS URL. API S3
reads use the internal endpoint; the signer uses the public endpoint so a host
browser can download the resulting URL without rewriting a signed hostname.
Only known SPA paths and static assets are public; `/api/v1/**` still requires
a bearer token except the health check. Worker operational routes are local
ports and must not be exposed as public cloud application routes.

Generated credentials, realm fixtures, template and smoke IDs live under ignored
`infrastructure/release/generated/`. Initialization preserves existing secrets.
It never copies the development `.env` or a provider API key. No live model call
is authorized by this profile, and it does not establish a new AI budget.
The synthetic browser password is `DEMO_PASSWORD` in that generated `.env`;
identities are `requester`, `manager`, `finance`, `admin`, `auditor`, `outsider`.

`scripts/smoke-release.mjs` checks packaged routes, API/operations denial,
Authorization Code + PKCE sign-in, role setup, template publication, two human
approvals, Kafka/worker completion, cross-tenant denial and a signed DOCX
download whose bytes match SHA-256/size and whose parsed content is correct.
On subsequent runs it also verifies the preceding approved case and selected
artifact survived deployment.
It adds synthetic cases each run; it does not delete or reset data. It can be
rerun directly after deployment.

`stop` retains all data. For container removal while preserving data, use
Compose `down` with the same release project/environment and the current image
IDs. Never add `--volumes` casually: that deletes the release database, identity,
broker and object data. No supplied script performs volume deletion.

## Base image provenance

Resolved using `docker buildx imagetools inspect <tag>` on 2026-09-17; the
Dockerfiles pin both the version tag and multi-platform index digest.

| Stage | Official version | Compatibility |
| --- | --- | --- |
| Web builder | Node `22.23.2-bookworm-slim` | Web package requires Node `>=22.12.0 <23` |
| API builder | Eclipse Temurin `21.0.12_8-jdk-noble` | Java 21 toolchain and checked Gradle Wrapper |
| API runtime | Eclipse Temurin `21.0.12_8-jre-noble` | Runs the Java 21 executable Spring Boot jar |
| Worker | Python `3.12.14-slim-bookworm` | Plan pins Python 3.12; Linux wheels installed from requirements lock |

Primary sources: [Node official image](https://hub.docker.com/_/node),
[Eclipse Temurin official image](https://hub.docker.com/_/eclipse-temurin),
[Python official image](https://hub.docker.com/_/python),
[Compose health-gated startup](https://docs.docker.com/compose/how-tos/startup-order/),
[Docker build best practices](https://docs.docker.com/build/building/best-practices/).
Dependency services reuse the digest pins already verified in `compose.yaml`.
These pins make inputs identifiable; they still require periodic review and
security updates. Lockfiles fix dependency versions; they do not establish
byte-for-byte reproducibility of all package repository responses.

No AWS account, IAM credentials, TLS domain or paid resource is required here.
Real ECR/ECS/RDS/S3/ALB deployment, cloud smoke, cloud rollback and teardown
remain separate acceptance gates with account, region, identity and spending
prerequisites.
