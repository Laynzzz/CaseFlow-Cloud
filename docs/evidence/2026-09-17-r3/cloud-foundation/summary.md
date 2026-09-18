# Actual AWS foundation bootstrap

Executed September 17, 2026 local time (September 18 UTC), within the approved
USD 10 existing-credit allowance. Account remained ACTIVE/FREE and reported
USD 100 before provisioning. The operator was verified as the intended IAM
user; the owner's installed policies matched the reviewed bootstrap source.

Actual resources now retained:

- Public Route 53 zone for `laynexia.com`, creation change INSYNC. Registrar
  delegation remains pending: public resolver 1.1.1.1 still returned Porkbun
  nameservers during this session. Zone creation alone does not establish public
  delegation or certificate validation.
- S3 Terraform state bucket outside the workload stack. Readback verified
  versioning, AES256 encryption, all four public-access blocks, bucket-owner
  enforced ownership and a TLS-only policy. Project/environment tags were set.
- Two empty ECR repositories, `caseflow-rehearsal/api` and
  `caseflow-rehearsal/worker`, with immutable tags and scanning on push.

Terraform 1.16.2 initialized the S3 backend using the existing AWS CLI login
profile directly. No static key export or alternate credential profile was
needed. The documented registry-only target plan contained exactly two creates,
zero updates and zero deletes. Applying the reviewed saved plan succeeded.
S3 readback verified persisted state versions and released lock objects. This
demonstrates backend write/lock/delete access, not concurrent-lock contention.

`verified.json` preserves actual readback responses with the account identifier
replaced by synthetic `123456789012`; bucket and repository account references
are sanitized consistently. It contains metadata, not credentials or state
contents. EC2 project inventory, RDS inventory and ECS cluster inventory were
empty. No application compute, database, certificate or public application
endpoint has been deployed in this batch. Full-stack permissions remain untested.

Reproducible sequence after a reviewed foundation exists:

```powershell
$env:AWS_PROFILE = 'caseflow-rehearsal'
terraform '-chdir=infrastructure/terraform/rehearsal' init -reconfigure -input=false '-backend-config=generated/backend.hcl'
terraform '-chdir=infrastructure/terraform/rehearsal' plan '-target=aws_ecr_repository.app' '-out=generated/registry.tfplan' -input=false
# Inspect the saved plan before applying it.
terraform '-chdir=infrastructure/terraform/rehearsal' apply -input=false 'generated/registry.tfplan'
```

Backend settings, account-specific variables and binary plans remain ignored.
Provisional zero image digests were used only for registry planning; they MUST
be replaced with actual pushed digests before full planning. Refresh the expiry
metadata when the supervised compute session starts. The first unquoted
PowerShell init invocation failed argument parsing; quoted flags succeeded.

Retained costs: hosted zone USD 0.50/month plus queries, and metered S3 requests
and small state-version storage. Empty registries have no image storage yet.
Actual billed usage can lag the credit balance. Reserve USD 1 for foundation
overhead, per the [credit ledger](../../../aws-credit-ledger.md). No teardown
or zero-continuing-cost claim is made. Compute remains pending DNS readiness.
