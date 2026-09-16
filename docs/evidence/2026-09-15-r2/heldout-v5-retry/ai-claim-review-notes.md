# Held-out v5 retry: AI semantic claim review

Reviewer: **Codex AI assistant**. Method: `ai-claim-review-v1`. Profile:
`ai-reviewed-learning`. `humanVerified: false`. This is delegated experimental AI
review under ADR 0006, not independent human validation.

The rubric is unchanged from the development review:
`ai-semantic-claims-2026-09-15-v1`. Its complete counting conventions and original
borderline interpretations are recorded in
`../development-v5-full/ai-claim-review-notes.md`. No prompt, model, retrieval
configuration, policy, or dataset was changed during this review. No provider
calls were made by the reviewer. Held-out outputs were used for assessment only.

## Scope and outcome

The reviewer read all 60 completed cases, including their actual summary and
finding text, manual purchase, citations, and saved review evidence. There are
**108 inventoried outputs: 60 summaries and 48 findings**. Proposed extraction
values and uncited quote/policy text were not substituted for the facts supplied
to the review job.

| Measure | Result |
| --- | ---: |
| Supported factual claims | 360 |
| Unsupported factual claims | 52 |
| Factual denominator | 412 |
| Supported fraction | 87.38% |
| Non-factual qualitative segments | 14 |
| Reviewed outputs | 108 |
| Outputs with at least one unsupported claim | 17 |
| Failed or missing review jobs | 0 |
| Provisional 95% claim-support target met | No |
| Release gate passed | No |

All 48 finding texts are supported by their actual cited rules. The 52
unsupported factual assertions occur in summaries; supported purchase facts in
those same summaries remain in the denominator.

| Family | Supported | Unsupported | Non-factual |
| --- | ---: | ---: | ---: |
| Audio | 70 | 6 | 3 |
| Tools | 62 | 15 | 1 |
| Laboratory | 57 | 0 | 3 |
| Safety | 52 | 9 | 1 |
| Display | 64 | 17 | 2 |
| Shipping | 55 | 5 | 4 |

This report binds synthetic-v2 and the completed full retry:

- Dataset SHA-256:
  `3bb2c600455389735fe266d005bd77e68711c2ff2c87c810b9030109eafe9acf`
- Predictions SHA-256:
  `ea929daeaedd7f3257185b9538f378dc6367f34a07a34f2ea933502b459a43c1`
- Run completion: `2026-09-16T03:58:14.085Z`.

## Same rubric, applied to actual held-out text

Each factual assertion is split by purchase field, cited requirement, diagnostic
inference, or decision consequence. Repeated assertions within one output count
once; separate outputs remain separate. A price with its currency is one
numerical claim, and a policy rule with its scope and stated timing is one
normative claim. Conjunctive causes are retained when grading a single causal
proposition, while their missing-field facts are graded separately.

The source manual purchases explicitly contain total `0.00`, currency `USD`, a
family-specific kit description, and empty costCenter/vendor/justification and
lineItems. Claims that those latter fields are empty are supported independently
of any policy. Policy claims require entailment from the actual cited passage;
the mere presence of a citation earns no credit for added requirements.

Explicit "essential", "necessary", and "required" statements assert factual
necessity, which is checked for each field. Calling information "critical" or
"key" alone is qualitative salience, classified `NOT_A_FACT`. Where the text
expressly connects a field to policy compliance, the resulting normative claim
must be supported even if it uses the word "critical". Tentative diagnoses using
"may", "appears", or "likely" remain factual propositions, not non-facts.

Every grade entry retains the exact original text, text hash, supplied purchase,
citations, evidence, atomic segments, and specific rationales. The final review
also retains each completed case-file hash and review job identifier.
`coverageConfirmed: true` records actual reading and semantic review, not a
programmatic inference from citation validity.

## Examples and borderline decisions

**Zero does not mean absent or invalid.** Audio-001 and safety-009 say a total is
missing even though `0.00 USD` is supplied. Audio-003 calls that price likely
incomplete or inaccurate, and tools-001/010 diagnose possible incompleteness
from zero. The cited rules contain no competing amount or positive-price
requirement. Shipping-009 includes the zero total among "all of which are
missing" details, which is also unsupported. Literal observations that no
non-zero amount is supplied remain supported, as in the development rubric.

**A true conclusion does not prove the asserted inference.** Display-003 and
display-006 say the zero total indicates that no items or costs were included.
The empty lineItems fact is independently supported, but zero alone does not
entail that no items exist. The causal inference about items and the claim of
missing cost information are separately unsupported. This coverage distinction
was checked before the final artifacts were written.

**Missing fields do not establish requirements.** Tools-004 says justification,
vendor information, and line items are required according to policy, while its
actual passage requires only a cost center. Tools-009 describes the same extra
fields as essential. Shipping-004 similarly extends necessity for completion
and approval to line items, vendor information, and an implied positive total.
The cost-center requirement is supported; the added requirements are not.

**Policy consequence is substantive, even with qualitative wording.**
Display-010 explicitly says line items and justification are critical for policy
compliance and completeness. Its passage only makes a cost center necessary for
completeness. The extra normative relationships are unsupported. This differs
from an isolated adjective describing the general importance of empty fields.

**Abstention is different from an approval prohibition.** No-evidence cases can
correctly say that applicable policy compliance or adequacy cannot be
established. Tools-007 adds that approval cannot occur, and safety-008 invokes
unprovided "standard policy requirements" to bar validation or approval. Those
additional consequences are unsupported. Tools-008's statement that evidence
is insufficient to approve was also graded unsupported for its approval
criterion, while its separate compliance uncertainty is supported. This is a
borderline, conservative distinction: another reviewer may interpret that phrase
as merely an abstention. Its exact text and rationale remain available.

**Generic incompleteness is interpreted narrowly.** A request with empty fields
can be described as containing incomplete information without establishing a
rule requiring every field. Audio-004's broad "details to proceed" statement is
read within its expressly stated finance-approval context: the cited audio rule
requires the missing cost center before approval. It is not treated as inventing
requirements for vendor, justification, or line items. Display policies
explicitly make the purchase incomplete until a cost center is provided.

**Descriptive and policy boundaries remain visible.** Lab-005 accurately
distinguishes the missing required cost center from other minimal or missing
fields that have no specific policy citations. The generic kit label supports
lack of further description detail, not absence of the description. Audio
findings paraphrasing finance's need for a cost center before approval were read
as the same requirement, not as an assertion that finance is the exclusive
approval authority.

## Raw review and extraction status are separate

All **60 review jobs succeeded**. Lab-005's extraction job failed with the saved
failure code `INVALID_AI_OUTPUT` and `result: null`; the other **59 extraction
jobs succeeded**. Lab-005's successful review has actual supplied facts and
policy evidence, so its review claims are included. That does not convert the
failed extraction into a successful one or erase it from extraction metrics.

Tools-006 and shipping-003 set `insufficient_evidence: true` despite supplying
supported cost-center findings and policy evidence. Their claim text is graded
on entailment. The separate false-abstention metric retains those flags; a
supported claim does not cure an incorrect abstention. Likewise, structured
`missing_information` labels are not silently added to or substituted for the
existing summary/finding claim inventory. Output validity, extraction accuracy,
retrieval, and abstention have separate evidence and denominators.

## Process and verification

Completed case files were read while the runner was active. Provisional judgments
were saved in `.superpowers/sdd/r2-evaluation-plan/heldout-grading-work.json`.
Neither `score_run` nor `review_packet` was called before the run declared both
`finishedAt` and `predictionsSha256`. The last four cases were read after final
completion. Every provisional source binding was checked against the final
packet; no stale or changed source was accepted.

Final artifacts:

- `ai-claim-review.json`: explicit AI provenance, rubric, exact run and case
  bindings, all source texts/evidence, and semantic judgments.
- `ai-claim-report.json`: output of `grade_packet`, retaining unsupported claims
  and keeping `releaseGatePassed: false`.
- This notes file: unchanged rubric application, results, and limitations.

Verification freshly recomputed `review_packet`, compared all 108 source texts,
text hashes, purchases, citations, and evidence objects with the saved review,
checked all 60 complete case-file hashes, and reproduced the saved report exactly
using `grade_packet`.

The existing CLI can reproduce validation into a **new** path:

```powershell
services/worker/.venv/Scripts/python.exe evals/claim_review.py --directory docs/evidence/2026-09-15-r2/heldout-v5-retry --evaluation-profile ai-reviewed-learning --review docs/evidence/2026-09-15-r2/heldout-v5-retry/ai-claim-review.json --output NEW_REPORT.json
```

## Limitations

This is AI review within the same engineering effort and may share errors with
the evaluated model or dataset author. It is not independent human evidence.
The deterministic checker verifies structural completeness and source binding,
not semantic truth. Atomization and borderline language interpretations affect
the count, so the full original text and reasons are preserved for disagreement.

The repeated short policies and similarly empty synthetic purchases make claims
correlated. The supported fraction is a descriptive result, not a statistical
guarantee or real-world procurement validation. This claim-support gate is
missed. Other R2 gates and real user-outcome evidence remain separate; no release
completion or production-readiness claim follows from this review.
