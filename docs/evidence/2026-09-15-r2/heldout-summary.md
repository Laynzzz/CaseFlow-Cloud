# R2 held-out evaluation — 2026-09-15–16

Status: **R2 remains experimental and incomplete.** The frozen v5 assistant meets
the aggregate extraction and retrieval targets on this synthetic split, but misses
the claim-support target. No R3 release transition is recorded.

| Measure | Full held-out result | Interpretation |
| --- | --- | --- |
| Extraction fields | 221/240 (92.08%) | Above 90% aggregate target; one rejected extraction counts as four misses |
| Vendor fields | 44/60 (73.33%) | Aggregate accuracy hides this weak field |
| Currency / total / items | 59/60 each | Includes the rejected result in every denominator |
| Recall@5 | 48/48 for text, semantic and hybrid | Single-passage corpora cannot establish a ranking advantage |
| Correct abstention | 12/12 | All deliberately irrelevant-policy cases abstained |
| False abstention | 2/48 | tools-006 and shipping-003 had applicable evidence but also declared it insufficient |
| AI-reviewed factual claims | 360/412 (87.38%) | Below the 95% target; 52 unsupported claims, 14 non-factual segments |
| Reviewed outputs | 108 | Every successful summary and finding; zero missing review jobs |
| Output rejection | 1/60 extractions | lab-005 had an invalid citation; the invalid result was not displayed |

Claims were split and judged against the actual supplied purchase and cited
passages. Supported purchase facts and policy assertions count separately;
plausible additional requirements do not receive credit. This is AI review under
ADR 0006, not independent human validation. The development run was reviewed with
the same rubric: 377/437 supported claims (86.27%). See the per-output reasons in
each run's `ai-claim-review.json` and the grading notes. Review text may be wrong
even when its citations identify real policy passages.

## Frozen configuration and provenance

`heldout-v5-retry` ran all 60 synthetic-v2 held-out cases through real OIDC,
Java API, PostgreSQL, Kafka and the Python worker. Generation used
`gpt-4.1-mini-2025-04-14`, prompt `purchase-assistant-2026-09-15-v5`, schema
`purchase-assistant-v4`. Displayed reviews used PostgreSQL full-text retrieval;
the comparison also recorded exact cosine and RRF60 rankings with the existing
`text-embedding-3-small` configuration. No product prompt/model/retrieval setting
changed after viewing these held-out results.

Each case used a separate synthetic tenant and the normal authorization path.
Review inputs were the saved manual purchase; extracted proposals were deliberately
not accepted during this diagnostic run. Therefore its empty vendor/items and zero
total describe the actual draft, not the separate quote's price. That separation
is essential when judging whether a review invents facts.

The first attempt (`heldout-v5-full`) stopped on a provider subprocess failure
after five complete cases. All its failures, missing denominators and unknown cost
reservation remain recorded; the successful rerun does not overwrite them. The
safe failure category does not establish the original low-level cause.

## Variability and cost

One predeclared repeat covered audio-001 through audio-010, spanning the five
categories within one family. Same-subset extraction changed from 35/40 to 37/40.
Four vendor values changed, all ten summary texts changed, eight finding texts
changed, and no abstention decisions changed. Different wording is not itself a
factual error. This is one narrow repeat, not a statistical estimate of variability
across the whole product. See `heldout-repeat-comparison.json` and its plan hash.
The comparator verifies matching quote content hashes, manual purchase values,
and policy content identities. All ten saved pairs passed. Missing provenance
is marked unverified, and failed jobs keep their original score denominators.

The full rerun recorded 180 settled calls for 120 jobs, including the rejected
extraction's USD 0.000830 call. Its total estimated cost was USD 0.077615; the
ten-case repeat cost USD 0.013282. Shared lifetime accounting is USD 0.358652 of
the USD 10 ceiling, including USD 0.058983 reserved for three unknown calls.
These are dated ledger estimates and reservations, not a provider invoice.

Local full-run p50/p95 were 4,266/5,858 ms for extraction calls,
1,781/2,093 ms for embedding calls, and 3,657/4,670 ms for review calls.
Job end-to-end p50/p95 was 6,092/7,848 ms across 120 jobs. Queue p50/p95 was
567/879 ms across 118 valid intervals; two negative wall-clock intervals remain
listed and excluded. Browser work and part of the repeat shared this host and
worker. These observations are not controlled performance benchmarks or user
completion times.

## Product checks and remaining gates

The browser file-input chooser accepted a real synthetic TXT fixture, and the
source reached indexed status with its text preview. A browser-only simulated
503 from the assistant did not prevent manually saving a cost-center edit; it
persisted after reload and the total stayed USD 70. No provider calls were made
by that browser test. This tests the browser chooser event, not navigating the
Windows OS dialog by mouse. See `browser-file-and-fallback.json`.

The quality miss is real: summaries add unsupported necessity/approval conditions
and infer invalidity or missingness from a supplied zero total. Keep AI explicitly
experimental. Future improvements must use development evidence, retain this
baseline, and avoid presenting reused held-out outputs as a fresh unseen test.
If held-out examples influence tuning, retire their families and freeze a new
version before claiming a new held-out score.

Remaining work includes resolving the claim-support gap, broader browser and
accessibility acceptance, manual/extraction-only/grounded task-outcome comparison,
and the separately open cloud/operations gates. No human pilot, time savings,
production readiness, or R2/R3 completion is claimed.

Offline verification passed 41 Python evaluation tests and four Node dataset
tests. Field, retrieval, operations and claim reports reproduce exactly from
the saved artifacts. Final code review found and resolved input-comparison and
Windows UTF-8 decoding gaps; no new model calls were needed for those fixes.

Reproduce offline (all output paths must be new):

```powershell
services/worker/.venv/Scripts/python.exe evals/score_run.py --directory docs/evidence/2026-09-15-r2/heldout-v5-retry --output NEW_METRICS_JSON
services/worker/.venv/Scripts/python.exe evals/claim_review.py --directory docs/evidence/2026-09-15-r2/heldout-v5-retry --evaluation-profile ai-reviewed-learning --review docs/evidence/2026-09-15-r2/heldout-v5-retry/ai-claim-review.json --output NEW_CLAIM_REPORT_JSON
services/worker/.venv/Scripts/python.exe evals/compare_repeated_run.py --baseline docs/evidence/2026-09-15-r2/heldout-v5-retry --repeat docs/evidence/2026-09-15-r2/heldout-v5-repeat-10 --plan docs/evidence/2026-09-15-r2/heldout-repeat-plan.json --output NEW_REPEAT_REPORT_JSON
services/worker/.venv/Scripts/python.exe -m pytest evals -q
node --test evals/test-dataset.mjs
```
