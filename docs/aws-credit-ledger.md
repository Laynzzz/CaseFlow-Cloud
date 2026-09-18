# AWS rehearsal credit allowance and outcome

Authorized by the user on September 17, 2026: **USD 10 from existing AWS credits**
for a short deployment, workflow smoke, image rollback and cleanup in us-east-1.
The account stays on Free. No Paid upgrade or out-of-pocket AWS charges were
authorized or requested. This is separate from the USD 10 hosted-AI lifetime
ledger and the domain registration purchase.

| Evidence point | Account credit balance | Rehearsal state |
| --- | --- | --- |
| September 17 preflight | USD 100 reported | No project cloud resources |
| Foundation, September 18 00:24–00:28 UTC | USD 100 reported | Public DNS zone and protected state bucket created; registries followed |
| Before full apply, 00:36 UTC | USD 100 reported; ACTIVE/FREE | Reviewed infrastructure plan; application tasks initially zero |
| Final inventory, 01:41:56 UTC | USD 140 reported; ACTIVE/FREE | Workload removed, no database/snapshots/compute/application storage; retained resources below |

The infrastructure session ran approximately **00:38–01:42 UTC (64 minutes)**,
inside the four-hour operating target. [Actual evidence](evidence/2026-09-17-r3/cloud-deployment/summary.md)
records successful HTTPS/browser/S3 workflow, candidate rollout, prior-image
rollback and checksum preservation. Terraform removed 82 managed resources;
its managed state is empty. The final synthetic snapshot was explicitly deleted
and AWS readback found no manual or retained automated backups.

**Estimated session cost: USD 1–2 including a conservative overhead reserve.**
This is a planning estimate, not an observed bill. The original compute/edge
estimate was about USD 0.22/hour; temporary task overlap, startup/replacement,
DNS, storage, logs and requests are additional. [Rates and assumptions](aws-deployment-proposal.md)
remain recorded. The account-wide credit balance rose from USD 100 to USD 140;
we do not attribute that increase to this project, subtract balances to invent a
project bill, or treat it as additional spending authorization. Billing can lag.
The project-specific billed total is **not yet known**.

## Intentionally retained resources

Verified in [final inventory](evidence/2026-09-17-r3/cloud-deployment/teardown-inventory.json):

| Resource | Retention reason | Continuing cost / consequence |
| --- | --- | --- |
| Public Route 53 zone for laynexia.com, NS/SOA records only | Registrar now delegates to it; preserve domain DNS control | About USD 0.50/month plus queries; no application host records remain |
| Protected, versioned Terraform state bucket | Deployment audit and future state bootstrap | 46 state versions totaling 3,606,687 bytes at inventory; small storage/request charges, not zero |
| Seven ECS task-definition revisions | Deliberately retained immutable configuration; scoped operator cannot deregister on wildcard resources | No running tasks; images and task roles were deleted, so definitions alone cannot run the application |
| Seven runtime secrets marked for deletion | Terraform's configured seven-day recovery window | Not retrievable during pending deletion; names can prevent immediate recreation. No secret values archived |
| Three owner-created access policies and existing operator sign-in access | Account-owned prerequisites for future authorized work | No workloads; do not widen or remove account access as incidental cleanup |
| AWS-managed service-linked roles | Account infrastructure, including unrelated existing service roles | Retained; no application compute or storage implied |

No workload EC2/EBS, RDS or snapshots, ALB, active ECS services/tasks, ECR images,
application S3 bucket/versions, private Cloud Map namespace, workload log group,
ACM certificate, VPC or network interfaces remain. The RDS-managed master secret
was removed with its database. The public application is intentionally offline;
the local demo was not torn down.

Keep the DNS and state costs within the same allowance; it is not renewed per
session. At about USD 0.50/month plus small variable usage, retained foundation
costs continue while present. The account Free plan currently reports expiration
March 17, 2027; do not upgrade it automatically. Recheck the current balance,
pricing and remaining allowance before any future deployment. A future account
billing view can establish delayed charges; no recurring monitoring was created.

The shared AI ledger remains USD 0.633975 of USD 10. This entire cloud rehearsal
made no hosted-AI calls. Budget alerts and a credit balance are not hard spending
caps; bounded runtime, explicit teardown and inventory are the controls used.
