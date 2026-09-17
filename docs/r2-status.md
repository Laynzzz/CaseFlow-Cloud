# R2 implementation map — 2026-09-16 local / September 17 UTC

**Local functional/evaluation deliverable complete; AI remains experimental.**
The [acceptance decision](evidence/2026-09-16-r2/r2-acceptance.md) maps actual
evidence to plan.md §§3,12,17. Completion means working assisted/manual paths
and published evaluation, not passing all provisional quality targets. R1 cloud
gates remain open. R3 is the next phase under the user's existing authorization.

| Product step | Implemented and verified | Remaining limitation |
| --- | --- | --- |
| Attach quotes/policies | PDF/TXT or pasted text, immutable bytes, bounded parser, indexed previews; real browser upload | No OCR; OS dialog clicking not tested |
| Policy evidence | Publication, version pins, scoped retrieval; all three methods 48/48 fresh Recall@5 | One-passage cases do not establish ranking quality or semantic advantage |
| Suggest fields | Live typed proposals and strict source/arithmetic validation | Fresh 164/240 (68.33%) misses 90%; 19 nonliteral-citation rejections |
| Accept suggestions | Browser explicitly saved vendor/currency/items; server total USD70; old result disabled | Suggestions require human checking; a stale request can require retry |
| Cited review | 60 fresh review jobs, 463/463 AI-supported assertions, correct abstention12/12 and false0/48 | Narrow synthetic coverage; no independent human validation |
| Manual path | Browser manual editing persisted during simulated assistant503; ordinary approvals unchanged | Simulated outage, not provider-wide outage evidence |
| Complete journey | Admin setup → request → suggestions → manual completion → manager/finance → downloaded DOCX | Local only; focused keyboard/layout checks, not full accessibility certification |
| Workflow comparison | 9/9 correct drafts and assigned-mode completions across three modes | Agent-operated API self-test; no human reading/typing/time-saving measurement |
| Evaluation variability | Full60 fresh cases plus three fixed12 repeats; exact hashes, claims, failures and costs | Extraction repeat scores75%,75%,66.67%; correlated, limited categories |

The original120 v2 cases are retained unchanged as v3 development. Fresh cases
use six new layouts. Product configuration was frozen through all v3 runs:
extraction promptv5/schema4, review promptv6/schema5, GPT-4.1 mini snapshot
2025-04-14. No tuning used fresh outputs during this evaluation.

Shared accounting: **USD0.633975 / USD10**, including unchanged USD0.058983
reservations for three earlier unknown calls. The full/repeat/browser/workflow
checks added USD0.160212; no allowance was reset.

Evidence: [fresh report](evidence/2026-09-16-r2/heldout-v3-summary.md),
[repeats](evidence/2026-09-16-r2/heldout-v3-repeats.md),
[browser](evidence/2026-09-16-r2/browser-journey/README.md),
[comparison](evidence/2026-09-16-r2/workflow-comparison/README.md), and
[preserved older baseline](evidence/2026-09-15-r2/heldout-summary.md).
Architecture and interview notes remain cumulative in `teaching-guide.md` and
`interview-prep.md`. AI failures must remain visible in future demonstrations.
