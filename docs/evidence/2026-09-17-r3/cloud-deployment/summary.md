# Cloud deployment session

Session started September 17, 2026 local time (September 18 UTC). In progress:
this evidence is not a completed cloud acceptance or rollback claim.

## Verified before application provisioning

- Google public DNS returned all four assigned AWS nameservers after the user
  changed Porkbun delegation. Another resolver still had the old cached answer.
- Images were built from source revision `50decb5`. The Java/frontend build used
  `VITE_OIDC_URL=https://auth.laynexia.com`; the worker used the pinned Dockerfile.
  Both builds succeeded and both tagged images were pushed to private ECR.
  Registry readback supplied the real immutable digests in the deployment plan.
- Fresh secret, dependency and image checks passed the existing scan policy.
  API: no HIGH/CRITICAL findings. Worker: existing exact-version, expiring reviewed
  exceptions remain; acceptance does not mean zero vulnerabilities.
- The full saved Terraform plan contained 80 creates, two expiry-tag updates,
  no replacements or deletes. Reviewed invariants: private encrypted micro RDS,
  the permitted EC2 size, required IMDSv2, boundaries on all five IAM roles,
  only TCP 443 open from the internet, and both application desired counts zero.
- Immediately before apply, AWS reported ACTIVE/FREE with USD 100 credits.
  The estimate remains roughly USD 0.22/hour for the compute/edge subtotal;
  at most four supervised running hours, plus DNS/storage/logs/requests, under
  the previously authorized USD 10 total. USD 1 is reserved for foundation
  overhead. Credit balance is delayed, account-wide evidence, not a hard cap.

The reviewed full plan was applied starting approximately 00:38 UTC. ACM DNS
validation succeeded and the certificate was issued. RDS and ALB creation were
still in progress at this checkpoint. No completed workflow, running application,
cloud rollback, or cleanup is claimed here. This file will be updated with actual
outcomes and retained resources as the session progresses.

## First apply and diagnosed startup repair

The full apply succeeded. The one-off ECS bootstrap stopped with exit zero and
logged successful role grants and synthetic-realm storage; see
`bootstrap-result.json`. This exercises real RDS/Secrets Manager task access.

The first EC2 cloud-init failed before Docker installation: `awscli2` is not an
AL2023 package. Private SSM inspection confirmed the installed package is
`awscli-2`. Corrected the template and replaced only the uninitialized VM plus
its attachment/target wiring; the database and 30 GiB retained disk were preserved.
The replacement successfully installed Docker, mounted the correct data volume
and began starting the pinned supporting containers.

The follow-up plan also exposed drift hidden by mocked testing: RDS returned
`rds.force_ssl` with `pending-reboot`, ECS materialized empty added-capability
lists and explicit TCP/host ports, and an empty Cloud Map health block was not
retained. Made those settings explicit. The Cloud Map change replaced the two
discovery registrations and updated the two stopped ECS services. No business
data or running application task was removed. Two Terraform tests pass and the
subsequent real full plan has **zero changes**. Cloud Map's explicit threshold
produces a provider deprecation warning (AWS fixes the value to one); recorded
for migration when the pinned provider removes this argument.

Actual HTTPS OIDC readiness and application workflow remain pending. A first
request during Keycloak startup returned 502; this is not a passed health gate.

## Baseline cloud workflow and browser gate

Subsequent HTTPS OIDC discovery passed. The auxiliary host completed cloud-init;
Kafka, Keycloak, collector, Tempo, Prometheus and Grafana started. The first API
task was replaced during Java startup because ECS's ALB health grace was zero.
An added startup-grace assertion failed, then passed with a 180-second API grace.
The real update changed only that service setting. Both services reached steady
state afterward. Local mocked tests must use `-var=enable_services=false` when
an ignored active-deployment tfvars exists, so that the default-safety test does
not inherit the running session's desired counts.

The initial smoke saw an empty 401 on authenticated `/me` during stabilization;
later attempts passed without an authentication-code change. Root cause of that
transient response is unproven. A subsequent run reached download verification
but rejected the configured S3 hostname: the SDK uses the bucket's global
`s3.amazonaws.com` hostname in us-east-1. Corrected the ignored smoke configuration
to that exact observed bucket origin; did not weaken origin checks.

The original smoke runner then passed HTTPS SPA deep links, PKCE login, operations
and tenant denial, two approvals, Kafka/worker completion, real S3 download,
SHA-256/length and DOCX contents. `baseline-purchase.json` identifies the approved
case and checksum. No live AI calls occurred.

Separately, an actual Playwright browser completed requester draft/assignment/
submission, manager approval and finance approval for a second synthetic USD 4,200
purchase. The UI reported document success; its download produced a DOCX with
the expected vendor and price, no unresolved markers, and recorded checksum.
See `browser-result.json`, screenshot, snapshot and document. The in-app browser
runtime failed initialization; an isolated Playwright CLI browser was used.
Known favicon 401 errors remain, as in the local UI evidence.

Private SSM inspection verified three healthy Prometheus scrape targets, worker
database health, and traces in Tempo. The initial query is in `trace-search.json`;
cross-service trace inspection is a separate pending step.

## Candidate rollout (in progress)

The candidate disables automatic OTLP metrics export in application YAML because
Prometheus already scrapes metrics and the collector accepts only traces. The
baseline was logging 404 responses for redundant metric exports. The exact
Spring Boot 4.1.1 configuration metadata confirmed the property. The candidate
image build and HIGH/CRITICAL scan pass. Business code and V14 schema are unchanged.

The first rollout attempt failed when Terraform tried to deregister the old task
definition: the operator's scoped grant does not authorize this action on `*`.
No permissions were expanded. Configured and first applied `skip_destroy=true`
on the three definitions with baseline images unchanged, retaining immutable
revisions for rollback and explicit teardown inventory. Then replanned candidate
rollout; only API/worker definitions and their services change. Full sampling is
enabled temporarily for the bounded trace test. Rollback restores baseline image
and sampling inputs. Retained definitions do not imply running tasks and must
remain explicitly listed if operator permissions cannot remove them at cleanup.

Files beside this report preserve DNS, published/local image identifiers,
pre-apply cost readback, resource actions and scan decisions. Account identifiers
are consistently replaced by synthetic `123456789012`; real credentials, state,
binary plans and application secrets are excluded.
