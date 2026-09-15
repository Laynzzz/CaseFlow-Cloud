# R2 implementation map — 2026-09-15

Release status: **in progress / experimental**. R1 cloud gates also remain open.

| Product step | Implemented | Verified so far | Remaining |
| --- | --- | --- | --- |
| Attach a vendor quote | PDF/TXT upload, immutable bytes, bounded parsing, text preview | Parser, database, real API/storage/worker checks | File-picker browser regression and broader hostile-file suite |
| Publish purchasing policies | Indexed publication, deactivation, immutable case pins | Real API and SQL invariants; browser text/search checks | Draft-content editing experience and broader history regressions |
| Find policy evidence | Authorized PostgreSQL full-text search, top five passages | Tenant/pin filtering and historical access tests | Embedding/hybrid candidate and measured comparison |
| Suggest purchase details | Provider adapter, strict schema, citations, arithmetic, durable jobs | Mocked transport and database checks | Live provider and assisted browser verification |
| Accept selected suggestions | Current-versus-proposed UI, separate acceptance command | Real SQL acceptance/replay/stale/revocation tests with synthetic results | Positive browser journey with a live model result |
| Generate a cited review | Fixed facts/evidence pipeline, abstention and citation checks | Contract/eligibility/fencing tests | Live claim-support and adversarial evaluation |
| Control AI spend | Zero-default lifetime/tenant-day ceilings and durable reservations | Concurrent reservations, duplicate calls, unknown costs | Approved live-test budget, key configuration, wall-clock containment checks |
| Demonstrate quality | 120 synthetic cases, disjoint 60/60 families, rubric and targets | Dataset files checked into Git before prompt work | Reference verification, runner, raw held-out outputs, scores, repeated runs and outcome measurements |

No live provider call has been made. Passing mock and SQL tests does not establish
AI quality. The user-facing app keeps manual purchase entry and policy search
available while live AI is disabled.

Next input needed for live checks: put `OPENAI_API_KEY` in the ignored local `.env`
and specify a maximum test budget. Never paste the key in chat. The budget command
in `docs/ai-provider.md` is prepared but has not been run with a positive limit.

Implementation notes and interview material are maintained in
`docs/teaching-guide.md` and `docs/interview-prep.md`. Claims and observed outputs
are linked from `docs/evidence-index.md`.
