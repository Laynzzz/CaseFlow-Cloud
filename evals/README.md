# R2 synthetic evaluation protocol v1

Status: split and provisional gates fixed before prompt work; generated references
still require human verification. No model or retrieval quality has been measured.

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
these fields with reference answers. That runner and embedding comparison remain
unfinished; this scorer is an offline diagnostic tool.

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
