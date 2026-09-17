# ADR 0007: bounded AWS rehearsal and explicit retained data

Status: implementation scaffold, offline validation only, 2026-09-17. No AWS
account-backed plan, deployment, smoke, rollback or teardown has run.

Preserve the plan's Java/web and Python Fargate deployments, PostgreSQL RDS,
S3, ECR, ALB, Secrets Manager and Terraform. For the initial supervised cloud
evidence session, use one EC2 host for Kafka, synthetic Keycloak identity and
small monitoring services. Kafka has one broker/controller, replication factor
one and no high availability. The host is a shared failure domain; replacement
can interrupt identity, messaging and observability together. Its dedicated
encrypted EBS data volume is retained separately from the disposable host.

This implements the plan's permitted single-broker VM profile. Managed Kafka
and independent highly available identity/monitoring services are deferred;
their cost is not justified by a short synthetic deployment test. No local
benchmark is a capacity guarantee for the proposed cloud instance sizes.

Public access terminates at HTTPS ALB host rules. Application and identity
backend ports accept the ALB security group only. RDS is private and all
database clients verify TLS against the checked regional RDS CA bundle.
Kafka PLAINTEXT is confined by security groups to the VPC task group; this is
an explicit rehearsal limitation, not an assertion of transport encryption or
a production security recommendation. Management listeners and anonymous
Grafana Viewer are reachable only through private operational access/SSM.

Public IPv4 egress on the tasks and auxiliary VM avoids NAT gateway cost in
this short profile. Task services remain stopped until bootstrap completes.
The bootstrap task alone reads the RDS-managed master credential and writes
generated application/identity secret values. Terraform stores secret ARNs
and metadata, not those values; no secret-version or random-password resource
is used. Application task roles cannot fetch database master credentials.

One-off bootstrap creates roles and their narrow grants; API Flyway startup
applies central schema migrations. Image rollback preserves data and depends
on backward-compatible migrations. Single-node broker restart/recovery and
actual cloud S3 behavior require account-backed verification before release.

RDS, S3, secret metadata and auxiliary data disk have `prevent_destroy`; RDS
and ALB also start with provider deletion protection. A blanket destroy is
deliberately not a data-deletion procedure. Teardown requires a reviewed plan
listing retained data, snapshots and continuing costs. Budget alerts do not
stop spending. The existing USD 10 AI ledger does not authorize AWS charges.

Implementation: [Terraform rehearsal](../../infrastructure/terraform/rehearsal/README.md).
Current assumptions/pricing: [deployment proposal](../aws-deployment-proposal.md).
This decision does not authorize provisioning; account, DNS and separate
cloud-budget prerequisites remain outstanding.
