# Review v6 prompt-only development check

All ten summaries and eight policy findings were read against their actual saved
purchase, citations and retrieved evidence. The unchanged rubric is
`ai-semantic-claims-2026-09-15-v1`. Reviewer: Codex AI assistant;
`ai-reviewed-learning`, `humanVerified: false`. This is experimental AI judgment,
not independent human validation.

The review counted 66 supported factual claims, zero unsupported claims, and
zero non-factual segments across 18 outputs. Individual purchase fields are
separate assertions; total and currency form one numerical assertion. Each
finding restates the actual scoped cost-center rule. Summaries 007 and 008 state
the absence of policy evidence without inventing an approval prohibition.
Summary 009 contains purchase observations only; its separate finding supplies
the policy requirement. Summary 010 states description, total, absent cost
center, and the scoped rule. All other sentences are covered in the saved grades.

The exact same ten cases in the historical v5 development review scored 63/70
supported claims (90%). The new score is 66/66; denominators differ because the
model made different assertions. Quote hashes, manual purchase objects and
policy content identities match across all ten pairs. These are one-family
development observations, not a statistically established improvement or a
fresh held-out result. All original 60-case held-out results remain unchanged.

**Separate observed defect:** equipment-001 lists `description` in
`missing_information`, despite the saved description being `Equipment kit`.
The established claim rubric inventories summary/finding text, so its 66/66
score does not cover this list. Preserve this defect beside the score rather
than interpreting that score as complete output correctness. It motivated a
subsequent deterministic field check and review schema v5, tested separately.

This run used review prompt `purchase-review-2026-09-16-v6` with schema
`purchase-assistant-v4`. Extraction retained prompt v5. All 20 jobs/calls
succeeded: 40/40 fields, 8/8 text Recall@5, 2/2 correct abstentions and 0/8 false
abstentions. Estimated call cost: USD 0.014247. No embedding comparison was
requested; retrieval/model configuration otherwise stayed unchanged.

The source records, hash-bound judgments, operation timings and raw call ledger
are stored alongside this note. The original prompt-only run is not relabeled
as evidence for the later field-validation guard.
