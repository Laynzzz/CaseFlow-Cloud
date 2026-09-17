# Synthetic v3 held-out semantic claim audit

Reviewer: Codex AI assistant (delegated semantic claim reviewer). Method:
`ai-claim-review-v1`; profile: `ai-reviewed-learning`; human verified: **false**.
Rubric: `ai-semantic-claims-2026-09-15-v1`, unchanged from the development-v6-full
AI claim review. This is experimental AI-reviewed evidence under ADR 0006.

The assistant read all 60 summaries and 48 findings against each review's actual
`manualPurchase`, citations and returned evidence. No unsupported proposition was
identified. The audit preserves every exact output text and its SHA-256, atomic
judgments and rationales, purchase facts, citations and evidence. Field absence
was not treated as a policy obligation, and extraction proposals and reference
answers were not treated as accepted purchase data.

The final packet was created after the run finished at
`2026-09-17T02:52:00.934Z`, with `stoppedEarly: false` and all 60 selected cases.
Predictions SHA-256:
`ad5bdde8a94433372238e69e2174553da55e96af42d5ca5e35b7adf655dd5c1f`.
Dataset `synthetic-v3` held-out SHA-256:
`4897f4d248cac923945e0a6fa4d34a8a6a21bf4ce7809a4dc1803014cec1fe54`.
Preparatory observations were bound to completed case outputs while the runner
continued. Prior bindings were rechecked before adding observations and before
finalization; no incomplete-run packet was published.

| Measure | Result |
| --- | ---: |
| Supported factual claims | 463 |
| Unsupported factual claims | 0 |
| Factual denominator | 463 |
| Supported fraction | 100% |
| Non-factual segments | 0 |
| Reviewed summaries / findings | 60 / 48 |
| Reviewed output texts | 108 |
| Failed or missing review jobs | 0 |
| Failed extraction jobs, reported separately | 19 |
| False missing-information entries | 0 / 240 |
| Provisional 95% claim target met | Yes |
| Release gate passed | No |

| Family | Supported | Unsupported |
| --- | ---: | ---: |
| Calibration | 76 | 0 |
| Filtration | 77 | 0 |
| Packaging | 74 | 0 |
| Textiles | 80 | 0 |
| Signage | 78 | 0 |
| Mobility | 78 | 0 |

## Rubric and coverage

Compound text is split into purchase-field facts, scoped policy obligations,
diagnoses and consequences. Amount and currency form one numerical proposition;
a scoped rule with its stated purpose or timing forms one normative proposition.
Repeated assertions within an output count once; repetitions across different
outputs count separately. Every asserted field absence counts separately. Facts
not stated in the summary or finding are not added merely because the input or
`missing_information` list contains them.

Purchase facts require support in the actual saved purchase. Policy claims require
entailment by the actual cited passage for the purchase's scope. Citation existence,
plausibility and hedged diagnoses do not themselves establish support. Explicit
necessity words require evidence; qualitative salience alone is non-factual.
No unsupported hedged diagnosis or separate qualitative-salience assertion was
identified in this run. Helpers serialized explicitly selected per-output semantic
judgments and performed consistency checks; they did not infer semantic support
from keywords or the mere existence of citations.

## Specific judgments

**Zero remains present data.** All saved purchases have total `0.00` and currency
`USD`, even when the supplier quote uses another currency or a positive amount.
Statements of `0.00 USD` therefore describe the actual saved purchase. No output
asserts that zero is missing, invalid or forbidden by policy. Signage-004 says the
purchase request is for a sign holder "priced at 0.00 USD"; in this request-summary
context the wording is interpreted as the supplied request amount, not a separate
assertion about a supplier's unit price. The exact wording is retained for a later
reviewer to challenge this interpretation.

**Missing fields do not create new obligations.** Vendor, cost center,
justification and line items are absent from the saved requests. Cost-center rules
apply to calibration, packaging and signage. Justification rules apply to
filtration, textiles and mobility. Summaries correctly distinguish absent fields
from each cited policy's requirement. No source has been assumed accepted merely
because extraction succeeded; all reviews still concern the saved draft.

**Three findings contain two propositions.** Textiles-009 and textiles-010 findings
say a business-need justification is missing and required before approval.
Mobility-003 similarly says an intended-use justification is missing and required.
Each is split into an absence fact supported by the empty saved justification and
an obligation supported by the actual policy passage. This preserves both factual
assertions instead of awarding one blanket citation-based grade.

**Scope, timing and purpose are not added to paraphrases.** Filtration-003 and
filtration-004 summary grades preserve their shorter written-justification rule
without adding the policy's explanatory-purpose clause. Textiles-004's summary
does not state approval timing, so its graded paraphrase does not add that timing.
Textiles-002 and textiles-010 preserve the stated reviewer-check obligation.
Textiles-010 cites a shorter excerpt, but its referenced returned passage includes
the full textiles scope and approval timing; that actual passage supports the rule.

**Omissions and repeats affect counts.** Calibration-006 and packaging-002 do not
state vendor or line-item absence. Filtration-002 and mobility-009 omit line-item
absence. Packaging-006 and packaging-009 omit vendor absence. Those facts are not
invented in their summary grades. Calibration-010 repeats the missing cost center
and its rule in a policy-linked sentence; the repeated absence and obligation count
once each rather than adding a third restatement. Repeated policy quotations and
inline chunk IDs are likewise not extra purchase or policy propositions.

**Abstention remains narrow.** Cases 007 and 008 in every family return empty
review evidence and no citations or findings. Their statements that policy
requirements or compliance cannot be assessed are supported by those actual empty
evidence objects. This is one scoped insufficiency proposition per summary, not a
claim that purchasing is prohibited or that every absent field is mandatory.

## Separate diagnostics and verification

Every review reports four missing fields; all 240 entries agree with the actual
empty strings or list. No review reports the supplied total, currency or description
as missing. The case-level checks are retained in `missingInformationReview` and
are separate from the 463 summary/finding propositions.

Nineteen extraction jobs failed, but all 60 review jobs succeeded. The extraction
failures are preserved by ID in `completedRun.failedExtractionIds`; they are not
removed from extraction scoring or converted into failed reviews. Claim support
does not establish extraction quality or erase those operational failures.

Verification rebuilt `review_packet(directory, 'ai-reviewed-learning')`, checked
every saved source text/hash, purchase, citation and evidence object against the
packet, verified completed-run and prediction hashes, and required exact equality
between a fresh `grade_packet` result and the saved report. It independently checked
all 60 missing-information lists and the 19 failed extraction IDs. All checks passed.

Reproduce the standard grading contract into a new output file:

```powershell
services/worker/.venv/Scripts/python.exe evals/claim_review.py --directory docs/evidence/2026-09-16-r2/heldout-v3-full --evaluation-profile ai-reviewed-learning --review docs/evidence/2026-09-16-r2/heldout-v3-full/ai-claim-review.json --output NEW_REPORT.json
```

Files: `ai-claim-review.json` holds judgments and exact source bindings;
`ai-claim-report.json` is the unmodified `grade_packet` output; this file records
method, counts, judgment details and limits. This task made no provider calls,
product/prompt/schema/dataset changes or commits.

## Limits

AI review can share errors with the system being evaluated; this is not independent
human validation. Atomic segmentation and contextual readings affect counts, so
full texts and rationales remain available for independent disagreement. The cases
use repeated, short policies and similarly empty synthetic drafts; the descriptive
100% fraction is not a real-world accuracy guarantee. Citation and hash validation
establish source binding and completeness, not semantic truth. Extraction, retrieval,
abstention, operations, isolation, user outcomes and remaining R2 release gates
require their own evidence. `releaseGatePassed` remains false.
