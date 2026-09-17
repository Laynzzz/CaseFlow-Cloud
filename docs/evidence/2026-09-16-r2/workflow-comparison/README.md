# Automated synthetic workflow comparison

Nine of nine isolated-tenant tasks saved the predeclared correct draft and
completed their assigned workflow: three manual, three extraction-only, and
three grounded-review tasks. No accepted quote fields needed correction. All
three grounded reviews reported the one missing required field and cited the
published policy. This is an **agent-operated API self-test with zero human
participants**, not a participant pilot or evidence of user time savings.

The run occurred on 2026-09-17 at 02:41:37–02:43:07 UTC (the evening of
2026-09-16 in America/New_York). The runner revision was `fab6875`; its exact
SHA-256 and Node version are recorded in [run.json](run.json). The existing
local Java API, PostgreSQL, OIDC, Kafka and Python worker handled the requests.
The parent task concurrently ran browser acceptance and held-out evaluation.

## Method declared before calls

[predeclared-plan.json](predeclared-plan.json) was written before authentication
or any API call. Its hash is in `run.json`. It declares three matching purchase
fixtures, their quotes, policies, initial values, intended final values, required
field, completion definition, and this rotated order:

| Fixture | First | Second | Third | Required field |
| --- | --- | --- | --- | --- |
| Stand replacement | Manual | Extraction-only | Grounded review | costCenter |
| Archive labels | Extraction-only | Grounded review | Manual | justification |
| Workbench kits | Grounded review | Manual | Extraction-only | costCenter |

Each task created its own tenant, draft, quote and published policy. No existing
tenant membership, permission or purchase was changed. Every mode performed the
same source ingestion and policy pinning before the measured task interval.

Manual mode entered the predeclared quote fields and required policy field.
Extraction-only mode requested extraction, checked that the draft had not been
mutated, explicitly accepted vendor/currency/lineItems, compared the saved values
with the predeclared purchase, and entered the policy field manually. Grounded
review followed the extraction path, requested a review before filling the
policy field, inspected its findings/citations, and then entered that field.
Java computed the total from accepted line items; total was never accepted or
written as an independent editable field.

The harness counts actual differing quote fields replaced after acceptance as
corrections. Planned entry of an initially missing cost center or justification
is tracked separately. Null or wrong extraction suggestions remain visible as
discrepancies; provider failures remain failures even if manual fallback saves a
correct draft. Correct-draft completion and assigned-workflow completion are
separate measures. No fallback or failure occurred in this run.

## Observed results

| Mode | Correct drafts | Assigned workflows completed | Quote-field corrections | Task intervals, milliseconds |
| --- | --- | --- | --- | --- |
| Manual | 3/3 | 3/3 | 0 | 22, 19, 20 |
| Extraction-only | 3/3 | 3/3 | 0 | 5426, 6202, 7712 |
| Grounded review | 3/3 | 3/3 | 0 | 11557, 11641, 13139 |

Six extraction jobs succeeded and had zero discrepancies across their four
compared extraction fields. All three review jobs succeeded, reported the
predeclared missing field, retrieved/cited the case's policy, and left the
purchase unchanged. The assisting agent also read their returned summaries and
findings against the stored purchases and supplied passages: the stated vendor,
quantity, amount, existing request facts and policy requirement matched those
inputs. This qualitative AI inspection is not independent human validation or a
held-out claim-support score.

The model was `gpt-4.1-mini-2025-04-14`, using extraction prompt
`purchase-assistant-2026-09-15-v5` / schema `purchase-assistant-v4` and review
prompt `purchase-review-2026-09-16-v6` / schema `purchase-review-v5`. Review used
`postgres-full-text-v1`. No product configuration changed for this comparison.

[selected-call-ledger.json](selected-call-ledger.json) reconciles exactly nine
calls to the nine recorded job IDs: all settled without an error, costing
**USD 0.006996** in total. The shared lifetime ledger snapshot afterward was
USD 0.551944 against the unchanged USD 10 ceiling, including other runs and
unsettled reservations. That global difference must not be attributed to this
comparison because concurrent work was spending from the same ledger.

## Evidence and limits

- Individual numbered JSON files retain initial/final purchases, source IDs,
  source hashes, job IDs, outputs, acceptance responses, corrections, timing and
  failures. `run.json` binds their exact hashes and summarizes the observations.
- [records.jsonl](records.jsonl) contains those complete task records in order;
  its hash is recorded in `run.json`.
- [shared-ledger-after.json](shared-ledger-after.json) is a read-only snapshot of
  global accounted spend, including reserved/unknown usage.

Timing is harness execution plus API/queue/provider/worker time after common
setup. It excludes human reading, reasoning, typing and corrections, sign-in,
tenant creation, document ingestion and policy publication. The manual harness
already knows the correct answer. Its roughly 20 ms save is not a human manual
completion time. No time-savings or usability conclusion follows from these
numbers. Concurrent browser/evaluation traffic further prevents an isolated
performance interpretation. There are only three simple, single-item fixtures
and one run of each pair; rotated order does not remove those limitations.

Completion here means a correct saved draft. Approvals, DOCX generation,
participants/consent, generalization, and overall release acceptance are outside
this comparison. `humanVerified` and `releaseGatePassed` remain false.

## Reproduce

```powershell
node --test tests/e2e/workflow-comparison.test.mjs
node tests/e2e/workflow-comparison-live.mjs --validate-only
node tests/e2e/workflow-comparison-live.mjs --live --output docs/evidence/NEW-workflow-comparison
```

The last command makes paid requests under the existing shared ledger and needs
the local services and configured synthetic admin identity. It refuses an
existing output directory. Use a new directory; preserve this run's results.
The existing `services/worker/tools/export_ai_calls.py` exports calls for the
resulting `records.jsonl`; it requires the configured local database environment
and never prints credentials.

## Teaching and interview checkpoint

The runner is JavaScript executed by local Node, not browser code. The Java API
owns saved purchases and acceptance/version checks; the Python worker executes
AI jobs. A stand replacement begins with an empty vendor and item list. The
worker returns proposals; the runner's explicit acceptance command changes the
draft, after which Java calculates USD 374.50. The cost center is entered
separately because the quote cannot establish the requesting department.

1. **What did the comparison show?** In this agent-operated API self-test all
   nine synthetic tasks saved correct drafts, with no quote-field corrections.
   Follow-up: it does not measure human speed, usability or adoption.
2. **How did you distinguish assistance from fallback?** Recorded job outcomes,
   explicit acceptance, review inspection and correct final fields separately;
   a fallback could complete the draft without completing its assigned assisted
   mode. Follow-up: real people may reject a technically correct suggestion for
   reasons these fixtures cannot model.
3. **Why keep exact input and output hashes?** The input plan was declared before
   calls and each record is bound to the run summary, making accidental changes
   detectable. Follow-up: hashes establish artifact consistency, not correctness
   of the reference answers or independent validation.
