# Development v6 full: AI semantic claim review

Reviewer: Codex AI assistant. Method: `ai-claim-review-v1`. Profile:
`ai-reviewed-learning`. `humanVerified: false`. This is delegated experimental
AI review under ADR 0006, not independent human validation. The UTC review
timestamp is saved in `ai-claim-review.json`.

## Scope and results

The reviewer individually read all 60 summaries and 48 findings with their actual
manualPurchase, citations, and saved review evidence. The finalized inventory
comes from `review_packet(directory, 'ai-reviewed-learning')` and binds the exact
dataset and predictions hashes. This run uses **synthetic-v1**, review prompt
`purchase-review-2026-09-16-v6`, and review schema `purchase-review-v5`. Extraction
uses `purchase-assistant-2026-09-15-v5` / `purchase-assistant-v4`.

No quote, extraction proposal, reference answer, or uncited passage was
substituted for the purchase facts or evidence actually supplied to the review.
Preparatory judgments were made from successive completed development prefixes;
each extension checked previous source bindings and preserved earlier judgments.
The final artifacts were created only after the 60-case run completed and its
run manifest was finalized.

| Measure | Result |
| --- | ---: |
| Supported factual claims | 459 |
| Unsupported factual claims | 1 |
| Factual denominator | 460 |
| Supported fraction | 99.78% |
| Non-factual segments | 0 |
| Reviewed outputs | 108 |
| Outputs containing an unsupported claim | 1 |
| Failed or missing review jobs | 0 |
| Provisional 95% claim target met | Yes |
| Release gate passed | No |

| Family | Supported | Unsupported | Non-factual |
| --- | ---: | ---: | ---: |
| Equipment | 79 | 0 | 0 |
| Seating | 75 | 1 | 0 |
| Network | 75 | 0 | 0 |
| Printing | 76 | 0 | 0 |
| Lighting | 76 | 0 | 0 |
| Storage | 78 | 0 | 0 |

All 48 findings are supported by their actual cited passages. The one unsupported
proposition is in the seating-005 summary. Other supported statements in that
summary remain in the denominator.

## Unchanged rubric and coverage

Rubric version: `ai-semantic-claims-2026-09-15-v1`, unchanged from the development
v5 full review notes, applying `evals/README.md` and plan section 12.

- Split compound text into separate purchase-field facts, policy requirements,
  diagnoses, and consequences. An amount and its currency are one numerical
  claim. A scoped rule with its stated purpose or timing is one normative claim.
- Count repeated assertions within one output once. Assertions repeated across
  separate outputs remain separate. Do not add unspoken purchase-field claims
  merely because the fields exist in the input or missing_information list.
- Support purchase facts from actual manualPurchase. Support policy assertions
  only when the actual cited passage entails them for the purchase. Valid
  citations, relevant keywords, plausible advice, and hedges do not establish
  support for other assertions.
- Explicit required, necessary, and essential wording asserts necessity and
  requires evidence for each field. Key/critical alone expresses qualitative
  salience and would be `NOT_A_FACT`. This run has no such separately counted
  qualitative segments. Factual attribution to policy is not qualitative salience.
- Preserve full sourceText, SHA-256, purchase, actual citations, and saved
  evidence in every output entry. `coverageConfirmed: true` records actual review
  of the whole output. Segments are faithful atomic paraphrases or exact text.

The reviewer authored explicit per-case segment selections after reading every
new output. Local Python helpers expanded the already-reviewed propositions,
attached exact source data, and called `grade_packet`; they did not decide
semantic support by keyword matching or citation presence.

## Specific and borderline judgments

**Unsupported policy attribution remains visible.** Seating-005 says the missing
cost center and justification are relevant information for finance review
"according to policy". Its actual cited passage only states that seating
requests must include a cost center for finance review. The attribution about
justification is therefore `UNSUPPORTED`. The later sentence correctly says
there is no policy evidence regarding justification; that supported caveat does
not erase the preceding unsupported attribution. The missing justification fact
itself is supported. Repeated mentions of missing justification count once.

The cost center's stated relevance for finance review repeats the more specific
cost-center requirement in that summary and is counted once with the normative
rule. The separate diagnosis that this purchase lacks the required cost center
is supported by the empty field and the stated rule. Equipment-009 and
network-001 likewise make separate, supported applications of their cited rule
to the purchase's missing cost center.

**Zero is supplied data.** All manual purchases have total `0.00` and currency
`USD`. Statements of that amount are supported; none invent a positive-price
rule or diagnose it as invalid. Lighting-010 awkwardly coordinates a list of
absent fields with "and a total cost of 0.00 USD". The amount phrase is read as
stating the supplied total, with "no" modifying the preceding absent fields.
The exact text is retained so another reviewer can scrutinize that reading.

**Missing values and requirements differ.** The manual purchases have a
family-specific kit description, empty vendor/costCenter/justification strings,
and an empty lineItems list. Those absence statements are supported without
implying every field is required. Storage-010's "missing a valid cost center"
is supported by the completely empty field and its cited rule requiring a valid
cost center; it does not diagnose a supplied identifier as invalid.

**Policy scope and timing are preserved.** The cited policies require a cost
center for the corresponding family: equipment before approval, seating for
finance review, network before procurement can proceed, printing identifying the
requesting cost center, lighting recording the department cost center, and
storage a valid cost center on every request. The outputs add no unstated
approval timing to the printing, lighting, or storage rules.

**Abstention stays narrow.** Cases 007 and 008 in every family have empty review
evidence and no citations. Their summaries describe inability to assess policy
compliance or requirements. Each scoped absence/insufficiency statement for that
assessment counts as one proposition; no procurement prohibition is inferred.

**Do not count omitted or repeated facts.** Seating-001 omits the amount and
line-items observation; seating-004 and lighting-003/004 omit the amount;
network-002 states only the description, amount, and policy; printing-004 states
only description, amount, missing cost center, missing justification, and policy.
Printing-004's repeated missing cost center counts once. Repeated policy quotes
in seating-005, lighting-009, and storage-003/004 count once per output. Inline
chunk IDs in lighting-009 and storage-003 match their actual cited evidence and
are citation metadata, not additional policy or purchase propositions.

## Separate missing-information and operational diagnostics

All 60 outputs report exactly vendor, costCenter, justification, and lineItems
as missing. Every entry matches the actual supplied empty string or list.
**False missing-field reports: 0/240; affected cases: 0/60.** No output reports
the supplied zero total, USD currency, or kit description as missing. The full
case-by-case diagnostic is saved in `missingInformationReview` in the review
JSON. Its entries are not added to the summary/finding factual denominator.

Seating-005 and printing-005 have failed **extraction** jobs but successful
**review** jobs. Their review outputs were graded against the actual saved
manualPurchase and review evidence. Extraction failures remain separate
operational/extraction evidence; they are neither counted as failed reviews nor
erased by the high claim-support fraction. This claim review does not certify
extraction, retrieval, latency, cost, isolation, or the complete R2 release.

## Artifacts and verification

- `ai-claim-review.json`: exact dataset/output hashes, explicit AI provenance,
  all 108 exact source texts and evidence, atomic grades/rationales, and separate
  missing-information observations.
- `ai-claim-report.json`: unmodified output of `grade_packet`; the provisional
  claim target is met and `releaseGatePassed` remains false.
- This notes file: frozen rubric, reviewed scope, results, and judgment limits.

Verification rebuilt `review_packet`, checked every saved source text, text hash,
purchase, citation, and evidence object against it, and asserted exact equality
between a fresh `grade_packet` result and the saved report. It also verified all
60 recorded missing-information lists against predictions and identified the two
extraction failures separately. No provider calls, product/evaluation code edits,
or git commits occurred during this review.

For deterministic validation into a new output path:

```powershell
services/worker/.venv/Scripts/python.exe evals/claim_review.py --directory docs/evidence/2026-09-16-r2/development-v6-full --evaluation-profile ai-reviewed-learning --review docs/evidence/2026-09-16-r2/development-v6-full/ai-claim-review.json --output NEW_REPORT.json
```

## Limitations

The checker establishes completeness, provenance, and hash binding, not semantic
truth. The reviewer is an AI assistant in the same engineering effort; shared
model or author bias remains possible. Atomization and borderline wording affect
counts, and exact texts and reasons remain available for independent disagreement.
Repeated one-sentence policies and similarly empty synthetic purchases make
claims correlated. The fraction is descriptive, not a statistical guarantee.

These are 60 synthetic **development** cases. They are not a fresh held-out
evaluation, independent human review, real-world procurement validation, user
outcome evidence, or an R2 pass. No claim about a repaired prompt generalizing to
unseen policy families follows from this report. Other acceptance gates and any
future genuinely fresh evaluation remain separate.
