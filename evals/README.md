# R2 synthetic evaluation protocol v1

Status: split and provisional gates fixed before prompt work; generated references
still require human verification. The live runner is implemented; provider HTTP
429 blocks successful live results. No model or retrieval quality has been measured.

## Live runner

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

Held-out execution requires `--annotation-review PATH`. The JSON must record
`status: verified`, `method: human-reference-review`, the `datasetVersion`, actual
`reviewer`, `reviewedAt`, and `files` entries for both JSONL files with the frozen
`sha256` and `reviewedCount` equal to all rows. This file must describe real human
review; filling its fields is not a substitute for reviewing the references.
No such review has yet been recorded. Automated guard tests use synthetic review
fixtures only. The runner and scorer never mark the release complete.

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
comparison remains unfinished. This scorer is an offline diagnostic tool.

Missing/failed cases stay in field and abstention denominators. A failed job does
not receive credit for a reference null. Decimal formatting is normalized, while
line order, quantities and prices are preserved. Recall considers only the first
five retrieved passages. Duplicate/unknown case IDs are rejected. Generated
summary/finding text is inventoried for manual grading, never automatically marked
supported. Reports preserve the input/dataset hashes and refuse to overwrite an
existing output. Known successful-result cost is a subtotal, not total billing;
failed/unknown calls still require ledger reconciliation.

`releaseGatePassed` remains false in these diagnostic reports. Human reference
verification, claim grading and the remaining R2 checks require separate evidence.

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
at least 90%; retrieval Recall@5 at least 90%; manually judged cited-claim support
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
