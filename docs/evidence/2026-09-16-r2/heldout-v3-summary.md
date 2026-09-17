# Fresh held-out assessment: synthetic v3

**Extraction missed its target: 164/240 fields (68.33%) against 90%.** All 19
rejected extraction jobs had nonliteral source quotations and count as four
incorrect fields each. The 41 accepted extractions matched all four references.
The assistant remains experimental; no production or real-world quality claim.

The full run used 60 fresh synthetic cases in six new quote-layout families,
frozen before calls. All 120 previous v2 cases were retired unchanged into v3
development. The review/extraction configuration remained frozen at the product
candidate `38fab84`: model `gpt-4.1-mini-2025-04-14`, extraction prompt v5/schema
v4, review prompt v6/schema v5. Actual full IDs, hashes and declaration are in
[the plan](heldout-v3-plan.json) and [run metadata](heldout-v3-full/run.json).
The run lasted 2026-09-17 02:33:55–02:52:00 UTC and did not stop early.

## Actual full-run results

| Measure | Observed result | Frozen target |
| --- | ---: | ---: |
| Extraction field match | 164/240 (68.33%) | 90% — missed |
| Vendor / currency / total / line items | 41/60 for each | Aggregate above |
| Text retrieval Recall@5 | 48/48 | 90% — met |
| Semantic / hybrid comparison Recall@5 | 48/48 each | No advantage demonstrated |
| AI-judged supported factual claims | 463/463 (100%) | 95% — met in this synthetic AI review |
| Correct abstention | 12/12 | Report actual counts |
| False abstention | 0/48 | Report actual counts |
| Failed extraction / review jobs | 19/60 / 0/60 | Failures retained |
| False missing-information entries | 0/240 | Separate diagnostic |

The [metrics](heldout-v3-full/metrics.json),
[108 exact claim judgments](heldout-v3-full/ai-claim-review.json),
[claim report](heldout-v3-full/ai-claim-report.json) and
[semantic notes](heldout-v3-full/claim-audit-notes.md) preserve the actual outputs,
atomic assertions and evidence. The claim rubric is unchanged:
`ai-semantic-claims-2026-09-15-v1`. The reviewing AI read 60 summaries and 48
findings; the root assistant also read all those texts. This is **AI-reviewed,
not independently human-verified**. Report validators establish integrity and
coverage, not the truth of semantic judgments.

| Extraction category | Correct fields / selected fields |
| --- | ---: |
| Ordinary | 40/48 |
| Missing fields | 28/48 |
| Conflicting totals | 16/48 |
| Insufficient policy | 36/48 |
| Hostile instructions | 44/48 |

## What failed and why

The recorded ledger codes were `INVALID_CITATION` for all 19 rejections. An
[offline audit](heldout-v3-full/rejected-quotes.json) matched original quote
hashes and recorded output hashes, then found at least one nonliteral quote in
every rejected output. Examples include removing JSON whitespace, combining
nonadjacent supplier answers, joining CSV headers to values, and eliding XML
between conflicting amounts. Even citations attached to null values are checked.
The runtime rejected each entire extraction; the score gives no credit for its
other fields. No citations were repaired after the run and no threshold changed.

The earlier v2 extraction result (221/240) and v3 result use different sources;
they are not a controlled before/after improvement experiment. V3 exposes a
formatting-generalization weakness hidden by the older, simpler layouts. The
old baseline and development results remain in their original directories.

## Cost and operations

[Selected ledger](heldout-v3-full/calls.json): 180 settled calls for 120 jobs,
including 60 retrieval-comparison embedding calls. Total USD **0.092924**;
USD **0.016240** of that was spent on rejected extractions. No new unknown call
was recorded in this run. The existing shared USD 10 ceiling was not reset.

[Operations report](heldout-v3-full/operations.json): model/transport p50/p95
4,639/6,797 ms for extraction and 4,171/6,203 ms for review; queue delay
532/891 ms and end-to-end job time 6,570/9,160 ms. These are local observations
under concurrent browser, workflow, repeat and targeted-test activity, not a
controlled load benchmark or human completion-time study.

## Limits

There are only six synthetic layouts, one line item per quote and two narrow
policy requirements. Each answerable case has one relevant policy passage,
so perfect retrieval recall does not establish robust ranking or superiority
over text search. Most review inputs are similarly incomplete drafts: extraction
proposals are deliberately not accepted during this quality run. The complete
purchase check, browser journey and workflow comparison address different paths,
not broad real-world coverage. Synthetic correlated cases and AI grading can
share systematic errors. All raw scorer artifacts keep `releaseGatePassed:false`;
overall release acceptance is a separate documented decision.

The predeclared fixed-subset repetitions are separate immutable runs under
`heldout-v3-repeat-1`, `heldout-v3-repeat-2` and `heldout-v3-repeat-3`; their
comparisons retain the same 12-case denominator and frozen source identities.
