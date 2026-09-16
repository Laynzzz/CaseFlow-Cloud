# R2 evaluation execution — 2026-09-15

Spec: plan.md sections 11–12 and ADR 0006. Continue the existing implementation,
preserving the frozen prompt and synthetic split. This is an execution checklist,
not a replacement for release gates.

## Global constraints

- No product prompt/model/retrieval tuning using held-out examples or results.
- Keep the shared USD 10 lifetime model ceiling; no fresh per-run allowance.
- Use synthetic data; never print credentials or tokens. Do not push.
- AI review is explicitly labeled and never counts as independent human review.
- Keep failures and missing outputs in denominators; retain raw evidence.
- No user studies, performance outcomes or release completion may be invented.
- Commit only owned files in short, coherent commits. Other work may run alongside.

## Task 1: Add explicit AI claim-grading provenance

Files: evals/claim_review.py, evals/test_claim_review.py, evals/README.md.
Read those files first; implement only this bounded evaluation tooling change.
The human grading path remains the default. Add an explicit evaluation profile
argument to review_packet and CLI, default human-reviewed. The alternative is
ai-reviewed-learning, with method ai-claim-review-v1 and humanVerified false.
Grade validation must bind method, profile and human provenance to the packet,
alongside existing exact dataset/prediction/output hashes and complete coverage.
Keep backwards compatibility for legacy human packets/tests, without accepting
AI artifacts under the human method. Reject unknown profiles, absent reviewer,
stale hashes, missing grades, unconfirmed coverage and blank rationales.
Reports retain method, profile, reviewer, humanVerified, all counts and failures;
releaseGatePassed remains false. Limitations must correctly describe the chosen
reviewer type. The function checks structural completeness, never semantic truth.
Do not generate judgments or mark claims supported merely because citations exist.
The controller will read actual outputs and produce judgments separately.

Use meaningful red/green tests for provenance mismatch and unchanged denominators,
then run all eval Python tests. Document the AI profile command and limitations.
Commit only the three owned files; report commands/results and commit ID.
No subagents from this task, no product edits, no provider calls, no full docs edits.

## Task 2: Frozen held-out run and operational evidence

Run all 60 synthetic-v2 held-out cases through the existing authenticated API and
durable workers using prompt v5, comparison enabled and accepted AI references.
Preserve raw outputs and failed attempts. Score fields/retrieval/abstention and
export cost/job timings. Inspect provenance and the shared ledger afterward.
Repeat a predeclared fixed subset without using its results to tune.

## Task 3: Claim review and actual release status

Read every reviewed output and its actual supplied/cited evidence. Split factual
claims, record reasons, identify unsupported scope/conditions, and retain grades
bound to exact output hashes. Grade both development and held-out as AI reviews.
Report counts and limitations. Update teaching/interview notes and release map.
Review the evaluation-tooling diff; fix material findings and verify before commit.
R3 proceeds only after applicable R2 gates; missed targets remain explicit.
