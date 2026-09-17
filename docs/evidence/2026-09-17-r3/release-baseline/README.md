# Local release packaging evidence

Environment: Windows host, Docker Desktop Linux containers, Docker Engine
29.0.1. Synthetic local data only; isolated Compose project `caseflow-release`.
Recorded 2026-09-17. No cloud provisioning or paid AI request was performed.

## Baseline actually verified

- `services/worker/Dockerfile` built successfully from pinned Python 3.12.14.
  All pinned requirements installed; `pip check` reported no broken requirements.
  A separate `docker run --read-only --tmpfs /tmp:rw,noexec,nosuid,size=256m`
  generated a DOCX as UID 10001.
- `services/case-api/Dockerfile --target build` built the packaged React app
  (`npm ci`, TypeScript check, Vite build) and executable Java 21 jar using the
  checked Gradle Wrapper. The baseline runtime was derived from that exact
  builder snapshot before telemetry source changes.
- `node scripts/release.mjs deploy release-baseline` created fresh isolated
  data volumes, waited for readiness and passed the full release smoke. Raw
  output is [baseline-deploy.txt](baseline-deploy.txt).
- `node scripts/smoke-release.mjs` passed again, including preservation of the
  previous approved case. Raw output is
  [baseline-repeat-smoke.txt](baseline-repeat-smoke.txt).
- Three focused Java tests passed: `WebSecurityTest` and both
  `ObjectStoragePublicEndpointTest` cases. They enforce public known SPA reads,
  API/operational route denial, and correct public signed-download hostname.

Exact baseline image IDs, builder snapshot ID, source parent revision, dirty
state and limitations are in [baseline-manifest.json](baseline-manifest.json).
The builder's actual packaged Java source, configuration, migrations and built
static files are identified by
[baseline-packaged-source-hashes.txt](baseline-packaged-source-hashes.txt).
The API baseline includes new telemetry dependencies but predates telemetry
source/configuration; the worker baseline predates telemetry dependencies.
Do not label this dirty snapshot as a clean commit deployment.

Candidate deployment, executed rollback and final monitoring/load evidence
must be recorded separately before claiming those gates. Successful local
packaging does not satisfy AWS deployment, cloud smoke, cloud rollback or
teardown requirements in `plan.md`.
