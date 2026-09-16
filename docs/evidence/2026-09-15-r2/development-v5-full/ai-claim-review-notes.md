# Development v5 full: AI semantic claim review

Reviewer: Codex AI assistant. Method: `ai-claim-review-v1`. Profile:
`ai-reviewed-learning`. `humanVerified: false`. This is delegated experimental
AI review under ADR 0006, not independent human validation. The UTC review
timestamp is recorded in `ai-claim-review.json`.

## Scope and results

The reviewer read all 108 actual inventoried outputs from
`review_packet(directory, 'ai-reviewed-learning')`: 60 summaries and 48 findings,
with each output's supplied manual purchase, actual citations, and saved evidence.
This historical run binds **synthetic-v1**, not the corrected synthetic-v2 dataset.
No reference answers, extracted proposed values, or uncited policy passages were
substituted for the manual purchase or actual evidence seen by the review job.

The manual purchases record a family-specific kit description, total `0.00`,
currency `USD`, empty vendor/costCenter/justification strings, and empty lineItems.
The corresponding cited policies are one-sentence cost-center requirements.
Cases 007 and 008 in each family have empty policy evidence and no citations.

| Measure | Result |
| --- | ---: |
| Supported factual claims | 377 |
| Unsupported factual claims | 60 |
| Factual denominator | 437 |
| Supported fraction | 86.27% |
| Non-factual qualitative segments | 12 |
| Reviewed outputs | 108 |
| Outputs containing an unsupported claim | 24 |
| Failed or missing review jobs | 0 |
| Provisional 95% claim target met | No |
| Release gate passed | No |

All 48 finding texts are supported by their actual cited rules. The unsupported
claims occur in summaries. This does not mean all of those summaries are wholly
wrong: their supported purchase facts remain in the denominator alongside their
unsupported diagnoses or added policy requirements.

| Family | Supported | Unsupported | Non-factual |
| --- | ---: | ---: | ---: |
| Equipment | 63 | 7 | 0 |
| Seating | 58 | 13 | 2 |
| Network | 68 | 15 | 2 |
| Printing | 59 | 11 | 2 |
| Lighting | 66 | 12 | 4 |
| Storage | 63 | 2 | 2 |

## Rubric and coverage

Rubric version: `ai-semantic-claims-2026-09-15-v1`, applying the claim rubric in
`evals/README.md` and plan section 12.

- Split compound statements into separate purchase-field facts, policy
  requirements, diagnoses, and approval consequences. A price and its currency
  are one numerical claim. A scoped policy rule, including its stated timing or
  purpose, is one normative claim. A causal statement with a conjunctive cause
  is one causal proposition; the component missing-field facts are separately
  graded. Do not assume that a plausible causal connection is supported.
- Count repeated assertions within one output once. Repetitions across separate
  outputs remain separate. For example, printing-005 repeats the missing cost
  center and the same cost-center policy; neither is counted twice in its summary.
- Support purchase facts from the actual supplied manualPurchase. Support policy
  claims only when the actual cited passage entails them for that purchase. A
  citation's existence does not establish support for other claims in the output.
- Mark unsupported requirements and unsupported diagnoses `UNSUPPORTED`, even
  when introduced with "may" or "appears". Those are still propositions about
  this request. `NOT_A_FACT` is reserved for qualitative salience such as calling
  information "critical", not for hiding unsupported claims behind hedges.
- Treat explicit "required", "necessary", and "essential" as assertions of
  necessity. Split necessity for each field. Missing vendor, justification, or
  line items does not establish that policy requires them. Necessity language
  is stricter than the qualitative adjective "critical".
- Retain the exact full source text, its SHA-256, purchase, citations, and evidence
  in each output's review entry. Segment text uses faithful atomic paraphrases
  or exact source text. `coverageConfirmed: true` was set after actually reading
  each output, not inferred by the grading program.

The case-by-case segment selections and exception judgments were authored by the
reviewer. Local Python helpers expanded repeated already-reviewed propositions,
attached their exact source facts, and called `grade_packet`. They did not use
keyword matching or citation presence to decide summary support. The repeated
findings were individually read; an additional assertion checked their exact
policy quotations, with the faithful singular paraphrase in lighting-010 handled
explicitly.

## Borderline judgments and examples

**Zero is supplied data.** "The total is zero" is supported. "No non-zero total"
is a narrowly true description of that value, and is not automatically treated
as a claim of invalidity. By contrast, storage-003 says the request lacks a total
amount even though `0.00` is supplied. Equipment-006 says zero conflicts with the
purchase description and makes the total ambiguous; no competing amount or
positive-price rule supports either inference. Lighting-004/005 and network-009
tentatively diagnose zero as possibly incorrect; a hedge does not supply the
missing evidence. A later reviewer may reasonably scrutinize the distinction
between describing absent positive value and implying a positive-value rule.

**Additional requirements need evidence.** Lighting-002 asserts vendor
information is required for lighting orders. The actual cited passage only
requires recording the department cost center. Network-004 extends necessity to
vendor, line items, and justification, although its cited policy only prohibits
proceeding without a cost center. Seating-001 and printing-008 use
necessary/essential language for extra fields; that asserted necessity is graded
separately from the true observation that the fields are empty.

**Policy timing cannot be added.** Equipment's cited rule explicitly says before
approval, so that deadline is supported. Seating's rule explicitly says for
finance review. Network's rule explicitly says procurement cannot proceed without
a cost center. Printing and lighting rules establish cost-center requirements
without defining extra approval prerequisites. Thus printing-001 and lighting-010
do not gain support for an approval consequence merely from the presence of a
cost-center citation. Network-010's cost-center barrier is supported, but its
separate claim that the additional fields make procurement processing incomplete
is unsupported by the actual cited rule.

**Abstention differs from prohibition.** No-evidence cases can correctly say that
policy compliance cannot be established. This review supports such narrow
statements of uncertainty. Seating-007 and network-007/008 also assert that the
request cannot be approved or processed; those consequences are unsupported
without policy evidence. General inability to evaluate adequacy is treated as
epistemic limitation, not a conclusion that the purchase is invalid.

**Description detail is distinct from a missing description.** "Description
details/completeness" is read narrowly as a lack of specifics beyond the generic
kit label, which the saved purchase demonstrates. It is not interpreted as a
claim that the description field is absent, or that policy requires a more
detailed description. This is a permissive borderline interpretation recorded
for later review.

**Generic incompleteness is distinct from policy necessity.** A statement that
the request has incomplete information can describe its empty fields or missing
required cost center. That does not establish a rule requiring every empty field,
invalidate zero, or prove an approval barrier. Printing-004's broad statement
that the request lacks critical information according to policy is supported
only in the narrow sense that the cited rule requires the missing cost center;
it is not expanded into unspoken requirements for its other empty fields.

## Artifacts and verification

- `ai-claim-review.json`: exact run hashes, explicit AI provenance, all source
  texts and evidence, all atomic segments, grades, and specific rationales.
- `ai-claim-report.json`: actual `grade_packet` output; claims and failures remain
  visible and `releaseGatePassed` remains false.
- This notes file: declared rubric, review boundaries, and ambiguous judgments.

Verification recomputed `review_packet` from the saved run, passed the saved
review into `grade_packet`, and asserted exact equality with the saved report.
It also checked every saved source text, purchase, citation, and evidence object
against the fresh packet. No source evidence, implementation, prompt, model,
dataset, or existing artifact was changed. No provider calls or commits occurred.

The existing grading CLI can independently validate the review into a **new**
output path (it refuses overwrites):

```powershell
services/worker/.venv/Scripts/python.exe evals/claim_review.py --directory docs/evidence/2026-09-15-r2/development-v5-full --evaluation-profile ai-reviewed-learning --review docs/evidence/2026-09-15-r2/development-v5-full/ai-claim-review.json --output NEW_REPORT.json
```

## Limitations

The checker establishes completeness, provenance, and hash binding, not semantic
truth. The reviewer is an AI assistant working within the same engineering
effort, so shared model or author biases remain possible. Atomization and
borderline language judgments affect counts; the full text and reasons are
retained so another reviewer can disagree without erasing the original review.

These 60 synthetic development cases are not held-out validation, independent
human evidence, real procurement policy verification, or evidence of user
outcomes. Repeated one-sentence policies and similarly empty purchases make
individual claims correlated; the reported fraction is a descriptive count,
not a statistical guarantee. All remaining R2 gates and any stronger independent
review remain separate. This run misses the provisional claim-support target.
