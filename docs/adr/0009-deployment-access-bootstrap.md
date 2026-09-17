# ADR 0009: owner bootstrap and bounded application-role delegation

Status: implemented and checked offline/read-only, 2026-09-17. User execution
and actual IAM grants are pending. User authorized USD 10 of existing AWS
credits, with the Free account plan retained.

Keep the CLI operator separate from the account owner. The current
`caseflow-operator` can inspect AWS but cannot deploy. The account owner runs
the reviewed `aws_access.py` once in CloudShell to create three managed IAM
policies and attach two to that operator. It makes no account-plan changes,
creates no access keys and launches no workloads. Terraform then uses temporary
operator login credentials for ordinary provisioning.

The deployment policies enumerate infrastructure writes, constrain regional
services to us-east-1, and narrow S3/ECR/RDS/secrets/logs/ECS and IAM resources by
project name where implemented. Only the five exact runtime role names may be
created or passed to ECS/EC2. Creating those roles requires the owner-created
runtime permissions boundary; Terraform sets it on all five roles. The operator
cannot edit that boundary policy, remove a role boundary or grant itself other
IAM user policies. Managed role attachments are restricted to the ECS execution
and SSM core policies. Paid-plan upgrade and Organizations actions are denied.

Before any grant, bootstrap checks the account, active Free plan, exact user,
required baseline read/sign-in policies, absence of unexpected user policies,
groups or user boundary, reserved role boundaries and instance-profile members.
It refuses policy-name collisions whose documents differ. Every preflight
completes before the first write. IAM calls are not transactional: a network or
permission failure during writes can leave some policies present; a same-source
rerun checks their exact documents and finishes missing attachments. Concurrent
administrative edits to these reserved names are unsupported; run bootstrap
and deployment as a single supervised session.

This is service-scoped deployment access, not complete resource isolation.
Selected EC2 network/disk writes, ALB, ACM and Cloud Map writes cover the region;
Route 53 writes cover the account's zones. Creation APIs and generated resource
IDs complicate stronger tagging policies. The operator is privileged within
those scopes. Name-scoped secret access includes the project's synthetic demo
credentials; the shared runtime boundary also permits RDS-managed secret reads
and SSM agent actions, while the narrower per-role policies enforce the actual
runtime access. A shared/production account would need stricter tags, boundaries
and separate administrator review. It is not safe to call this a general-purpose
least-privilege deployment policy.

The alternative of attaching AdministratorAccess is unnecessary. Manual creation
of every role avoids delegated IAM but adds setup drift and many user steps.
An existing federated admin environment is preferable when available; creating
Organizations just for this Free account could change its billing plan.

The runtime ceiling explicitly includes decrypt/data-key operations only through
Secrets Manager in this account/region and for alias/aws/secretsmanager. It
does not grant direct KMS or arbitrary customer-key use through that statement.
This avoids relying on subtle AWS-managed key policy/boundary interactions;
it is not evidence that the previous omission caused an observed runtime failure.

Validation: 13 offline bootstrap/policy checks, two mocked Terraform plans,
AWS Access Analyzer ValidatePolicy and selected IAM custom-policy simulations.
These do not prove every runtime request or protection against concurrent owner
changes. Actual resource creation remains the next evidence stage.

Implementation and removal instructions: [ACCESS.md](../../infrastructure/terraform/rehearsal/ACCESS.md).
