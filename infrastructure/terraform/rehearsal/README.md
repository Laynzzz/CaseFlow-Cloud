# AWS rehearsal scaffold

Implemented source; **offline validation plus read-only AWS preflight**. The
limited `caseflow-rehearsal` profile is signed in as `caseflow-operator`; account
plan, quotas, regional offerings and domain DNS were checked. No account-backed
Terraform plan was run and no resource was created. Successful
`validate` or mocked tests do not establish deployability, quotas, engine/AMI
availability, permissions, health or cloud acceptance. See
[ADR 0007](../../../docs/adr/0007-cloud-rehearsal-profile.md) and the
[cost proposal](../../../docs/aws-deployment-proposal.md).

## Local verification (no AWS account)

From repository root, these commands download the pinned provider and check
syntax/schema and plan-level invariants using Terraform's mock provider:

```text
terraform -chdir=infrastructure/terraform/rehearsal init -backend=false -input=false
terraform -chdir=infrastructure/terraform/rehearsal fmt -check
terraform -chdir=infrastructure/terraform/rehearsal validate
terraform -chdir=infrastructure/terraform/rehearsal test
```

Terraform 1.16.2 and AWS provider 6.62.0 were used. Commit the provider lock;
the `.terraform` cache, state, saved plans, backend configuration and real
variable files are ignored. `example.tfvars` deliberately contains invalid
account/AMI/image placeholders; it cannot authorize or accidentally launch a
deployment. The tests use fake account IDs and images and issue no AWS API calls.

The public RDS `us-east-1` CA bundle was fetched 2026-09-17 from
[AWS regional truststore](https://truststore.pki.rds.amazonaws.com/us-east-1/us-east-1-bundle.pem),
SHA-256 `b1711d12bae51838581281e23b6cb97b1074016873b4dafc80ed14002462dd77`.
It contains public certificates, not credentials. The ECS certificate init
container writes it into an ephemeral shared volume; Java and Python use
`verify-full` and mount it read-only. Update/review the bundle before CA rotation.

## Account and remote-state prerequisites

Current onboarding uses AWS CLI 2.36.48 browser-based `aws login` with an IAM
user, not an IAM Identity Center session. It has `ReadOnlyAccess`,
`SignInLocalDevelopmentAccess` and `IAMUserChangePassword`; it cannot provision
this stack. The user completed:

```text
aws login --profile caseflow-rehearsal --region us-east-1
aws sts get-caller-identity --profile caseflow-rehearsal
```

Require the expected `user/caseflow-operator` identity, never a root session.
Do not print/export cached credentials. SSO commands below are an alternative
for an existing SSO environment, not an instruction to enable Organizations
on this Free account. See [ADR 0008](../../../docs/adr/0008-free-plan-rehearsal-sizing.md)
for the revised `db.t4g.micro` / `m7i-flex.large` instance selections.

Before the account-backed phase, select the authorized AWS account/SSO role,
region, explicit cloud spending/session limit and application/authentication
DNS names. This profile expects an existing controlled Route 53 public hosted
zone and two distinct hostnames in it. External DNS or a different OIDC provider
requires a reviewed configuration change, not pasted credentials. Verify a
regional AL2023 x86_64 AMI and exact PostgreSQL 18 minor/instance availability.
AWS account verification is a future command after authorization:

```text
aws sso login --profile caseflow-rehearsal
aws sts get-caller-identity --profile caseflow-rehearsal
aws rds describe-db-engine-versions --engine postgres --engine-version 18.6 --region us-east-1 --profile caseflow-rehearsal
```

An authorized administrator separately creates an encrypted S3 state bucket
with versioning and public access blocked, and grants the deployment role
state/object-lock access plus the reviewed infrastructure permissions. The
backend uses native S3 lockfiles (`use_lockfile=true`). Keep the state bucket
outside this rehearsal root so teardown cannot remove it. Copy
`backend.hcl.example` to ignored `generated/backend.hcl`, supply its real bucket,
and initialize with `init -reconfigure -backend-config=generated/backend.hcl`.
Set `AWS_PROFILE` in the process, not a committed file; the provider refuses
an account different from `account_id`. Do not enable Terraform debug logs
around credential operations.

## Deployment sequence (not executed)

1. Copy `example.tfvars` into ignored `terraform.tfvars`, replace every
   placeholder and set expiry/session metadata. Keep `enable_services=false`
   and `deletion_protection=true`. Build the cloud API with
   `--build-arg VITE_OIDC_URL=https://<auth-hostname>`; the browser issuer is a
   build input, while API issuer/JWKS are runtime values. Images must be pushed
   under the authorized account's private ECR digest references.
2. Registry bootstrap is the one deliberate staged-target exception:
   `terraform plan -target=aws_ecr_repository.app -out=generated/registry.tfplan`.
   Review that only the two intended empty repositories are created, then
   apply the reviewed saved plan. Valid digest-shaped provisional image inputs
   are needed for Terraform variable validation but no task starts at this
   stage. Push both images using the normal `aws ecr get-login-password` pipe
   to `docker login --password-stdin`; never print or save the token. Set the
   resulting actual `repository@sha256:...` inputs before the full plan.
3. `terraform plan -out=generated/rehearsal.tfplan`; inspect account, region,
   size, public rules, no existing-resource replacement and estimated cost.
   After the separate cloud authorization, apply that exact plan. This creates
   RDS, empty secret containers and tasks with **desired count zero**. The
   auxiliary VM retries safely until the secret bootstrap completes.
4. Start the one-off bootstrap task. The PowerShell example below builds JSON
   network input without putting secret values into command arguments:

```powershell
$tfDirectory = 'infrastructure/terraform/rehearsal'
$clusterName = terraform "-chdir=$tfDirectory" output -raw cluster
$bootstrapDefinition = terraform "-chdir=$tfDirectory" output -raw bootstrap_task_definition
terraform "-chdir=$tfDirectory" output -json network_configuration | Set-Content -Encoding utf8NoBOM "$tfDirectory/generated/network.json"
aws ecs run-task --cluster $clusterName --task-definition $bootstrapDefinition --launch-type FARGATE --network-configuration "file://$tfDirectory/generated/network.json" --region us-east-1
```

   Capture the returned task ARN, use `aws ecs wait tasks-stopped`, then
   `aws ecs describe-tasks` and require bootstrap container exit code zero and
   no ECS `failures`. Inspect its CloudWatch log for the completion message.
   Bootstrap reads the RDS-managed master secret, generates stable secret
   values when absent, creates database roles/grants and stores the synthetic
   OIDC realm. It never writes credentials to Terraform state or emits them.
   Reruns preserve stored passwords. Concurrent bootstrap tasks are unsupported;
   run only one. No API schema migration is claimed at this step.
5. The auxiliary systemd service mounts only the volume whose serial matches
   the newly provisioned EBS ID. It formats that disk only if no filesystem
   exists, retains it across VM replacement, and gates Docker on the data mount
   after reboot. It starts the pinned broker, production-mode Keycloak and
   private monitoring. Require SSM/log inspection and the HTTPS OIDC discovery
   endpoint to be healthy before enabling application tasks. The Keycloak
   admin console is not routed by public ALB; synthetic credentials are fetched
   only through an authorized private operations workflow.
6. Set `enable_services=true`, review/apply the new plan, then wait for both
   ECS services to stabilize and the ALB API target to become healthy. API
   startup runs forward Flyway migrations. Worker execution can retry until
   schema/broker readiness, but full workflow smoke is still mandatory.
7. Run the synthetic browser journey at the real HTTPS origin, then role and
   tenant denial, two approvals, actual S3 DOCX download/checksum, manual AI
   fallback, and a trace lookup through private monitoring. Existing local
   smoke runner accepts an explicit configuration: copy `smoke.example.json`
   into the ignored `generated` directory and supply the exact HTTPS application,
   issuer and bucket origins plus an immutable local worker helper image ID.
   Save the synthetic `DEMO_PASSWORD` locally in ignored `.env.cloud-smoke` using
   the authorized Secrets Manager session; never paste it into chat or logs.
   Run `node scripts/smoke-release.mjs infrastructure/terraform/rehearsal/generated/smoke.json`.
   It creates only synthetic purchase fixtures, exercises PKCE and approvals,
   checks tenant denial and verifies the downloaded DOCX. The helper image runs
   locally with no network/capabilities to generate/check DOCX bytes; it does not
   execute inside ECS. Private worker health must be checked separately through
   ECS and private operations access. Both default and configured runner paths
   passed locally; HTTPS/AWS execution is **unverified**. Record exact image digests and migration
   checksums with raw output and limitations.

The API currently receives migrator credentials during startup, matching the
existing application-owned Flyway arrangement; moving migrations into a
separate cloud task is a future least-privilege refinement. No hosted AI key
is injected by this profile. Do not create a second independent paid-AI ledger.

Application, certificate-init and bootstrap containers drop all Linux capabilities.
The worker IAM role additionally permits prefix-constrained document listing and
deletion for the manual orphan-cleanup command; it cannot delete templates or
source uploads. Selected-object safety still depends on the command's locked
database checks and conditional deletion. Versioned S3 deletion retains old
versions and may incur ongoing storage costs; it does not purge object history.
The current worker image has expiring reviewed OS findings; recheck the
[scan policy](../../../docs/runbooks/ci.md) and actual cloud runtime assumptions
before accepting a cloud deployment. Offline Terraform tests are not that proof.

## Rollback and teardown (not executed)

Save the prior API/worker digest pair and task definition revisions before
updating. Apply only backward-compatible migrations, deploy candidate digests,
wait for ECS/ALB health, and run the complete smoke. Restore the prior digest
pair through a reviewed plan, re-run smoke and verify that the previously
approved case and selected object checksum are unchanged. Do not down-migrate
SQL or restore an older database snapshot as an image rollback shortcut.
ECS deployment circuit breaking catches health failure; it does not replace
workflow smoke or prove schema compatibility.

First set `enable_services=false` to stop Fargate work. Inspect a destroy plan
for the compute/edge resources only, including their dependencies, before
applying it. The persistent RDS instance, S3 bucket, secrets and EBS disk are
protected: a blanket `terraform destroy` is expected to fail until an explicit
data-retention decision changes the lifecycle guards. Disable ALB provider
deletion protection in a reviewed update before deleting it.

For a fully synthetic teardown, explicitly approve which database/object/broker
data may be deleted, select a uniquely named final database snapshot, remove
only those lifecycle guards, and review the complete saved destroy plan. Never
set S3 `force_destroy=true` or bypass retained state as a convenience. Object
versions and delete markers require an explicit inventory and deletion scope.
If data is retained instead, list the still-billable RDS instance/storage,
snapshots, S3 versions, encrypted EBS, ECR images, Secrets Manager records,
CloudWatch logs, DNS and remote-state bucket. Do not call stopped tasks a full
teardown. Record follow-up inventory and costs; budget alerts do not cap them.

Known unverified cloud details: account IAM/SCP/quota behavior, regional image
and PostgreSQL availability, bootstrap SQL privileges on actual RDS, EC2 package
installation/EBS device discovery, Keycloak proxy/realm readiness, private DNS
registration, task/init-volume permissions, S3 compatibility, trace export,
health-gated rollout, rollback, billing and final resource inventory. Offline
validation proves none of these cloud behaviors.
