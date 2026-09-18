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

Files beside this report preserve DNS, published/local image identifiers,
pre-apply cost readback, resource actions and scan decisions. Account identifiers
are consistently replaced by synthetic `123456789012`; real credentials, state,
binary plans and application secrets are excluded.
