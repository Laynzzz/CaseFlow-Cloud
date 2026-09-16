# Development v6 guard 10: AI semantic claim review

Reviewer: Codex AI assistant. Method: `ai-claim-review-v1`. Profile:
`ai-reviewed-learning`. `humanVerified: false`. Delegated experimental AI review
under ADR 0006; this is not independent human validation. The UTC review timestamp
is saved in `ai-claim-review.json`.

## Scope and results

The reviewer read all 10 summaries and 8 findings, individually, with each output's
actual manualPurchase, citations, and saved review evidence. The inventory came
from `review_packet(directory, 'ai-reviewed-learning')`. This completed guard run
binds **synthetic-v1**, not synthetic-v2. It contains equipment-001 through
equipment-010 only; the separate full development run was not reviewed here.

Review prompt/schema: `purchase-review-2026-09-16-v6` / `purchase-review-v5`.
Extraction prompt/schema recorded in this run:
`purchase-assistant-2026-09-15-v5` / `purchase-assistant-v4`. Extraction proposals
and quote evidence were not substituted for the manual purchase facts supplied
to the review job.

| Measure | Result |
| --- | ---: |
| Supported factual claims | 78 |
| Unsupported factual claims | 0 |
| Factual denominator | 78 |
| Supported fraction | 100% |
| Non-factual qualitative segments | 1 |
| Reviewed outputs | 18 |
| Failed or missing review jobs | 0 |
| Provisional 95% claim target met | Yes |
| Release gate passed | No |

Each summary contains seven factual propositions: the equipment-kit description,
0.00 USD total, four separately missing fields, and either the cited cost-center
requirement or the lack of policy evidence. The eight findings each state one
supported normative proposition. Equipment-009 also calls the missing information
"key", which contributes one non-factual qualitative segment.

## Rubric and specific judgments

Rubric version: `ai-semantic-claims-2026-09-15-v1`, unchanged from the v5 full
review notes and applying `evals/README.md` and plan section 12.

- Split compound text into separate purchase-field facts, policy requirements,
  diagnoses, and consequences. An amount with its currency is one numerical
  claim. A scoped policy requirement with its stated timing is one normative
  claim. Count repetitions within one output once; repetitions across outputs
  remain separate.
- Support purchase facts only from actual manualPurchase; support policy claims
  only when the actual cited passage entails the claim for that purchase.
  Citation existence alone does not establish semantic support.
- Explicit required, necessary, and essential language asserts factual
  necessity and must have evidence. Qualitative key/critical language alone is
  `NOT_A_FACT`. Hedges do not excuse unsupported diagnoses or requirements.
- Keep zero distinct from missing data. All ten purchases supply total `0.00`
  and currency `USD`; summaries faithfully describe that value without claiming
  invalidity, a conflict, or an unstated minimum price.
- All ten purchases supply description `Equipment kit`, empty vendor,
  costCenter, and justification strings, and an empty lineItems list. Each of
  those purchase facts is supported independently.
- The eight cited policies say exactly "Equipment purchases require a cost
  center before approval." Their equipment scope and before-approval timing
  support all eight finding texts and the corresponding summary paraphrases.
  No summary extends this necessity to vendor, justification, or line items.
- Equipment-007 and equipment-008 have empty review evidence and no citations.
  Their summaries correctly describe an inability to determine policy compliance
  or required fields. These are narrow epistemic limitations, not prohibitions
  on approval. Each is counted as one proposition about the absence/insufficiency
  of supplied policy evidence for that assessment.

The reviewer authored the per-case segment selections after reading each output.
A local Python helper expanded those selected propositions, attached each exact
sourceText, SHA-256, purchase, citations, and evidence, and called `grade_packet`.
It did not infer semantic support from keyword matching or citation presence.
`coverageConfirmed: true` records that the reviewer read the complete output.

## Separate missing_information diagnostic

All ten outputs report exactly vendor, costCenter, justification, and lineItems
as missing. All 40 entries match the supplied empty strings/list. **False missing
reports: 0/40; affected cases: 0/10.** No output reports total, currency, or
description missing. Case-by-case results are retained in the review JSON's
`missingInformationReview` field. These entries are not added to the frozen
summary/finding denominator, and are not counted again as factual claims.

## Artifacts and verification

- `ai-claim-review.json`: exact run hashes, explicit AI provenance, exact source
  text and evidence for every inventoried output, atomic grades and rationales,
  and the separate missing-information diagnostic.
- `ai-claim-report.json`: unmodified `grade_packet` output; the complete R2
  release gate remains false.
- This notes file: rubric, scope, judgments, counts, and limitations.

Verification recomputed the packet and grades, asserted equality with the saved
report, and checked every saved source text/hash, purchase, citation, and evidence
object against the fresh packet. It also checked the recorded missing-information
lists against all ten saved outputs. No provider calls or git commits occurred.
Only these three review artifacts were written in the completed guard folder.

For an independent deterministic recheck, choose a new report output path:

```powershell
services/worker/.venv/Scripts/python.exe evals/claim_review.py --directory docs/evidence/2026-09-16-r2/development-v6-guard-10 --evaluation-profile ai-reviewed-learning --review docs/evidence/2026-09-16-r2/development-v6-guard-10/ai-claim-review.json --output NEW_REPORT.json
```

## Limitations

The checker validates completeness, provenance, and hash binding, not semantic
truth. AI grading can share model or author biases with the system being tested.
This narrow, correlated sample uses one repeated equipment policy and similarly
empty purchases. The supported fraction is a descriptive synthetic development
result, not held-out validation, general policy accuracy, independent human
evidence, or a production-readiness claim. Atomization can affect the denominator;
exact text and rationales remain available for later disagreement. The broader
development run, held-out evaluation, and remaining R2 gates stay separate.
