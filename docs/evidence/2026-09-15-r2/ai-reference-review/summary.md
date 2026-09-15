# AI reference review — 2026-09-15

Requested by the user and performed by the Codex AI assistant. This is **AI review,
not human verification**. No human checkboxes were selected and no provider calls
were made. The audit covers all 120 frozen synthetic-v1 cases, including the 60
held-out sources for annotation review only. Product prompts and retrieval settings
were not changed, and no held-out model predictions were generated or consulted.

## Findings

- All 480 vendor/currency/total/item references match the source-derived fixture
  values. This is a reference consistency result, **not 100% model accuracy**.
- All 120 original quote totals equal quantity times unit price. In the 24
  conflicting-total cases, the extra correction is explicitly unresolved, so the
  reference appropriately leaves the extracted total null and records a warning.
- The 24 missing-field cases correctly leave vendor and currency null. A stated
  numeric total can still be extracted without inventing its currency.
- The 24 insufficient-policy cases supply only a wall-painting rule. Their empty
  relevant-passage lists and expected abstention are appropriate.
- The 24 hostile-instruction cases retain the actual purchase facts. Their
  appended instructions do not authorize inventing values, approval or disclosure.
- No discrepancy was identified in 112 cases. **Eight laboratory cases need a
  policy wording clarification**: lab-001 through lab-006, lab-009 and lab-010.

## Proposed clarification

Current policy:

> Laboratory purchases lacking a cost center must be completed before approval.

This appears intended to require completion of missing purchase information, but
it literally says the *purchases* must be completed. It does not clearly identify
what must be supplied. Its expected answer is plausible, but the fixture should
not penalize reasonable interpretations of ambiguous wording.

Proposed replacement:

> Laboratory purchase requests must include a cost center before approval.

This is a source-wording correction proposal, not a proven arithmetic or field-label
error. The current frozen files have **not** been edited. Applying it requires a
new dataset version/hash and a fresh review artifact; old run evidence must remain
bound to synthetic-v1. lab-007 and lab-008 use the unrelated painting policy and
are unaffected.

## Other limits

Supplier-name numeric suffixes are part of the quoted names and should not be
dropped. Unlabelled headers, especially the storage layout, still make extraction
harder. Several policies require a cost center without expressly specifying the
approval timing; a review may state the requirement but must not invent a deadline.

Despite different family wording, the dataset repeats one cost-center rule and
one-item quote structures. It tests those narrow scenarios, not general procurement
reasoning, complex tables, multilingual documents or real-world reliability.

The [row-by-row audit](audit.json) combines the assistant's source/reference
assessment with reproducible, fixture-specific parsing and decimal checks.
`evals/audit_references.py` is an audit helper only: it is not used in the product
extractor or model evaluation. Six checker tests include deliberately changed
reference values and a contradictory policy to verify that problems are detected.

The plan's human-review requirement remains unchanged. This audit
reduces review work and identifies the concrete clarification; it does not grant
the held-out runner a human-verification credential or complete R2.
