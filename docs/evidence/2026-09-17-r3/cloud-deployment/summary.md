# Cloud deployment session

Session started September 17, 2026 local time (September 18 UTC). Actual HTTPS
deployment, workflow/browser checks, candidate rollout and prior-image rollback
and teardown have passed. Final inventory: September 18 at 01:41:56 UTC.
The chronological checkpoints below retain failures and evidence boundaries;
the [R3 acceptance record](../r3-acceptance.md) states the final release decision.

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

## Candidate rollout and prior-image rollback

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


Both candidate services reached `COMPLETED`, with one running task each. The
candidate smoke passed and preserved the baseline purchase. The API candidate
was built from `8e61fe1` plus the uncommitted metrics-export setting, subsequently
committed in `a795184`; its image revision label `8e61fe1-cloud-metrics-fix` is a
build label, not a clean Git commit. `candidate-image.json` pins the actual ECR
index digest. The worker image was unchanged.

`trace-verification.json` and `actual-trace.json` record 13 spans across Java and
Python, including API publish, worker schedule/execute/publish and API completion.
Cross-service parent IDs and exported metadata allowlists passed. Direct lookup
by trace ID succeeded after a search returned no worker results; the reason for
the empty search is unproven. All three private Prometheus targets were healthy.
`candidate-log-check.json` records the checked window without the baseline's
redundant automatic OTLP metrics-export warnings.

The rollback restored the original API/worker digests and 0.1 trace sampling.
Both services again reached `COMPLETED` (`rollback-services.json`). The complete
smoke passed (`rollback-smoke.txt`), and separate post-rollback checks downloaded
and rehashed the baseline, candidate and browser documents. All three approved
records and checksums were preserved (`rollback-preservation.json`). This cloud
candidate changed configuration, not schema; additive V14 migration compatibility
has separate [local rollback evidence](../monitoring-recovery/summary.md).

A read-only one-off task verified all 14 successful Flyway migrations and a TLS
1.3 connection to RDS (`database-readback.json`). Its first attempt failed because
`rds.force_ssl` is an RDS parameter-group setting, not a runtime PostgreSQL `SHOW`
parameter. The corrected readback exited zero. No database state was changed by
this check. RDS API readback separately reported `rds.force_ssl=1`.


## Completed teardown and cost record

The API/worker services first reached desired/running/pending counts of zero.
All observed tasks then reached STOPPED; an early strict check waited for the
last task to finish stopping before deleting any objects. Inventory recorded
seven versions belonging to the one synthetic tenant and the exact two ECR
repositories. Deleted those versions and image manifests, verified the containers
empty, and retained the inventory (`pre-delete-inventory.json`).

The reviewed stop plan disabled RDS/ALB deletion protection. Only the four
persistent-resource lifecycle guards were temporarily relaxed to create the
saved destroy plan, then the original protected source files were restored.
The saved plan contained only deletion actions for 82 workload resources, with
the external public DNS zone and state bucket excluded. Its successful apply
is in `teardown-apply.txt`; no `force_destroy`/`force_delete` shortcut was used.

RDS created the explicitly scoped final synthetic snapshot. It did not exist
before this session. Its creation timestamp changed between creating/available
readbacks; a strict equality guard stopped the first deletion attempt. Rechecked
the exact source database resource ID and completed snapshot timestamp before
deleting it. `snapshot-deletion.json` records that deletion; final AWS readback
found no database, snapshots or retained automated backups.

`teardown-inventory.json` verifies empty Terraform managed state and absence of
workload compute, EBS, VPC/network interfaces, ALB, active ECS services/tasks,
application bucket, ECR repositories, private namespace, logs and certificate.
Both the initial failed and repaired EC2 instances are terminated. The RDS-owned
master secret disappeared. Seven runtime secrets remain marked for deletion
under the configured recovery window.

Intentionally retained: the public DNS zone (NS/SOA only), protected state bucket
(46 versions, 3,606,687 bytes), seven task-definition revisions, three owner-created
access policies/operator access and account-managed service-linked roles. The
first task-definition inventory used a partial family argument and returned no
matches; the corrected full-list filter verifies all seven retained definitions.
This is why API inventory was checked separately from Terraform's empty state.

Cloud work ran about 64 minutes from full apply to final inventory. Estimated
session cost is USD 1–2 with overhead reserve, **not a measured bill**. AWS still
reports ACTIVE/FREE; account credits increased from USD 100 to USD 140, so their
difference is not a project cost. The authorization remains USD 10. Retained DNS
is about USD 0.50/month plus queries; protected state adds small storage/request
charges. See `final-cost-readback.json` and the [credit ledger](../../../aws-credit-ledger.md).
No hosted-AI calls occurred and no paid-plan upgrade was made.

The AWS app is intentionally offline after this bounded rehearsal. Local preview
and release volumes were left intact. Future deployment must republish images,
refresh expiry/configuration, handle pending-deletion secret names, recheck
credits and rerun current scan gates. No always-on hosting is claimed.


## Reproduction and final verification

Use the [AWS runbook](../../../../infrastructure/terraform/rehearsal/README.md)
for prerequisites, secret bootstrap and health gates. This session used Windows,
PowerShell, Terraform 1.16.2, AWS provider 6.62.0, Docker 29.0.1 and Node 22.20.0.
The baseline source was `50decb5`; fixes and the candidate provenance are recorded
above. Account identifiers are redacted; generated plans/credentials stay ignored.
Representative commands actually used, from the repository root:

```powershell
$env:AWS_PROFILE = 'caseflow-rehearsal'
terraform '-chdir=infrastructure/terraform/rehearsal' validate -no-color
terraform '-chdir=infrastructure/terraform/rehearsal' test -no-color '-var=enable_services=false'
node scripts/smoke-release.mjs infrastructure/terraform/rehearsal/generated/smoke.json
terraform '-chdir=infrastructure/terraform/rehearsal' apply -input=false -no-color generated/rollback.tfplan
terraform '-chdir=infrastructure/terraform/rehearsal' apply -input=false -no-color generated/destroy.tfplan
terraform '-chdir=infrastructure/terraform/rehearsal' state list
```

Saved plans were individually inspected before execution; their names are not
standalone deploy/destroy recipes. Smoke used the exact HTTPS application, issuer
and S3 bucket origins plus an ignored synthetic credentials file. Final readbacks
used AWS ECS/RDS/EC2/ELB/S3/ECR/Route 53/Secrets Manager APIs to check owned resources,
not just Terraform output. The runbook explains prerequisites for a new session.

After restoring protected defaults, format/validation and two mocked tests pass.
The recorded Cloud Map deprecation warning remains. The initial final format
check found only formatting in ignored local tfvars; formatting that file fixed
it. Documentation link/hash checks and a targeted final secret scan passed.
The local preview responds HTTP 200, and `/api/v1/health` reports API/database UP.
See `final-verification.json`; previous full test/image scan evidence remains
bound to its recorded images and is not presented as rerun by a documentation check.
