# R2 implementation map — 2026-09-15

Release status: **in progress / experimental**. R1 cloud gates also remain open.
User direction: after R2 passes its gates, continue directly into R3 without
another confirmation unless an actual unresolved problem prevents the transition.

| Product step | Implemented | Verified so far | Remaining |
| --- | --- | --- | --- |
| Attach a vendor quote | PDF/TXT upload, immutable bytes, bounded parsing, text preview | Parser, database, real API/storage/worker checks | File-picker browser regression and broader hostile-file suite |
| Publish purchasing policies | Indexed publication, deactivation, immutable case pins | Real API and SQL invariants; browser text/search checks | Draft-content editing experience and broader history regressions |
| Find policy evidence | Authorized PostgreSQL full-text search, top five passages | Tenant/pin filtering and historical access tests | Embedding/hybrid candidate and measured comparison |
| Suggest purchase details | Provider adapter, strict schema, citations, arithmetic, durable jobs | Mocked transport and database checks | Live provider and assisted browser verification |
| Accept selected suggestions | Current-versus-proposed UI, separate acceptance command | Real SQL acceptance/replay/stale/revocation tests with synthetic results | Positive browser journey with a live model result |
| Generate a cited review | Fixed facts/evidence pipeline, abstention and citation checks | Contract/eligibility/fencing tests | Live claim-support and adversarial evaluation |
| Control AI spend | Zero-default lifetime/tenant-day ceilings and durable reservations | Concurrent reservations, duplicate calls, unknown costs; user-authorized USD 10 ceiling configured | Wall-clock containment checks |
| Demonstrate quality | 120 synthetic cases, disjoint 60/60 families, rubric, targets and offline scorer | Dataset hashes/families and five scorer tests | Reference verification, live runner, raw held-out outputs, scores, repeated runs and outcome measurements |

Two live extraction attempts reached the provider but failed; the second recorded
HTTP 429. Neither produced a model result. The ledger conservatively retains USD
0.039322 for unknown usage, which is a reservation, not confirmed billing. Passing
mock and SQL tests does not establish AI quality. Manual purchase entry and policy
search remain available when the provider fails.

The user configured the ignored local key and approved USD 10 total on 2026-09-15.
The worker was restarted to load it. Both the global lifetime and tenant/day caps
are USD 10; repeated tests share the global cap. Provider 429 needs resolution
before successful live checks. Credentials are never included in evidence.

Implementation notes and interview material are maintained in
`docs/teaching-guide.md` and `docs/interview-prep.md`. Claims and observed outputs
are linked from `docs/evidence-index.md`.
