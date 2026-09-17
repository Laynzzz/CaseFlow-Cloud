# Synthetic v3 reference audit

Method: `ai-reference-review-v1`, profile `ai-reviewed-learning`, under ADR 0006.
Reviewer: Codex AI assistant. **Human verified: false. Release gate passed: false.**

The assistant read all 60 new held-out quote texts, references, purchase fields,
queries and policy passages before recording judgments. No discrepancy was found.
The audit contains source-specific reasoning, field checks, integer-cent arithmetic,
policy relevance and abstention judgments for each new case. It does not score model
outputs. No paid provider calls were made, and no dataset or product files changed.

| Evidence | Count |
| --- | ---: |
| New source reviews | 60 |
| New extraction field checks | 240 |
| New arithmetic checks | 60 |
| New policy passage reviews | 60 |
| Answerable policy cases | 48 |
| Required policy abstentions | 12 |
| Unresolved competing totals requiring null total | 12 |
| Exact prior AI judgments carried forward | 120 |
| Prior held-out cases now labeled development | 60 |
| Total audit cases / field checks | 180 / 720 |

The six families are calibration, filtration, packaging, textiles, signage and
mobility. Each contributes ten cases and a distinct layout: Markdown table, XML,
JSON, CSV, nested proposal and supplier Q&A, respectively. Each category has twelve
cases: ordinary, missing fields, conflicting totals, insufficient policy and hostile
instructions. Calibration, packaging and signage require a cost center; filtration,
textiles and mobility require a justification. All six policies explicitly place
their requirement before approval. The unrelated garden passage supports neither
requirement. A missing commercial field does not prevent answering an available
policy rule, and an answerable rule does not mean the purchase is complete.

The conflict examples explicitly say that neither total supersedes the other.
Multiplying the line-item values verifies the original amount but cannot resolve
that declared conflict. Hostile appended instructions do not authorize approval,
fabrication or cross-tenant access. Empty warning references in those cases specify
no required extraction-conflict warning, not compliance with the hostile text.

## Carry-forward provenance

V3 development is verified as the byte-exact concatenation of both v2 split files.
Every copied case also matches its original case hash and the prior audit judgment.
The 120 prior judgments come from
[`ai-reference-review-v2/audit.json`](../../2026-09-15-r2/ai-reference-review-v2/audit.json),
whose SHA-256 is
`098401f2c6b0505ab626e493906317ed85d902c875d6730604ac41a2bf27e5b9`.
Original judgment contents are retained; the current split is development and added
provenance retains the original split, reviewer, timestamp and case hash. The prior
60 held-out cases were retired after tuning exposure. These are carried-forward
judgments, not a claim that 120 old cases received a fresh semantic review.

The new audit binds the exact v3 manifests and cases. The manifest pins candidate
`38fab84`, extraction prompt v5/schema v4 and review prompt v6/schema v5. Sources
were inspected only for reference auditing; no live held-out outputs were consulted.

## Reproduce integrity verification

From the repository root:

```powershell
node docs/evidence/2026-09-16-r2/ai-reference-review-v3/verify.mjs
```

The validator checks the learning-profile annotation contract, frozen file hashes,
byte-exact carry-forward, original judgment provenance, source-derived fields,
integer-cent arithmetic and recorded policy/abstention consistency. Expected output
is `status: passed`, 120 carried-forward cases, 240 new field checks, 60 arithmetic
and policy checks, 12 abstentions, 12 conflicting totals and zero discrepancies.
It rechecks recorded evidence; it does not replace semantic review or independently
establish that a policy interpretation is correct. Its source parsers are specific
to these frozen fixtures and are not production extractors.

## Limits

This remains AI-reviewed synthetic learning-project evidence, not independent
human verification, real-world model validation or an R2 release pass. The new
layouts improve fixture variety but still use single-item quotes, repeated category
patterns and two narrow policy requirements. AI reference review can share errors
with the evaluated system. Historical judgments retain the prior audit's limits.
Live extraction, retrieval, claim support, isolation, operations and user-outcome
evidence remain separate gates.
