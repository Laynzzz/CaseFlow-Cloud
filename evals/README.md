# R2 synthetic evaluation protocol v1

Status: development runs and source audits are recorded. Under user-delegated
ADR 0006, corrected synthetic-v2 has an AI reference review of all 120 cases.
Historical v1 files and reports remain unchanged. Held-out results and claim
support are still pending. AI-reviewed results remain experimental.

Preflight the complete review with zero provider calls:

```powershell
node evals/run-live.mjs --validate-only --split heldout --dataset-version synthetic-v2 --evaluation-profile ai-reviewed-learning --annotation-review docs/evidence/2026-09-15-r2/ai-reference-review-v2/audit.json
```

For an authorized live run, replace `--validate-only` with `--live`, add
`--compare-retrieval` and `--output NEW_DIRECTORY`. The shared USD 10 cap applies.
Each run saves the review artifact and checksum; scoring loads the declared
version and checks prediction/review hashes. Original root files are v1; v2 lives
in `datasets/synthetic-v2`. `version_references.py` reproduces v2 in a checkout
without that directory and refuses overwrites. Only eight policy passages change.

## Live runner

Add `--compare-retrieval` to record full-text, semantic and hybrid rankings on
the same runtime query and authorized corpus. The displayed review still uses
full-text evidence. `score_run.py` includes paired Recall@5, missing comparisons,
component timing and known embedding cost. The provider call export includes
both the generation and embedding calls for each selected review job.

`node evals/run-retrieval-challenges.mjs --live --output NEW_DIRECTORY` runs three
separate author-defined development probes with eight distractors per relevant
policy. These probes are explicitly outside the frozen held-out split; their
references also await human review. They help diagnose ranking behavior beyond
the primary dataset's mostly single-passage corpora. Never combine their scores
with the held-out denominator or describe them as independently validated quality.

`node evals/run-live.mjs --validate-only --split development --limit 2` checks the
frozen files and selection without signing in, creating records or calling AI.

After provider access works, an authorized run is:

```powershell
node evals/run-live.mjs --live --split development --limit 2 --output docs/evidence/2026-09-15-r2/development-first
```

The directory must be new. Each case uses an isolated synthetic tenant and the
normal API, Kafka and worker pipeline. All tenants share the existing global USD
10 lifetime ceiling; the runner never enables or resets a budget. It uses the
first N rows in frozen file order, stops on provider/budget failures, and preserves
job IDs before polling. Partial runs remain partial; score the full split so absent
cases stay in denominators. Do not infer suite accuracy from a two-case smoke run.

Each case file records actual jobs, source metadata/chunks, source-to-annotation
mapping and the supplied manual purchase. Proposed fields are not accepted in this
diagnostic run; review sees the same manual facts across cases. The separate
`tests/e2e/assistant-live.mjs` checks acceptance. Quote extraction excludes draft
defaults from provider input. Retrieval stores query and an explicit ranked chunk
array because PostgreSQL JSONB object key order cannot represent search rank.

Held-out execution requires `--annotation-review PATH`. The default human profile requires
`status: verified`, `method: human-reference-review`, the `datasetVersion`, actual
`reviewer`, `reviewedAt`, and `files` entries for both JSONL files with the frozen
`sha256` and `reviewedCount` equal to all rows. This file must describe real human
review; filling its fields is not a substitute for reviewing the references.
No human review has been recorded. The explicit `ai-reviewed-learning` profile
accepts method `ai-reference-review-v1`, status `ai-reviewed`, the matching
profile, `humanVerified: false`, and exact per-case checksums with no unresolved
issues. Both profiles require all rows and frozen file hashes. AI review cannot
pass the human profile. Neither runner nor scorer marks the release complete.

Create a human review packet with
`services/worker/.venv/Scripts/python.exe evals/build-review-page.py --output NEW_HTML`.
The page contains all frozen quotes, policies and expected answers, starts with
no approvals, and allows a reviewer to save/import progress. A correction or an
unchecked case keeps the exported review incomplete. It makes no model calls and
does not send data to a server. Its downloaded review file can be passed to the
held-out runner only after an actual person has finished checking the references.

To score a completed runner manifest's preselected first-N scope:
`services/worker/.venv/Scripts/python.exe evals/score_run.py --directory RUN_DIRECTORY --output NEW_REPORT_JSON`.
This verifies dataset/prediction hashes and frozen first-N selection. Missing jobs
within that preselected scope remain failures; this is a diagnostic subset report,
not a full-split or release result. The original `scoring.py` CLI scores the full
split regardless of how many records were supplied.

## Offline validation and diagnostic scoring

`services/worker/.venv/Scripts/python.exe evals/scoring.py --validate-dataset`
checks file hashes, counts, unique IDs, annotated passage references and family
separation. It makes no provider calls and reports no AI quality score.

`services/worker/.venv/Scripts/python.exe -m pytest evals/test_scoring.py -q`
checks scoring behavior using synthetic output fixtures.

For actual recorded outputs:

```powershell
services/worker/.venv/Scripts/python.exe evals/scoring.py --split development --predictions PATH_TO_RUN_JSONL --output PATH_TO_NEW_REPORT_JSON
```

Each JSONL record contains dataset `id`, `extraction` and `review` job responses
(including `status` and `result`), and ordered `retrievedPassageIds` mapped from
actual retrieved source/chunk IDs to this dataset's annotated passage IDs. The
live runner must retain the mapping and raw source/job provenance. Do not fill
these fields with reference answers. The live runner writes this format; embedding
comparison is recorded when explicitly enabled. This scorer is an offline diagnostic tool.

Missing/failed cases stay in field and abstention denominators. A failed job does
not receive credit for a reference null. Decimal formatting is normalized, while
line order, quantities and prices are preserved. Recall considers only the first
five retrieved passages. Duplicate/unknown case IDs are rejected. Generated
summary/finding text is inventoried for manual grading, never automatically marked
supported. Reports preserve the input/dataset hashes and refuse to overwrite an
existing output. Known successful-result cost is a subtotal, not total billing;
failed/unknown calls still require ledger reconciliation.

`releaseGatePassed` remains false in these diagnostic reports. Reference review,
claim grading and remaining R2 checks require separate evidence and explicit
AI/human reviewer provenance. Independent human verification is not recorded.

`python evals/build_dataset.py` creates 120 synthetic cases: 60 development and 60
held out, with disjoint quote/policy families. Checked-in JSONL files and SHA-256
manifest are the input contract. Do not tune prompts on held-out outputs. If a
held-out case influences tuning, retire that family to development and create a
new dataset version. Rebuilding must reproduce the checked-in manifest.

Each family has two cases in each category: ordinary, missing fields, conflicting
totals, insufficient policy evidence, and hostile document instructions. The
references deliberately preserve nulls and expected abstentions. These simple
fixtures are a starting synthetic benchmark, not evidence about real documents.

Before the first held-out run, a reviewer must check each source and reference,
record reviewer/date/corrections in a versioned annotation review file, and freeze
the corrected manifest. Programmatic consistency checks are not manual review.
The runner must refuse a release report while annotation review is incomplete.

Frozen provisional gates from plan.md: extraction normalized field exact match
at least 90%; retrieval Recall@5 at least 90%; rubric-judged cited-claim support
at least 95%. Report numerator/denominator, missing-value accuracy, per-category
failures, false and correct abstention, schema/citation failures, and uncertainty.

Claim rubric: supported only when the cited passage entails the whole factual
claim for the pinned purchase and policy version. Merely existing citations,
relevant keywords, plausible advice, or model self-ratings do not count. Split
compound claims before grading. An unanswerable policy question must abstain;
missing one purchase field should not erase other supported extracted fields.

Run text search and embedding/hybrid retrieval on identical questions, compare
manual / extraction-only / grounded workflows, and repeat fixed IDs 001 and 006
in each held-out family three times. Save raw synthetic responses, immutable
source/model/prompt/schema hashes, timing, tokens, retries, estimated cost and
dated prices. No inferred zero cost when usage is unavailable. Live runs require
an explicit budget and provider configuration. Mock CI checks validate plumbing
and permissions; they cannot satisfy quality gates or user-outcome claims.

Supplementary retrieval probes use nine policy passages per query, including
eight distractors. They are development diagnostics outside the frozen 60/60
split. Score them with `python evals/score_retrieval_challenges.py --directory
RUN_DIRECTORY --output NEW_REPORT.json`. The scorer verifies dataset/prediction
hashes and uses predeclared policy IDs from the fixture, never answers supplied
by the prediction record. Missing cases remain in denominators. These three
author-defined examples cannot establish general semantic quality.

For actual claim grading, create an offline form with
`python evals/build-claim-review-page.py --directory RUN_DIRECTORY --output NEW_PAGE.html`.
It displays each recorded finding/summary with the saved purchase and evidence.
The reviewer splits compound text into individual claims, chooses supported /
unsupported / not factual, records a reason, and confirms complete coverage.
Nothing starts graded. Export/import progress is bound to the run and text hashes.
After an actual person returns the completed file, run
`python evals/claim_review.py --directory RUN_DIRECTORY --review HUMAN_REVIEW.json --output NEW_REPORT.json`.
Missing, ungraded or mismatched outputs are rejected. Unit-test grades are explicit
synthetic fixtures and cannot be used as human evidence. The scorer checks record
completeness; it cannot verify the truth of the human's judgment or establish R2
completion by itself.

ADR 0006 also permits explicitly labeled AI claim grading for this learning-project
evaluation. Use
`python evals/claim_review.py --directory RUN_DIRECTORY --evaluation-profile ai-reviewed-learning --review AI_REVIEW.json --output NEW_REPORT.json`.
The review must declare `method: ai-claim-review-v1`, `profile: ai-reviewed-learning`,
`humanVerified: false`, an actual reviewer identifier and review date, and grades for
every inventoried output. The default remains `human-reviewed` with method
`human-claim-review-v1`; legacy human review files remain accepted. Method, profile,
human provenance, run hashes, output text hashes and complete coverage are bound
together, so an AI artifact cannot pass as human-reviewed. Both report types keep
their provenance, counts and failures and leave `releaseGatePassed` false. AI grading
is experimental evidence that may share errors with the evaluated system, while the
validator checks structural completeness rather than semantic truth. Citations alone
never establish claim support.

Local operational observations can be reproduced with
`python services/worker/tools/export_job_timings.py --records RUN_DIRECTORY/predictions.jsonl --output RUN_DIRECTORY/job-timings.json`
after loading the development environment, followed by
`python evals/report_operations.py --directory RUN_DIRECTORY --output NEW_OPERATIONS.json`.
The call ledger export must already exist as `calls.json`. These report nearest-rank
p50/p95 with counts for provider intervals, first-claim queue delay and terminal
API completion. Provider intervals include transport and child startup, not just
inference. Negative wall-clock intervals are explicitly listed and excluded, never
changed to zero. Local sequential observations are not load benchmarks or evidence
of user time savings.
