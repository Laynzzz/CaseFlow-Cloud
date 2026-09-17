# Repeat 2 semantic claim audit

Codex AI review under ADR 0006 and rubric `ai-semantic-claims-2026-09-15-v1`.
Profile: `ai-reviewed-learning`; `humanVerified: false`; `releaseGatePassed: false`.
Grading made no paid provider calls. All 12 completed review results were read
against their saved `manualPurchase` and actual cited passage; the audit binds
the completed run's exact dataset and predictions hashes.

The 24 outputs (12 summaries and 12 findings) contain **96 supported factual
propositions, zero unsupported propositions and zero nonfactual segments**.
All 12 requested reviews succeeded. A separate missing-information audit finds
**48 true reports and zero false reports**, outside the summary/finding count.

Each summary's description, supplied total/currency, stated absent fields and
scoped approval requirement were separated. `calibration-001` and `signage-006`
mention only two absent fields in their summaries, so the audit does not import
additional absence claims from their `missing_information` arrays.
`textiles-001/finding:0` contains both the absent justification and the policy
requirement; those are two propositions.

`signage-001/summary` additionally states there is no cited policy requiring
justification, vendor or line items. Those three evidence-scope assertions are
supported: the sole supplied cited passage requires only a cost center. This
does not assert that no such policy exists anywhere. The repeated rule quotation
and inline source locator introduce no new distinct policy proposition.

Every saved purchase has total 0.00 and currency USD, with empty vendor,
cost-center and justification strings and an empty line-item array. No output
misdiagnoses zero as missing or invalid, assigns accepted quote facts to that
purchase, or adds an unsupported necessity. Requirement scope, purpose and
approval timing are evaluated together. Citation presence alone earns no credit.

Validate exact coverage into a new output file:

```powershell
services/worker/.venv/Scripts/python.exe evals/claim_review.py --directory docs/evidence/2026-09-16-r2/heldout-v3-repeat-2 --evaluation-profile ai-reviewed-learning --review docs/evidence/2026-09-16-r2/heldout-v3-repeat-2/ai-claim-review.json --output NEW-repeat-2-claim-report.json
```

The validator checks hashes and completeness, not independent semantic truth.
This fixed synthetic subset contains only ordinary/conflicting-total cases and
one policy passage per case. It does not measure abstention, hostile-input
variability, participant outcomes or real-world quality. Its 100% observed
claim-support score does not establish other quality targets or release passage.
