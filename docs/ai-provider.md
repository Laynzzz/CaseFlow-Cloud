# R2 provider and budget contract

Implementation status, 2026-09-15: typed extraction/review validation, a single
OpenAI transport adapter, and a PostgreSQL spend ledger are implemented and tested
with synthetic transport fixtures. They are not yet connected to application AI
jobs or suggestion-acceptance screens. No live calls or AI quality measurements
have been made.

Pinned provider SDK: openai 3.14.0. Initial model snapshot:
`gpt-4.1-mini-2025-04-14`. It supports structured JSON and offers a small initial
cost for evaluation. This is a baseline choice, not a measured best-model claim.
Source checked on 2026-09-15:
[model specification and standard prices](https://developers.openai.com/api/docs/models/gpt-4.1-mini),
[structured-output contract](https://developers.openai.com/api/docs/guides/structured-outputs).
Standard text input/output prices used: USD 0.40 / 1.60 per million tokens;
cached-input discounts are conservatively ignored. Pricing version is recorded.

Transport: Responses API, structured JSON schema, store=false, no tools, no hidden
SDK retries, 30-second timeout, 4,096 output tokens, bounded serialized text/schema
input. Input UTF-8 byte count plus a 2,048-token framing allowance conservatively
fits the 32,768-token reservation. Every returned usage is checked against the
bounds and the exact expected model snapshot. Recheck prices before live runs.

Admission uses a global lifetime spending ceiling and per-tenant UTC-day ceiling;
both default to zero in V7. Each provider call reserves the worst-case cost while
holding a database advisory lock. Concurrent workers cannot each spend the same
remaining allowance. Timeouts, missing usage and crashes retain the reservation;
they never turn unknown billing into zero. Recorded actual usage releases only
the unused portion. A duplicate reservation for the same job/attempt/fence/purpose
is rejected. This ledger covers calls through this adapter, not external account
usage, taxes or provider-side price changes.

The initial AI arithmetic validator supports USD/EUR/GBP/CAD/AUD/JPY/KWD. Other
currencies remain available in manual purchase entry but AI output for them is
explicitly rejected until currency metadata is extended. Decimal per-line rounding
is checked before display. Matching citations and sums are structural validity;
semantic claim support still requires the human evaluation rubric.

Tests: `services/worker/tests/test_ai_contracts.py`, `test_ai_budget.py`, and
`test_ai_provider.py`. These verify invalid citations, absent values, arithmetic,
unsupported actions, concurrent admission, unknown costs, schema errors, transport
failure and permission revocation before sending. Fake provider output cannot
satisfy the held-out evaluation gate. API-key configuration and the user's test
budget remain pending.
