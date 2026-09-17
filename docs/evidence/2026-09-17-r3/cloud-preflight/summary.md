# Read-only AWS onboarding and Free-plan sizing

Captured 2026-09-17 with AWS CLI 2.36.48 and the user-established
`caseflow-rehearsal` profile in `us-east-1`. The exact expected IAM user was
checked before discovery; account identifiers are omitted from the archive.
No resources were created, modified or deleted. No account upgrade, deployment,
credential export, paid API inference or cloud release gate is claimed.

## Observations

- `caseflow-operator` has ReadOnlyAccess, SignInLocalDevelopmentAccess and
  IAMUserChangePassword. The preceding root login was replaced by the user.
- Free account plan: ACTIVE, USD 100 remaining credits, expiration reported
  March 17, 2027. This is a snapshot, not a budget reserved for this project.
- Fargate on-demand quota: 6 vCPUs; EC2 standard on-demand quota: 5 vCPUs.
  Proposed two application tasks consume 1 vCPU; auxiliary VM consumes 2.
  Rollout/bootstrap headroom and actual capacity still need cloud verification.
- PostgreSQL 18.6, `db.t4g.micro`, gp3, minimum 20 GiB is regionally orderable,
  including the two configured zones. AWS's RDS Free-plan documentation lists
  micro classes; the original small instance is replaced.
- `m7i-flex.large`: Free Tier eligible in EC2 discovery, x86_64, 2 vCPUs,
  8192 MiB; offered in both configured zones. Actual allocation is unverified.
- Amazon-owned AL2023 image `ami-0e34b50e714a297f1` is available, x86_64,
  name `al2023-ami-2023.12.20260914.0-kernel-6.18-x86_64`. No image was launched.
- `laynexia.com` resolves to four Porkbun nameservers. Route 53 discovery
  returned no hosted zones from that name. Registration is not DNS delegation.
- AWS Price List hourly rates: Linux shared m7i-flex.large USD 0.09576
  (SKU SD5Q9AZVZ786UZA2); Single-AZ PostgreSQL db.t4g.micro USD 0.016
  (SKU 9HPEGXQTDDGH53C9). These are list prices before credits/tax.

## Reproduction and artifacts

`read-only.json` records every CLI argument array, projected response, timestamp,
CLI version and DNS result. Append `--profile caseflow-rehearsal --region
us-east-1 --output json --no-cli-pager` to each recorded argument array when
repeating it. Do not publish full STS identities or credential caches.

`ec2-pricing.json` and `rds-pricing.json` contain public AWS Price List products.
Use `pricing get-products` with regionCode=us-east-1 and the exact instanceType;
EC2 filters: operatingSystem=Linux, tenancy=Shared, preInstalledSw=NA,
capacitystatus=Used. RDS: databaseEngine=PostgreSQL, deploymentOption=Single-AZ.

The Terraform assertion was added before changing sizes and failed with the
original choices (one test passed, one failed). After updating the choices,
`terraform fmt -check`, `validate` and `test` passed (2 tests). Output is in
`terraform-validation.txt`. Mocked tests do not contact AWS or prove runtime
capacity. The initial pricing CLI attempt failed on shell quoting; using JSON
filter files succeeded. No write API was attempted.

Pending: separate credit-usage authorization, scoped deployment permissions,
remote state, DNS zone/delegation, full account-backed plan, runtime service
eligibility, deployment, workflow smoke, rollback and teardown inventory.

Decision: [ADR 0008](../../../adr/0008-free-plan-rehearsal-sizing.md).
Proposal: [short supervised rehearsal](../../../aws-deployment-proposal.md).
