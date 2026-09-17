# R3 completion execution plan

Basis: `plan.md` sections 10, 14–20; user authorization to continue until R3 is
finished or a real user dependency remains. Build first; maintain teaching and
interview notes. No cloud provisioning or additional AI spending is authorized.

R2 remains a local experimental AI release: extraction missed its frozen target;
AI grading is not independent human review. Local verification never substitutes
for the plan's AWS deployment gate.

## Ordered work and gates

- [ ] Finish the four redacted dead-letter process-crash cases, preserving actual
  source coordinates, broker acknowledgements and business-effect invariants.
- [ ] Add bounded operational metrics and OpenTelemetry propagation through Java
  outbox → Kafka → durable Python job → completion outbox → Java. Preserve all
  transaction/acknowledgement/fencing boundaries. Verify metadata-only telemetry,
  disconnected export, durable context and private management endpoints.
- [ ] Package immutable Java/frontend and worker images in an isolated release
  Compose project. Verify empty-schema startup, OIDC/PKCE, full manual approval,
  immutable DOCX download and another tenant's denial. No live AI calls required.
- [ ] Provision local collector/trace/metric backends and dashboard/alerts. Export
  a correlated trace; diagnose one controlled failure and record restoration.
- [ ] Run the bounded k6 workload after warmup; publish offered/completed/dropped
  work, HTTP latency separately from job latency, backlog/drain and saturation.
  Record exact revision, images, workload, environment and limitations.
- [ ] Exercise packaged-service recovery and prior-image rollback with compatible
  migrations; preserve failed runs and all relevant checksums.
- [ ] Add repeatable CI gates, dependency/secret/container checks, declared critical
  module coverage and Terraform validation. Run locally where credentials permit;
  distinguish local validation from hosted CI evidence.
- [ ] Prepare Terraform, networking/identity/messaging decisions, current AWS cost
  estimate and exact deploy/smoke/rollback/teardown instructions. Before provisioning,
  obtain account availability, region, identity prerequisites and cost authorization.
- [ ] Execute cloud deployment/rollback/teardown only after prerequisites arrive.
  If blocked, finish all independent local work and report this gate as pending.
- [ ] Verify a clean-checkout synthetic demo; update release statuses, teaching
  guide, interview preparation and claim-to-evidence map. Do not claim R3 complete
  until its required gates have actual evidence.

## Execution controls

Root owns observability, integration, validation and cohesive commits. Existing
bounded agents own dead-letter probes, release packaging and load harness. Heavy
database suites run serially; image builds coordinate dependency changes. Runtime
experiments target isolated owned resources, never stop the user's existing demo.

Instrumentation uses bounded operation/kind/state labels; tenant/case/job IDs may
appear in scoped traces/logs but never metric labels. No tokens, credentials,
purchase text, source passages or model responses enter telemetry. Export is
disabled unless configured. Bounded trace evidence uses full sampling; ordinary
load/cloud defaults to parent-based 10% sampling.

Worker queue latency means time from `available_at` to claim, excluding deliberate
retry backoff. Execution duration covers execution and result persistence. User
completion latency is measured separately by the authenticated load client. An
unavailable metrics database must produce an unhealthy collector signal, not a
fabricated healthy zero backlog.

Every checked gate links to evidence in `docs/r3-status.md` and
`docs/evidence-index.md`. Incremental commits contain verified cohesive changes;
no credentials, raw token-bearing traces or unrelated changes are staged.
