# AWS permission bootstrap validation

2026-09-17. The user approved USD 10 from existing AWS credits, keeping the Free
plan. No policy was created or attached, no workload was launched, and the
account plan was not changed by the agent. Owner execution is still required.

## Checks completed

- New permission-bootstrap tests: 13 passed. Combined with the existing
  secret-redaction bootstrap test: 14 passed (`python-tests.txt`).
- Terraform formatting and validation pass; both mocked plan tests pass
  (`terraform-tests.txt`). The tests require the owner-controlled boundary on
  all five application roles. This does not prove real AWS IAM permissions.
- Ruff checks pass for both new Python files; the CI JavaScript parses.
  The CI Terraform gate now includes the new offline bootstrap tests.
- Live default `aws_access.py --account <expected-account>` preview passed
  under the read-only operator: exact account/user, active Free plan, baseline
  policies, no unexpected groups/inline policies, no conflicting reserved roles
  or instance profile, and no conflicting managed-policy documents. It printed
  `Preview only: no permissions changed`. The owner-only `--apply` was not run.
- All three documents passed AWS Access Analyzer `validate-policy` with zero
  findings (`validation.json`). This is syntax/static guidance, not a proof
  of least privilege or successful deployment.
- Eleven AWS IAM `simulate-custom-policy` cases matched their expected results
  (`simulations.json`): required role boundary, role-name scope, blocked boundary
  removal/admin policy attachment, explicit Paid-upgrade deny, approved versus
  oversized instance, ancillary launch resource, state prefix and unrelated S3
  object denial. Simulations do not include all runtime conditions or SCPs.

The `policies/` documents use synthetic account ID 123456789012. These exact
documents were validated and simulated; actual setup renders the real account
locally. To reproduce simulation, populate PolicyInputList with the JSON text
of the two listed files, ActionNames/ResourceArns/ContextEntries from each case,
and call `aws iam simulate-custom-policy --cli-input-json file://request.json
--profile caseflow-rehearsal --region us-east-1`. Do not use these synthetic
account documents to grant real access.

## Failures and review corrections retained in the explanation

Tests initially failed because the implementation was absent. Added negative
tests then exposed missing reserved-role/profile checks and required baseline
permissions; each failed before its fix. Review also identified EC2's per-resource
evaluation: the instance-size condition was split from ancillary resource
permissions. An initial Terraform assertion over whole role objects triggered
a Terraform diagnostic serialization panic; comparing boundary attributes
directly produced the intended failing assertion, then passed after wiring.
An initial native-shell simulator call could not parse multiple file arguments;
structured CLI-input JSON resolved it. No failed attempt changed AWS resources.

An independent code reviewer checked the fixes and found no further important
defects in that review scope. This is engineering review, not certification.
The access guide records regional/account-wide deployment privileges and the
remaining need for actual deployment evidence.

A final narrow review added explicit KMS decrypt/data-key operations to the
runtime ceiling, restricted to the account's AWS-managed Secrets Manager key
alias and service-mediated calls. Its regression test passed and all three
final documents were revalidated with zero findings. The 11 simulator cases
exercise deployment policies; they do not prove the KMS runtime path works.

Sources: [access instructions](../../../../infrastructure/terraform/rehearsal/ACCESS.md),
[ADR 0009](../../../adr/0009-deployment-access-bootstrap.md).
