# 0006: Delegated AI review for the learning-project evaluation

Status: accepted 2026-09-15, following the user's instruction to handle the
reference review and make the necessary decisions without further confirmation.

## Decision

Allow explicitly labeled AI reference review and AI claim grading for this
learning project's experimental R2 evaluation. The assistant reads source facts
and policy meaning, records judgments and reasons, and uses deterministic checks
to catch inconsistencies. This replaces the requirement for the user to manually
complete the reference-review form. It does not create independent human evidence.

Keep the human-review path for a future independent assessment. AI artifacts must
identify their method and reviewer, set `humanVerified: false`, bind exact dataset
and output hashes, cover every selected case/claim, and retain unresolved issues.
Only an explicitly selected `ai-reviewed-learning` evaluation profile may accept
them. Incomplete or stale reviews still block held-out execution. Neither profile
automatically passes the entire R2 release gate.

Correct the ambiguous laboratory policy in eight cases in `synthetic-v2`, before
the first held-out run. Preserve `synthetic-v1` and all its historical evidence.
The correction makes the intended cost-center requirement explicit; it changes
no quote, reference answer, split, target or product prompt. Reading held-out
sources for reference auditing is not permission to tune against their outputs.
Prompt v5 and the current retrieval settings remain frozen for held-out testing.

Retain the 90% extraction, 90% Recall@5 and 95% supported-claim targets, all
failure denominators, isolation checks, budget limits and remaining release gates.
AI grading must assess each factual statement against its actual supplied facts
and cited passage; citation presence alone earns no credit. Actual human studies,
consent and user-outcome measurements cannot be synthesized by an assistant.

## Trade-offs and boundaries

This removes a manual bottleneck and gives the user a reproducible evaluation
without requiring them to grade 120 cases. AI-assisted reference checking and
grading can share errors with the system being evaluated. Consequently all such
results remain synthetic, AI-reviewed, experimental evidence, not independent
validation or a production-readiness claim. A later independent human review can
disagree and must be retained alongside the original judgments.

The delegation concerns engineering and evaluation decisions. Purchase approvals
inside CaseFlow still require the authorized human approvers; AI cannot approve
requests. The existing USD 10 shared lifetime model budget remains unchanged.
