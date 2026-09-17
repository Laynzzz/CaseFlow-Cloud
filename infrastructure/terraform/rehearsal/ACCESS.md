# One-time AWS deployment access

Prepared 2026-09-17. The user authorized USD 10 of existing AWS credits and the
account must remain on Free. This setup grants permissions only; it does not
start the deployment or consume a new AI allowance.

## What the owner runs

Upload `aws_access.py` from this directory into the account owner's AWS
CloudShell. Use the expected account's console and us-east-1. CloudShell is an
AWS-hosted terminal with Python and AWS CLI already installed; no passwords or
access keys need to be copied into this repository or chat.

```text
python3 aws_access.py --account YOUR_12_DIGIT_ACCOUNT_ID
python3 aws_access.py --account YOUR_12_DIGIT_ACCOUNT_ID --apply
```

The first command is an account-backed, read-only preview. The second creates
the three policies described below and attaches the two deployment policies to
`caseflow-operator`. The account owner is needed because the operator cannot
grant itself access. This exceptional owner action is IAM bootstrap only;
routine local deployment must continue under the operator, never a root CLI
profile. Afterward, sign out of the owner console session and return to the
operator. Keep the local AWS CLI profile as `caseflow-rehearsal`.

Expected success: `CaseFlow deployment access configured. No workloads or
access keys created.` On an error, preserve the error and report it; do not
attach AdministratorAccess or change to Paid to work around it.

## Reviewable scope

| Policy | Purpose | Attached to operator? |
| --- | --- | --- |
| caseflow-access-infrastructure | Selected regional EC2, ECS, ECR, RDS, ALB, ACM, Cloud Map and logs operations | Yes |
| caseflow-access-identity-storage | Five bounded runtime roles, project buckets/secrets, DNS and tagged-host operations; denies Paid upgrade and Organizations | Yes |
| caseflow-access-runtime-boundary | Maximum permissions allowed to runtime roles | No; Terraform places it on each runtime role |

Existing ReadOnlyAccess and SignInLocalDevelopmentAccess remain. Permission to
change the operator's own password may also remain. The new policies cannot
create access keys, change user credentials, attach arbitrary role policies,
remove role boundaries or modify their own managed policy versions. Only the
five named application roles can be passed to ECS/EC2. Existing unbounded roles
with those names, unrelated instance-profile members and differing existing
policy documents stop bootstrap before any writes.

The operator has substantial deployment authority: selected EC2/ALB/ACM/Cloud
Map operations are region-wide, and Route 53 writes are account-wide. This is
not complete resource isolation. Only use it in this supervised learning account;
do not claim a production least-privilege review. IAM resource boundaries and
the narrower runtime role policies are separate layers. See
[ADR 0009](../../../docs/adr/0009-deployment-access-bootstrap.md).

Render the exact JSON for the account without contacting AWS:

```text
python aws_access.py --account YOUR_12_DIGIT_ACCOUNT_ID --render-dir generated/access
```

Review the three files before upload/run. Each is below the 6,144-character
managed-policy limit. The script uses only the Python standard library and the
AWS CLI; no remote script download or package installation occurs.

## What happens next

After the owner grants access, the operator can create a protected Terraform
state bucket and a Route 53 public zone for the purchased domain. The owner
then copies the four generated nameservers into Porkbun; the specific values
do not exist yet. Check public DNS delegation before requesting certificates.
Do not replace nameservers with example values or delete the domain registration.

Review an actual Terraform plan before applying it. Keep services at zero until
bootstrap/identity readiness passes. Provisioning consumes the existing USD 10
credit allowance; the scope is the short rehearsal, rollback and cleanup, with
retained storage/DNS recorded. Do not upgrade the account if a service is blocked.

## Removing temporary deployment access

After cloud cleanup and resource inventory, the owner detaches the two policies:

```text
aws iam detach-user-policy --user-name caseflow-operator --policy-arn arn:aws:iam::YOUR_12_DIGIT_ACCOUNT_ID:policy/caseflow-access-infrastructure
aws iam detach-user-policy --user-name caseflow-operator --policy-arn arn:aws:iam::YOUR_12_DIGIT_ACCOUNT_ID:policy/caseflow-access-identity-storage
```

Remove the now-unused managed policies only after checking attachments and any
retained runtime roles. Removing IAM access does not stop billable resources.
Keep enough access to inventory and remove them before revoking deployment
rights. The remaining read-only/sign-in permissions can be retained for learning.

## Evidence limits

Offline tests cover preflight failure before writes, missing baseline access,
existing-policy/role/profile collisions, policy scope/size and preview mode.
Terraform tests require the boundary on all five roles. AWS policy validation
and selected simulator cases were read-only; neither is proof of deployment.
The default preview also passed against the real limited account. No IAM grants
have been performed by the agent.

Official references: [CloudShell upload/run](https://docs.aws.amazon.com/cloudshell/latest/userguide/getting-started.html),
[IAM boundaries](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_boundaries.html),
[EC2 instance-size permissions](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ExamplePolicies_EC2.html#iam-example-instance-types).
