# Synthetic purchase scenario, version 1

This scenario now has executable synthetic fixtures. The packaged demo below
verifies the manual approval path; the separately configured development fixture
also supports the experimental AI journey and published evaluation.

Acme Studio's requester needs one laptop from Synthetic Equipment Supply for
USD 4,200.00 to edit training videos. Use cost center CREATIVE-01. The requester
provides the vendor quote; a product link is a possible future supplementary
field, not a substitute for the plan's uploaded quote.

The requester submits the draft. A manager is assigned to step 1 and a finance
reviewer to step 2. Both are approvers in Acme Studio and neither is the
requester. Manager approval leaves the case ACTIVE; finance approval changes
it to APPROVED and queues document generation. The approved state remains even
if rendering fails. Rejecting or cancelling terminates the case; corrections
start a linked new draft.

A second tenant, Northstar Workshop, provides the isolation test scenario.
Its members must not read Acme Studio cases, quotes, documents, or AI results.
Each tenant will also have an administrator and an auditor for permission tests.

In R2, a synthetic policy requires written justification for equipment above
USD 3,000.00. A deliberately incomplete quote/request variant exercises missing
information. AI proposes fields and cites policy evidence; it never decides
approval or silently fills missing values. The complete manual journey must
work independently of the provider.

## Packaged manual demo

With Node 22 and Docker Desktop's Linux engine, run from a clean checkout:

```text
node scripts/release.mjs build demo-v1
node scripts/release.mjs deploy demo-v1 --observability
```

Choose a new release name when an existing manifest already uses that name.
This isolated stack uses different ports/volumes from development and performs
an automated smoke before reporting deployment success. Open
[the packaged app](http://127.0.0.1:18080). Synthetic usernames are `requester`,
`manager`, `finance` and `admin`; their password is `DEMO_PASSWORD` in ignored
`infrastructure/release/generated/.env`. Keep this file with its database volume.

1. Sign in as requester and choose **Release Acme Studio**. Create a request
   with synthetic vendor, description, cost center, justification and a USD 4,200
   line item; choose the release workflow and template. Save the draft.
2. Assign manager to step 1 and finance to step 2, save reviewers and submit.
3. Sign out, sign in as manager, select the same organization and open the
   request from its list. Approve. The request remains active for finance.
4. Repeat as finance and approve. Observe approval separately from document
   generation; wait for **Succeeded**, then download the Word document.
5. Inspect [Grafana](http://127.0.0.1:13000/d/caseflow-operations) for the service
   metrics. A sampled trace may not exist for every request; the durable job and
   audit remain the authoritative record.

The packaged profile intentionally has no provider key: AI controls explain the
manual fallback. Live AI evaluation uses the existing shared budget ledger and
the separate evaluation runbook, not a new allowance for each demo.
Use `node scripts/release.mjs stop` to stop only this release's containers and
retain data. Rollback prerequisites and operational checks are in
[the runbook](runbooks/observability.md). Never delete volumes to make a failing
upgrade appear successful.

[Actual browser/clean-checkout evidence](evidence/2026-09-17-r3/demo/summary.md)
records the exercised steps and remaining UI limitations.
