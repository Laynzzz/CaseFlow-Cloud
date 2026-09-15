# R2 provider and budget contract

Implementation status, 2026-09-15: typed extraction/review validation, a single
OpenAI transport adapter, and a PostgreSQL spend ledger are connected to durable
application jobs and selected-field acceptance screens. Synthetic transport and
disposable-database checks pass. On 2026-09-15 the user configured the ignored
local key and authorized USD 10 total for synthetic live testing. The shared
lifetime and tenant/day ceilings are both USD 10; the global ceiling applies
across all tenants and runs. Live compatibility checks are in progress. The
complete assisted browser journey and AI quality remain unverified.

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

Tests: `services/worker/tests/test_ai_contracts.py`, `test_ai_budget.py`,
`test_ai_provider.py`, `test_assistant.py`, and Java `AssistantIntegrationTest`.
These verify invalid citations, absent values, arithmetic,
unsupported actions, concurrent admission, unknown costs, schema errors, transport
failure and permission revocation before sending. Fake provider output cannot
satisfy the held-out evaluation gate. After explicit budget authorization, an operator can run
`services/worker/.venv/Scripts/python.exe services/worker/tools/configure_ai_budget.py --total-usd APPROVED_TOTAL --tenant-daily-usd APPROVED_DAILY`
after `. ./scripts/dev-env.ps1`. Both limits are required. The total is a lifetime
ceiling for this ledger, not a fresh allowance on each invocation. Setting both
to zero disables future admission. The ignored `.env` key is loaded only by the
worker startup script; it is not part of the frontend bundle or API responses.

Read-only inspection after loading `scripts/dev-env.ps1`:
`services/worker/.venv/Scripts/python.exe services/worker/tools/ai_budget_status.py`.
This reports ceilings, counts, safe error codes and settled/reserved cost without
credentials or provider response bodies. Unknown usage stays reserved.

Opt-in integration check: `node tests/e2e/assistant-live.mjs --live`. It creates
synthetic quote/policy/case records, requests live extraction through the normal
API and worker, checks explicit acceptance and replay, then requests a cited
review. Each invocation can spend from the same approved ceiling. Raw synthetic
job results and failures are saved under a unique R2 evidence directory. Passing
this journey establishes compatibility, not benchmark accuracy or claim support.

Remaining R2 gates: live provider compatibility, embedding/hybrid comparison,
annotation verification, evaluation runner and held-out report, repeated runs,
manual-versus-assisted measurements, full assisted browser regression, broader
failure and permission tests. The configured SDK timeout is a network timeout;
strict end-to-end provider wall-clock containment also needs verification.
