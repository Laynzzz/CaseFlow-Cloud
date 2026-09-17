# ADR 0008: adapt rehearsal sizing to the existing AWS Free plan

Status: accepted configuration decision, 2026-09-17. Live read-only discovery;
deployment and capacity remain unverified. Updates the initial sizes in ADR 0007,
without changing its service boundaries or authorizing provisioning.

The user has an active AWS Free account plan. A limited `caseflow-operator`
session confirms USD 100 remaining credits. The original `db.t4g.small` and
`t3.large` choices are not in the Free-plan instance selections. A credit balance
does not remove those restrictions. Do not upgrade the account automatically.

Use Single-AZ PostgreSQL 18.6 on `db.t4g.micro` with the existing encrypted 20 GiB
gp3 storage. AWS documents this database class for the Free plan, and regional
discovery lists the exact version/class/storage combination. It has less memory
than the initial database proposal; migrations, application/identity connections
and the synthetic approval workflow must pass on the actual instance. This is
not a load-capacity claim. If the database cannot support the bounded workflow,
report the failure before requesting any paid-plan change.

Use `m7i-flex.large` (2 vCPUs, 8 GiB, x86_64) for the shared Kafka/Keycloak/
monitoring host. Live EC2 discovery lists it as Free Tier eligible and offered
in both proposed availability zones. It preserves the original memory budget
and architecture, unlike shrinking the host to a 2 GiB instance. Its on-demand
rate is slightly higher than `t3.large`; this is account eligibility, not a
claim that every Free-plan resource has a zero list price.

Keep ECS/Fargate, private RDS, S3, ALB/ACM, Secrets Manager, TLS, IAM boundaries,
bootstrap gates and data-retention rules unchanged. AWS read APIs do not prove
that every create operation will be permitted or that service capacity is
available. Service quotas and regional catalog availability are necessary but
insufficient evidence. Any service restriction encountered during a separately
authorized deployment must be reported; do not silently switch to Paid.

The alternative is keeping the original sizes and upgrading to Paid, which
allows charges after applicable credits. That adds billing exposure without
evidence that this short rehearsal needs a larger database. A local-only demo
remains useful but does not satisfy the plan's AWS release gate.

Sources: [RDS Free-plan classes](https://aws.amazon.com/rds/free/),
[EC2 eligible instance discovery](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/LaunchingAndUsingInstances.html),
[preflight evidence](../evidence/2026-09-17-r3/cloud-preflight/summary.md).
