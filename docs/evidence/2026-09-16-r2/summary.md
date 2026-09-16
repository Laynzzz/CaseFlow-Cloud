# R2 review improvements: development assessment

Date: 2026-09-16. **Development evidence only; R2 remains experimental.**
The previous v5 held-out result is preserved and has not been rerun or relabeled
as a new unseen test. No R3 transition is recorded.

## What changed

Review prompt v6 separates supplied purchase facts from cited policy obligations.
A supplied zero is present data; an empty field does not itself establish a policy
requirement. Extraction instructions remain on v5. Each task records its actual
prompt version and hash.

The first ten development cases exposed a separate error: the model listed the
already populated description as missing. Review schema v5 now constrains missing
field names to the actual empty/absent purchase fields, and post-validation
rejects a false report. Failed output remains recorded with its cost. No ordinary
code claims to prove semantic policy entailment. See [the design and trade-offs](../../r2-review-quality.md).

## Full sixty-case result

| Measure | Previous development v5 | Current development v6 |
| --- | ---: | ---: |
| AI-reviewed factual support | 377/437 (86.27%) | 459/460 (99.78%) |
| Unsupported factual claims | 60 | 1 |
| Reviewed summaries/findings | 108 | 108 |
| Extraction fields | 225/240 (93.75%) | 217/240 (90.42%) |
| Text Recall@5 | 48/48 | 48/48 |
| Correct abstention | 12/12 | 12/12 |
| False abstention | 0/48 | 0/48 |
| Failed/missing reviews | 0 | 0 |

All 60 current reviews succeeded. All 48 dedicated findings were supported.
The single unsupported claim is in seating-005: the summary attributes
justification's relevance to a policy that only addresses cost center. A later
caveat does not erase that earlier assertion. Separately, all 240 entries in
`missing_information` identify actually missing fields; no false reports were found.

Both extraction rejections, seating-005 and printing-005, had invalid citations.
They count as four field misses each, including fields whose reference is null;
a failed result is not a correct null prediction. Current vendor accuracy is
46/60; currency and total are each 58/60, and items 55/60. The aggregate above
90% does not mean every field meets that target. All failures remain visible.

Quote content hashes, manual purchases, policy content identities, retrieved
evidence text, review retrieval methods/queries and generation models match the
previous development run across all 60 cases. The new run did not request the
optional embedding comparison. Extraction prompt/schema are unchanged, yet
sampling produced different results. This is a single before/after observation,
not an isolated estimate of causal effect or a performance benchmark.

The claim rubric is unchanged and explicitly AI-reviewed: `humanVerified: false`.
Different generated assertions create different factual denominators. The
versioned synthetic development examples are correlated and already used for
development; the result is not real-world validation or independent human review.
Source hashes and exact grading reasons are in the
[claim review](development-v6-full/ai-claim-review.json), with
[rubric details](development-v6-full/ai-claim-review-notes.md) and
[comparison hashes](development-comparison.json).

## Smaller checks and cost

| Check | Result | Estimated call cost |
| --- | --- | ---: |
| Prompt-only first ten cases | 66/66 supported claims; one false missing-field report retained | USD 0.014247 |
| First ten with field validation | 78/78 supported claims; zero false missing-field reports | USD 0.014375 |
| Full sixty with field validation | Results above; 120 settled calls, including rejected extractions | USD 0.085784 |
| Complete purchase API journey | USD 4,200 draft returned no missing fields, cited its policy and stayed unchanged | USD 0.000705 |

Shared lifetime accounting is **USD 0.473763 of USD 10**, including the previously
reserved USD 0.058983 for three unknown calls. This batch adds no new unknown
charges or allowance. These are local usage estimates and reservations, not a
provider invoice. [Budget snapshot](budget.json); individual calls and timings
are stored in each run directory.

Full-run provider p50/p95 were 4,562/6,813 ms for extraction and 4,187/5,890 ms
for review. Job end-to-end p50/p95 was 5,513/7,590 ms across 120 jobs. No negative
wall-clock intervals were observed in this run. These are local observations;
the complete-purchase check briefly shared the worker near the end of the run.
No user time-saving claim follows.

## Verification and remaining work

Worker tests: 67 passed. Evaluation tests: 42 passed. Code review found and fixed
the repetition tool's assumption that extraction and review share one prompt
version. The final review found no further actionable issue. The live complete
purchase check exercised an empty allowed missing-field list through the actual
provider/API path. It is an automated API journey, not browser or user-pilot evidence.

All 108 output/source/evidence bindings, the claim report, field/retrieval report
and operations report reproduce exactly from the saved artifacts. Source and
prediction hashes are retained. Reproduce offline with the commands in
[the evaluation README](../../../evals/README.md); use new output filenames.
To rerun the one-case live check through the shared budget:

```powershell
node tests/e2e/review-complete-live.mjs --live --output NEW_JOURNEY_JSON
```

Next acceptance work needs a fresh frozen test assessment of the current
candidate, broader browser/accessibility acceptance and the separately tracked
workflow-outcome/cloud/operations gates. Preserve the previous baseline and do
not use its missed score or this development success to hide remaining gaps.
