# Repeat 1 semantic claim audit

Codex AI review under ADR 0006 and rubric `ai-semantic-claims-2026-09-15-v1`.
This is explicitly `ai-reviewed-learning`, with `humanVerified: false` and
`releaseGatePassed: false`. No paid provider calls were made for grading.

All 12 completed review results were read against their actual `manualPurchase`
and cited policy passage. The audit binds the completed run's exact dataset and
predictions hashes. Its 24 inventoried outputs (12 summaries and 12 findings)
contain **93 supported factual propositions, zero unsupported propositions and
zero nonfactual segments**. All 12 requested reviews succeeded.

Compound descriptions were separated into purchase description, supplied total
and currency, each stated absent field, and the scoped policy requirement.
The intended purpose and approval timing qualify the requirement. A finding
that additionally states an absent justification has two propositions:
`textiles-001/finding:0` records both absence and the approval requirement.
`calibration-006` and `mobility-001` mention only two absent fields in their
summaries; the audit does not add the other two from `missing_information` to
those summaries. Repeated quotations of the same rule and inline source IDs
do not create additional distinct factual claims.

The actual purchases have supplied USD currency and 0.00 total, empty vendor,
cost center and justification strings, and empty line-item arrays. Reporting
those supplied values earns support; zero does not imply a missing or invalid
total. None of these outputs adds such a diagnosis or an uncited necessity.
Extraction suggestions were not accepted in these runs. Quote suppliers,
amounts and items must therefore not replace the saved purchase facts.

The separate missing-information check finds **48 true and zero false reports**:
each result lists the four actually empty fields. This is not added to the
93-proposition summary/finding denominator. No abstention cases are in this
predeclared subset; all 12 cases have a relevant cited policy.

Reproduce integrity/completeness validation into a new output file:

```powershell
services/worker/.venv/Scripts/python.exe evals/claim_review.py --directory docs/evidence/2026-09-16-r2/heldout-v3-repeat-1 --evaluation-profile ai-reviewed-learning --review docs/evidence/2026-09-16-r2/heldout-v3-repeat-1/ai-claim-review.json --output NEW-repeat-1-claim-report.json
```

The validator verifies exact text/output hashes and full output coverage; it
does not independently establish semantic truth. These are synthetic repeated
ordinary/conflicting-total cases with one policy passage each, no human
verification, no participant outcomes and no real-world quality inference.
This observed 100% claim-support score does not pass the overall release gate
or establish the quality of extraction, retrieval or untested categories.
