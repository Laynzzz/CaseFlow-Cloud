# R2 implementation map — 2026-09-16

Release status: **in progress / experimental**. The full held-out evaluation and
AI claim review are recorded; the 95% claim-support target is missed. R1 cloud
gates remain open. R3 has not started: the user's automatic continuation remains
conditional on resolving R2's actual problems and acceptance gates.

The held-out figures below describe the preserved v5 baseline. The current
development candidate uses review prompt v6 and review schema v5, with ordinary
code rejecting false missing-field reports. Extraction remains on v5. See
[the quality work](r2-review-quality.md) for separate development evidence;
development improvements do not replace the held-out baseline.

| Product step | Implemented and verified | Remaining |
| --- | --- | --- |
| Attach quote | PDF/TXT and pasted text, immutable bytes, bounded parser, preview; browser chooser upload reached indexed status | Broader browser/accessibility acceptance; actual OS dialog clicking not tested |
| Policy evidence | Indexed publication, immutable pins, access checks; text/semantic/hybrid Recall@5 each 48/48 held-out | Larger distractor corpora; no semantic advantage established by one-passage cases |
| Suggest fields | Live structured extraction, citations, arithmetic; held-out 221/240 including rejected output | Vendor 44/60; lab-005 invalid citation rejected; numerical aggregate hides errors |
| Accept suggestions | Selected fields and matching draft revision; real API and browser vendor-only acceptance | Broader browser regression |
| Cited review | All 60 held-out review jobs succeeded; correct abstention 12/12 | Claim support 360/412 (87.38%) misses 95%; false abstention 2/48 |
| Manual fallback | Browser edit saved through simulated assistant 503 and persisted after reload | Controlled manual/extraction-only/grounded task-outcome comparison |
| Spend and failures | Shared USD 10 lifetime ceiling; full ledger, rejected-output cost, unknown reservations | More precise child-failure diagnostics and cloud-host validation |
| Evaluation | Versioned 120-case reference audit, full 60-case held-out run, one 10-case repeat, all 108 outputs graded in both dev and held-out | Independent human review and broader outcome evidence remain unmeasured |

Full evidence: [held-out summary](evidence/2026-09-15-r2/heldout-summary.md).
Reference review is handled under ADR 0006; no user form completion is needed.
AI review is an experimental evidence tier, not human validation. The corrected
v2 dataset retains v1 history and only clarifies eight policy sentences.

The first held-out attempt stopped after five completed cases on a provider
subprocess error. Its underlying cause is not established. The unchanged full
rerun preserved that attempt separately and completed all cases, with one
extraction rejected for an invalid citation. Nothing was removed from accuracy
denominators. Prompt v5 and retrieval settings stayed frozen.

The ten-case repeat changed four vendor predictions: same-subset field accuracy
35/40 → 37/40. Summary wording changed in 10 cases and finding wording in 8 cases;
wording variation alone is not error. This covers one family, not global variance.

Shared lifetime budget accounting is USD 0.358652 of USD 10, including USD 0.058983
reserved for three unknown calls. The full held-out rerun cost an estimated
USD 0.077615; its repeat USD 0.013282. No fresh allowance was introduced.

The next quality work must use development evidence, preserve the reported
baseline, and avoid presenting reused held-out outputs as a new unseen test.
If held-out examples influence tuning, retire their families into development
and freeze a new test version. Unsupported summary requirements and diagnoses of
zero totals are recorded failures, not reasons to lower the target.

Architecture, decisions and measured limitations are maintained in
`docs/teaching-guide.md` and `docs/interview-prep.md`. Installed frontend-design
and Superpowers skills are documented in `docs/development-skills.md`.
