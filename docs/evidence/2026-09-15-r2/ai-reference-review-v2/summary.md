# Corrected references: AI review, synthetic-v2

Date: 2026-09-15. Reviewer: Codex AI assistant. Decision: ADR 0006.
This is AI source assessment plus deterministic consistency checking, not
independent human verification, model accuracy or a completed release gate.

The original audit identified eight laboratory policies whose sentence could
mean the purchase must be completed before approval. V2 explicitly states:
"Laboratory purchase requests must include a cost center before approval."
That directly supports the expected missing-cost-center finding. The unrelated
wall-painting policies in lab-007/008 remain irrelevant and unchanged.

All other cases retain the prior source judgments. V2 changes exactly
lab-001 through lab-006, lab-009 and lab-010, and only their policy text.
Development bytes, quote facts, reference answers, splits and numerical targets
are unchanged. V1 files and historical reports remain at their original paths;
v2 is under `evals/datasets/synthetic-v2`.

`audit.json` records 120 case judgments, 480/480 matching field checks, 120
consistent initial line totals, and zero unresolved issues. Conflicting final
totals still require null, absent facts are not inferred, irrelevant policy
requires abstention, and hostile instructions have no authority. These checks
are tailored to this small synthetic dataset and cannot demonstrate model quality.

The user no longer needs to fill the original human-review form. The new runner
profile accepts complete AI reviews while distinguishing them from human review.
Case/file hashes, complete coverage, resolved findings and reviewer provenance
are checked before any live call, including in validate-only mode. The run keeps
the exact review artifact; offline scoring checks its checksum.

Reproduce from the repository root (output paths must be new):

```powershell
services/worker/.venv/Scripts/python.exe evals/audit_references.py --dataset-version synthetic-v2 --output NEW_AUDIT_JSON
node evals/run-live.mjs --validate-only --split heldout --dataset-version synthetic-v2 --evaluation-profile ai-reviewed-learning --annotation-review docs/evidence/2026-09-15-r2/ai-reference-review-v2/audit.json
services/worker/.venv/Scripts/python.exe -m pytest evals -q
node --test evals/test-dataset.mjs
```

Verification: 24 Python evaluation tests and four Node dataset/review tests pass.
Preflight selected all 60 held-out cases with zero provider calls. No product
prompt, retrieval setting or model changed in this batch. Prompt v5 remains frozen
for held-out testing. Held-out model runs, claim grading and remaining R2 evidence
are still pending. User-authorized shared lifetime spend remains USD 10.
