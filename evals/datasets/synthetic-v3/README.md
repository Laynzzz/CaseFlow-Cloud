# Synthetic v3: fresh inputs awaiting reference audit

This snapshot retires all 120 synthetic-v2 cases into development, preserving
their IDs, source text, purchases, queries, references, and JSONL row bytes.
The previous development file is concatenated with the previous held-out file.
The v1 and v2 snapshots and their prior evidence remain unchanged. Their cases
cannot provide fresh held-out evidence after output inspection and tuning.

The 60 new held-out cases use six disjoint document/template families, each with
two ordinary cases, two cases missing vendor/currency, two unresolved total
conflicts, two unanswerable policy questions, and two hostile-instruction quotes.

| Family | Document layout | Required purchase field |
| --- | --- | --- |
| calibration | Markdown table with a supplier header and settlement footer | costCenter |
| filtration | Nested XML vendor offer | justification |
| packaging | JSON offer object and goods array | costCenter |
| textiles | CSV header and single goods row | justification |
| signage | Nested bullet proposal grouped by party, goods, and settlement | costCenter |
| mobility | Written buyer/supplier question-and-answer quotation | justification |

All identities and goods are synthetic. Each quote has one line item, an explicit
currency or explicit missing currency, and decimal prices calculated with Python
Decimal. There is no tax, discount, shipping charge, or inferred procurement law.
An unresolved amendment has two explicitly unconfirmed totals and a null total
reference. Missing vendor/currency references are null; JSON null and the text
`[not supplied]` mean absence. Unanswerable cases have an unrelated passage and
`relevantPassages: []`. Hostile instructions are untrusted source content, never
instructions to the evaluator or application.

Both purchase fields are null in the fixtures. The current live runner creates
`costCenter` from the fixture (null becomes empty) and an empty `justification`;
these requirements therefore test fields actually present in the purchase sent
to review. Policies vary their wording, but remain simple synthetic internal
requirements. The same missing-fact/conflict/abstention pattern and one-passage
retrieval corpus deliberately retain v2's narrow difficulty. Formatting differs;
comparable model difficulty is an intended design property, not a measured claim.

## Candidate freeze and audit boundary

The candidate is frozen at commit `38fab84`: extraction prompt
`purchase-assistant-2026-09-15-v5`, extraction schema `purchase-assistant-v4`,
review prompt `purchase-review-2026-09-16-v6`, and review schema
`purchase-review-v5`. This change modifies dataset construction and version
loading only; it does not change product prompts, schemas, model, or retrieval.
Targets remain 90% extraction, 90% Recall@5, and 95% supported cited claims.

The manifest deliberately says `awaiting-versioned-review`. Construction and
checksum tests do not constitute reference review. Before any live execution,
a separate reviewer must inspect every source, expected extracted field,
arithmetic, relevant policy passage, and expected abstention, then record an
exact-hash-bound audit with actual case judgments. ADR 0006 permits explicitly
labeled AI review; it does not imply independent human validation. Any unresolved
reference ambiguity must be resolved and the input version frozen before outputs
are examined. Do not tune references, inputs, prompts, or retrieval after viewing
held-out outputs; tuning exposure retires that held-out snapshot.

No provider calls or scores are produced by constructing this snapshot. Quality,
grounding, model variability, and R2 release acceptance remain unmeasured here.
The single-passage corpus is a limited retrieval test, and synthetic templates
cannot establish generalization to real vendor documents. AI reference review
and AI claim grading share possible errors and are weaker than independent
human validation. The shared lifetime live-testing ceiling remains USD 10.

## Reproducible offline checks

From the repository root on Windows:

```powershell
services/worker/.venv/Scripts/python.exe -m pytest evals/test_build_fresh_dataset.py evals/test_scoring.py -q
node --test evals/test-dataset.mjs evals/test-fresh-dataset.mjs
py -3.12 evals/scoring.py --dataset-version synthetic-v3 --validate-dataset
```

`evals/build_fresh_dataset.py` deterministically constructs the three frozen data
files from v2 in a new directory and refuses to overwrite any existing v3
directory. Tests rebuild into temporary directories and check byte preservation.
The README is documentation, separate from those checksummed data files.
