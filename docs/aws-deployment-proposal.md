# Short-lived AWS release rehearsal proposal

Status: **executed and torn down**, September 17 local / September 18, 2026 UTC.
The actual HTTPS purchase/browser/S3 workflow, candidate rollout, rollback and
remaining-resource inventory passed. [Cloud evidence](evidence/2026-09-17-r3/cloud-deployment/summary.md)
and the [credit ledger](aws-credit-ledger.md) record outcomes and retained costs.
The account remains Free. The USD 10 AWS allowance is separate from the AI ledger.
The architecture and estimates below preserve the reviewed deployment proposal;
provisioning prerequisites were satisfied during this session.

[ADR 0008](adr/0008-free-plan-rehearsal-sizing.md) updates the initial instance
sizes for the Free plan. [Read-only preflight evidence](evidence/2026-09-17-r3/cloud-preflight/summary.md)
proves account state, catalog availability and quotas, not successful deployment.

## Concrete outcome

Deploy a synthetic purchase workflow over HTTPS, sign in with OIDC, approve a
$4,200 request, generate/download its DOCX from S3, then replace and roll back
the application images while preserving the approved record. Capture service
health, the correlated trace, image digests, migration history and teardown
inventory. This is the remaining cloud evidence required by `plan.md`; local
Compose evidence cannot substitute for it.

Use a short supervised session and tear down compute/network resources after
evidence is collected. Keeping the proposed stack running continuously is
materially more expensive and provides little additional release evidence.

## Proposed infrastructure

- Two ECS/Fargate Linux x86 tasks, initially one Java API/web task and one Python
  worker task, each 0.5 vCPU/1 GiB. These are initial smoke sizes, not measured
  capacity claims. ECR repositories store immutable image digests.
- One RDS PostgreSQL Single-AZ `db.t4g.micro`, 20 GiB gp3, private subnets in two
  availability zones, no public database endpoint. Preserve separate migrator,
  Java and worker roles. Regional discovery confirms PostgreSQL 18.6 with this
  class and storage. The smaller database must pass the actual migration,
  identity and approval smoke; regional orderability does not prove capacity.
- S3 bucket with public access blocked, versioning, encryption and least-privilege
  task roles. Cloud storage endpoints are blank so SDK default credentials use
  task IAM roles; no static S3 keys are injected. Record the selected object
  version/checksum and execute real S3 upload/download compatibility smoke.
- One HTTPS ALB serves `caseflow.laynexia.com` and `auth.laynexia.com`. ACM DNS
  validation requires DNS control; the Route 53 zone exists, with registrar
  delegation from Porkbun verified during the session. No management endpoint is
  included in public ALB routing. [ACM domain validation](https://docs.aws.amazon.com/acm/latest/userguide/domain-ownership-validation.html)
- A short-lived single EC2 `m7i-flex.large` (2 vCPU/8 GiB) hosts the pinned Kafka
  broker, temporary Keycloak identity service, and small monitoring stack. Its
  30 GiB encrypted gp3 disk retains broker/monitoring state during image rollout.
  Kafka and identity share a failure domain and have no high availability, as
  recorded in ADR 0007. This larger
  temporary host avoids assuming a 2 GiB machine can also hold every JVM and
  monitoring process. No public broker/admin/metrics ports; operational access
  uses SSM. Keycloak uses a separate database/role on RDS, production mode and
  the external HTTPS issuer, with synthetic users and PKCE audience mapping.
- The economical rehearsal network gives tasks and the VM public IPv4 addresses
  for outbound registry/provider access, while security groups admit API and
  Keycloak traffic only from the ALB and keep worker/broker operations private
  to the VPC. RDS remains in private subnets. This avoids a NAT gateway for the
  short rehearsal; a private-task/NAT or VPC-endpoint profile costs more and is
  an explicit alternative. [Fargate task networking](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/fargate-task-networking.html)
- Secrets Manager holds database/identity credentials; Terraform receives
  secret references, and credential values never enter committed variable
  files. CloudWatch log retention is short and synthetic; existing OpenTelemetry
  trace/Prometheus/Grafana views remain reachable through private operations
  access. No hosted AI call is needed for the manual workflow cloud gate.

An existing compatible OIDC provider can replace the temporary Keycloak service
after confirming issuer, JWKS, PKCE client, redirect/logout URLs and the
`caseflow-api` access-token audience. That reduces identity administration but
is not assumed to be available. Cognito is an alternative requiring explicit
token/audience integration verification; do not call it a drop-in replacement
for the tested Keycloak configuration.

## Current planning estimate

On-demand, no free-tier credits, no reserved commitments, 730-hour comparison.
Official pages were checked 2026-09-17. Numbers are estimates, exclude tax and
domain purchase, and are not a spending cap. RDS SKU/rate data was fetched from
the public AWS Price List (publication 2026-09-11) and preserved in
[aws-rds-pricing.json](evidence/2026-09-17-r3/cloud-planning/aws-rds-pricing.json).

| Component and assumed quantity | Rate used | 730-hour estimate |
| --- | --- | ---: |
| Two 0.5 vCPU/1 GiB Fargate tasks | $0.0404784/vCPU-hour + $0.004446/GiB-hour | $36.04 |
| One `m7i-flex.large` Linux VM | $0.09576/hour | $69.90 |
| RDS PostgreSQL `db.t4g.micro` Single-AZ | $0.016/hour | $11.68 |
| RDS 20 GiB gp3 | $0.115/GiB-month | $2.30 |
| ALB, assuming one LCU average | $0.0225/hour + $0.008/LCU-hour | $22.27 |
| Five public IPv4 addresses: ALB minimum two, two tasks, VM | $0.005/address-hour | $18.25 |
| VM 30 GiB data + 8 GiB root gp3 at baseline I/O | $0.08/GiB-month | $3.04 |
| Seven runtime secrets + RDS-managed master secret | $0.40/secret-month | $3.20 |
| ECR 2 GiB images | $0.10/GiB-month | $0.20 |
| **Subtotal before DNS/variable logs/objects/requests/transfer** | | **$166.88** |

The updated EC2 and RDS rates come from read-only AWS Price List queries; raw
products are in the [preflight archive](evidence/2026-09-17-r3/cloud-preflight/summary.md).
The previous RDS price archive records the superseded small-instance estimate.

Rate sources: [Fargate](https://aws.amazon.com/fargate/pricing/),
[EC2 regional Price List response](evidence/2026-09-17-r3/cloud-preflight/ec2-pricing.json),
[RDS PostgreSQL](https://aws.amazon.com/rds/postgresql/pricing/),
[ALB](https://aws.amazon.com/elasticloadbalancing/pricing/),
[IPv4](https://aws.amazon.com/vpc/pricing/),
[EBS](https://aws.amazon.com/ebs/pricing/),
[Secrets Manager](https://aws.amazon.com/secrets-manager/pricing/),
[ECR](https://aws.amazon.com/ecr/pricing/).

The compute/ALB/IPv4 portion is about $0.22/hour. Four running hours are about
$0.88 before storage, logs, requests, minimum billing, transfer and setup time.
A **USD 10 allowance from the existing AWS credits**, for a supervised session
targeting at most four running hours followed by teardown, was authorized by
the user on 2026-09-17. Keep the Free
plan; no paid-plan upgrade or out-of-pocket AWS charges are authorized. Credit
metering can lag, so this is an operating allowance, not a hard metering cap.
Include retained storage/DNS costs in the allowance and final inventory.
If left running, plan for
roughly $170–190/month at these small usage assumptions. Larger traces, downloads,
RDS burst CPU credits, extra ALB capacity/addresses and retained snapshots can
increase this. Cloud Map resource/discovery charges, Route 53 DNS queries and
Secrets Manager API calls are additional to this subtotal. IAM roles/policies
do not add a per-role line item here; calls to services they authorize can incur
charges. The public Route 53 zone is retained and adds DNS hosting charges.
Domain registration was purchased separately. The confirmed USD 100 credit
balance is account-wide, not reserved for this project; credit eligibility and
remaining balance must be checked during deployment.
Budgets alerts are delayed monitoring, not a hard cap; teardown and inventory
verification are the cost control.

## Terraform layout exercised in AWS

The single `infrastructure/terraform/rehearsal` root contains the network, data,
edge, IAM, service, auxiliary-host and bootstrap definitions. Its
[runbook](../infrastructure/terraform/rehearsal/README.md) distinguishes validated
source from the separately recorded actual cloud behavior. The responsibilities below map to
these implementation files (related concerns share files):

| File | Responsibility |
| --- | --- |
| `versions.tf`, provider lock | Pinned Terraform/provider compatibility and allowed AWS account |
| `backend.hcl.example` | Remote-state bucket/locking bootstrap instructions without credentials |
| `variables.tf`, `example.tfvars` | Region, domain/zone, budget tag, digest inputs, expiry and data-retention choices |
| `network.tf` | Two-AZ subnets, routes, narrowly scoped security groups |
| `bootstrap.py`, `auxiliary.sh.tftpl` | Runtime role/realm bootstrap, Keycloak secret references and HTTPS issuer configuration |
| `storage.tf` | Private RDS, protected S3, encrypted EBS and retention defaults |
| `storage.tf`, `iam.tf` | Immutable ECR repositories, execution/task/SSM roles |
| `services.tf` | API/worker Fargate task definitions and health-gated services |
| `broker.tf` | Pinned single-node Kafka VM bootstrap, no broker HA claim |
| `edge.tf` | ACM DNS validation and ALB host rules |
| `broker.tf`, `outputs.tf` | Logs, bounded monitoring, private operations and artifact addresses |

A separate bootstrap runbook establishes remote state and an AWS SSO/session
profile. Do not run `apply` or inspect credential stores just to prepare this
proposal. `terraform fmt`/`validate` and an offline review precede an account-backed
plan. Keep RDS/S3 deletion protection and snapshot/version retention explicit;
teardown never silently deletes user data.

Before claiming cloud completion, execute image push by digest, schema migration,
health-gated deploy, full browser/API-to-S3 smoke, trace capture, candidate update,
rollback with old-case readback, then teardown and remaining-resource inventory.
Retained S3 versions, snapshots, ECR images, logs, state bucket and domain/DNS
must be named with their continuing costs.

## Prerequisites for a future rehearsal

Account, us-east-1 region, domain, operator access, registrar delegation and the
original USD 10 credit allowance were established for this completed session.
Nothing further is needed from the user now. A future deployment must recheck
login/credits and remaining allowance, publish fresh image digests, refresh the
expiry tag, handle pending-deletion secret names and rerun scans before applying.
Do not assume the allowance renews or leave the stack running indefinitely.
The [access setup](../infrastructure/terraform/rehearsal/ACCESS.md) remains the
record of the owner-granted prerequisites; do not repeat grants unnecessarily.
