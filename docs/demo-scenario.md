# Synthetic purchase scenario, version 1

This is a scenario specification, not seeded application data. Phase 0 still
needs executable identity, policy, quote, and template fixtures.

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
