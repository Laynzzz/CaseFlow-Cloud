# R2 local acceptance decision

Decision recorded 2026-09-17 UTC: **R2's local functional/evaluation deliverable
is complete, with AI explicitly experimental. AI quality targets did not all
pass. R1 cloud delivery remains incomplete.** This is not a production release.

## Why this status follows the plan

`plan.md` §3 requires a working AI journey and manual fallback plus published
held-out results. §17 phase 4 requires assisted/manual paths and an actual quality
report. §12 freezes numerical goals, requires reporting failures, and explicitly
says missed goals leave AI experimental while the manual product can ship.
ADR 0006 permits labeled AI review for the learning project; it does not turn
those judgments into independent human validation.

Earlier status notes treated unmet quality goals and unfinished evidence
together as an unfinished R2. The evidence work is now complete; the extraction
quality limitation remains. This decision distinguishes those two facts rather
than lowering the 90% extraction target or claiming that all gates passed.
Machine-generated quality reports retain `releaseGatePassed:false`; no individual
score declares overall release acceptance.

| Requirement | Observed evidence |
| --- | --- |
| Assisted browser journey and explicit acceptance | [Admin setup through actual DOCX download](browser-journey/README.md); saved $70 total, two ordered approvals, download checksum/content verified |
| Manual fallback | [Browser edit persisted during simulated assistant 503](../2026-09-15-r2/browser-file-and-fallback.json); simulation clearly labeled |
| Reference verification, held-out metrics and claims | [V3 full report](heldout-v3-summary.md), all 60 new cases, 180 versioned reference judgments, 108 output texts graded |
| Retrieval comparison and variability | Full-run text/semantic/hybrid results and [three predeclared repeats](heldout-v3-repeats.md) |
| Workflow comparison | [9/9 agent-operated API tasks](workflow-comparison/README.md); zero human participants, no time-saving claim |
| Failures and costs retained | 19 full-run rejected extractions, all repeat failures, selected ledgers; [USD 0.633975 shared accounting](budget-after-v3.json), including prior unknown reservations |
| Isolation, stale writes and spend protections | Existing named integration evidence plus fresh 7 Python and 4 Java database-backed checks below |
| Usability checks | Browser validation alert, keyboard skip/focus and editing, disabled stale acceptance, 390-pixel layout without overflow; limited scope, not full WCAG certification |

Fresh checks on the restored local services:

```powershell
. ./scripts/dev-env.ps1
$env:PYTHONPATH = Join-Path (Get-Location) 'services/worker'
services/worker/.venv/Scripts/python.exe -m pytest services/worker/tests/test_assistant.py services/worker/tests/test_policy_pins.py services/worker/tests/test_ai_budget.py -q
./services/case-api/gradlew.bat -p services/case-api test --tests dev.caseflow.evidence.AssistantIntegrationTest --rerun-tasks
services/worker/.venv/Scripts/python.exe -m pytest evals -q
node --test evals/test-case-selection.mjs evals/test-dataset.mjs evals/test-fresh-dataset.mjs
node --test tests/e2e/workflow-comparison.test.mjs
node scripts/smoke.mjs
node scripts/smoke.mjs http://127.0.0.1:5173
```

Results: 7 Python worker checks, 4 Java integration checks (zero skipped),
56 Python evaluation checks, 13 Node evaluation checks, 3 comparison checks,
and both smoke checks passed. Database tests use disposable test databases.
Root reproduced claim/score/comparison reports and reviewed all 60 main-run
summaries/findings. An independent agent checked reference/workflow/browser
artifact integrity and caught the explicit-ID scoring mismatch; its regression
tests failed before the scorer fix and passed afterward. No new model tuning.

## Limitations carried forward

Extraction is unreliable on some structured layouts: 68.33% against the 90%
goal, with strict citation rejection. Users must check suggestions or enter the
purchase manually. Fresh review support is 463/463 under AI grading, with narrow,
correlated synthetic coverage. No human user benefit, real-world quality,
production readiness or independent human verification is established.

R3 may now deepen recovery, performance, operations and portfolio evidence under
the user's existing continuation instruction. It must carry these AI limitations
forward. Cloud smoke, rollback and teardown require their own actual evidence;
they are not fulfilled by this local R2 decision.
