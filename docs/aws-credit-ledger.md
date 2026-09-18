# AWS rehearsal credit allowance

Authorized by user on 2026-09-17: **USD 10 from existing AWS credits**, for a
short deployment, workflow smoke, image rollback and cleanup in us-east-1.
The account stays on Free. No Paid upgrade or out-of-pocket AWS charges are
authorized. This is independent of the USD 10 hosted-AI lifetime ledger and
the domain registration purchase. Do not request the same allowance again.

| Evidence point | Account credit balance | Rehearsal state |
| --- | --- | --- |
| September 17 read-only preflight | USD 100 reported | No project cloud resources provisioned |
| Permission bootstrap preparation | No newer balance measurement | Policies prepared/validated/simulated; owner grant pending |
| September 17 foundation bootstrap (September 18 UTC) | USD 100 reported immediately before creation | Owner grant verified; Route 53 zone, protected state bucket and two empty ECR repositories created |

Foundation timestamps: Route 53 zone created September 18 at 00:24:07 UTC;
state bucket created at 00:28:04 UTC. Registry creation timestamps and verified
inventory are in [foundation evidence](evidence/2026-09-17-r3/cloud-foundation/summary.md).
No application compute, RDS or ECS service has started. DNS delegation is pending.

Retained foundation estimate: USD 0.50 per hosted-zone month plus DNS queries;
S3 state versions/requests add a small usage charge (not measured yet). The two
repositories are empty, so no image storage has accumulated. Reserve USD 1 of
the allowance for foundation/storage/request overhead; this is an estimate,
not a billed charge or hard limit. The account credit balance can lag usage.
Compute's four-hour rehearsal window has not started. These foundation resources
remain intentionally retained for the next deployment step; ongoing cost is not zero.

The balance is account-wide and can change due to other activity. It is not an
exact, instantaneous project cost meter. Before creating billable resources,
record a fresh balance and projected resource cost; track creation/teardown
times and estimates during the session. Target no more than four running hours.
Stop adding resources if forecast usage approaches the remaining allowance.
Prioritize cleanup and report delays or failures; budget alerts are not a cap.

After tests, record deleted and deliberately retained resources, their estimated
continuing cost and eventual credit usage as billing catches up. Do not claim
zero ongoing cost while DNS, state, object versions, logs, snapshots or other
resources remain. Do not create recurring automation without a user request.

Current estimate and sequence: [deployment proposal](aws-deployment-proposal.md).
