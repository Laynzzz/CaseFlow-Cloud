# R2 synthetic evaluation protocol v1

Status: split and provisional gates fixed before prompt work; generated references
still require human verification. No model or retrieval quality has been measured.

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
