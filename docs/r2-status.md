# R2 implementation map — 2026-09-15

Release status: **in progress / experimental**. R1 cloud gates also remain open.
User direction: after R2 passes its gates, continue directly into R3 without
another confirmation unless an actual unresolved problem prevents the transition.

| Product step | Implemented | Verified so far | Remaining |
| --- | --- | --- | --- |
| Attach a vendor quote | PDF/TXT or pasted text, immutable bytes, bounded parsing, text preview | Real API/storage/worker checks and browser pasted-TXT upload; compressed-stream and memory limits | Native file-picker selection remains unverified; broader browser regression |
| Publish purchasing policies | Indexed publication, deactivation, immutable case pins; edit pasted text before upload | Real API/SQL invariants and browser source text/search | Broader history/browser regressions |
| Find policy evidence | Authorized full-text baseline plus opt-in semantic/hybrid comparison | All methods 48/48 in simple dev corpora; three distractor probes: text 0/3, semantic 3/3, hybrid 0/3 | Human-verified held-out comparison; larger and more realistic corpora |
| Suggest purchase details | Live provider, strict schema, citations, arithmetic, durable jobs | Full dev rerun 225/240 fields; browser extraction and acceptance | Vendor accuracy remains 48/60; held-out evaluation |
| Accept selected suggestions | Current-versus-proposed UI, matching-revision acceptance | SQL and API replay tests; browser vendor-only acceptance preserves unselected items/total | Broader browser regression |
| Generate a cited review | Fixed facts/evidence pipeline, abstention and citation checks | Real dev jobs; correct abstention 12/12, false abstention 0/48 | Human claim-support grading and held-out results |
| Control AI spend | Shared lifetime/tenant-day ceilings, unknown reservations, bounded provider child | Real generation/embedding calls, revoked/stale cache writes, timeout termination, credential exclusion | Cloud-host validation and broader failure matrix |
| Demonstrate quality | Frozen 60/60 split, scorers, reference and claim review forms, timing/cost exporters | Two complete 60-case development runs, raw outputs/failures, 58 worker and 17 eval checks | Reference verification, held-out results/repeats, claim grades and manual-versus-assisted outcome measurements |

The user resolved provider billing, and the live extraction/acceptance/review
journey now passes. Initial failures remain in evidence: HTTP 429, a malformed
decimal total, and a malformed citation ID. Output constraints were tightened
using development cases only. The ledger retains USD 0.039322 for the two earlier
unknown calls in addition to reported usage from subsequent calls. Manual purchase
entry and policy search remain available when the provider fails.

The user configured the ignored local key and approved USD 10 total on 2026-09-15.
The worker was restarted to load it. Both the global lifetime and tenant/day caps
are USD 10; repeated tests share the global cap. Credentials are never included
in evidence. Successful model responses establish compatibility, not held-out
quality; human reference review and the remaining release gates are still open.

Latest evidence: `development-v5-full` records all 60 development cases under
prompt v5/schema v4 with the bounded provider transport. It improves the prior
full-run extraction score from 207/240 to 225/240. Twelve vendor and three item
errors remain. All 120 assistant jobs completed, with 180 settled provider calls
and estimated run cost USD 0.077731. Total lifetime accounted cost is USD 0.241278,
including USD 0.039322 reserved for unknown earlier calls, under the USD 10 cap.

The source-entry browser flow uploaded a new quote, extracted it, accepted only
the vendor and generated a review for the new revision. It did not silently change
the existing purchase total. Native file-picker automation exposed no controllable
dialog, so that particular interaction is still unverified.

Current human gate: complete `reference-review.html` and return the exported
review file. The held-out runner refuses absent, partial or stale review files.
The separate claim-review form inventories 108 finding/summary outputs from the
latest run, initially ungraded; the reviewer must split compound claims and give
reasons. Do not grade the output as supported merely because a citation exists.
R3 remains pending until the R2 acceptance evidence is complete.

Implementation notes and interview material are maintained in
`docs/teaching-guide.md` and `docs/interview-prep.md`. Claims and observed outputs
are linked from `docs/evidence-index.md`.
