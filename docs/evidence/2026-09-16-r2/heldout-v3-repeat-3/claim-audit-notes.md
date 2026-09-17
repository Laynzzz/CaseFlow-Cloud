# Repeat 3 semantic claim audit

Codex AI review under ADR 0006 and rubric `ai-semantic-claims-2026-09-15-v1`.
Profile: `ai-reviewed-learning`; `humanVerified: false`; `releaseGatePassed: false`.
Grading made no paid provider calls. Every summary and finding from all 12
completed reviews was read against its saved purchase and actual cited passage.
The audit binds the completed run's dataset and predictions hashes.

The 24 outputs contain **93 supported factual propositions, zero unsupported
propositions and zero nonfactual segments**. All 12 reviews succeeded. The
separate missing-information audit records **48 true reports, zero false**;
those array entries are not added to the summary/finding denominator.

Summary purchase description, total/currency, each stated absent field and
scoped policy requirement are separate propositions. The policy's purpose and
approval timing qualify the requirement. `packaging-001` mentions only two
absent fields in its summary. `signage-006` states no policy requirement in
its summary, so none is invented from its citations or finding.
`textiles-001` reports a zero total without naming a currency; its segment
therefore says only zero. `textiles-006/finding:0` refers to this purchase
request, which retains the matching textiles context.

All actual purchases have supplied total 0.00 and USD, empty vendor, cost center
and justification, and empty line-item arrays. These are saved facts; the
unaccepted quote/extraction proposals are not purchase facts. Reporting zero
does not assert it is missing or invalid. No output adds an unsupported zero
diagnosis or necessity. Repeated wording/source locators are not new distinct
factual claims, and citation existence alone earns no support.

Validate exact coverage into a new output file:

```powershell
services/worker/.venv/Scripts/python.exe evals/claim_review.py --directory docs/evidence/2026-09-16-r2/heldout-v3-repeat-3 --evaluation-profile ai-reviewed-learning --review docs/evidence/2026-09-16-r2/heldout-v3-repeat-3/ai-claim-review.json --output NEW-repeat-3-claim-report.json
```

This validator checks hashes and coverage, not independent semantic truth.
The fixed subset includes ordinary and conflicting-total examples only, with
one policy passage each. It does not measure abstention or hostile-input
variability, participant outcomes or real-world quality. The observed 100%
claim-support score is separate from other quality targets and release gates.
