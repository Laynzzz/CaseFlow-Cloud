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
