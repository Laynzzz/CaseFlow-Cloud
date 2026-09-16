# R2 review quality: observations versus requirements

Status: development work, 2026-09-16. This does not replace the published v5
held-out baseline or mark R2 complete.

## The problem in a purchase request

Suppose the saved draft describes an equipment kit, has no vendor or cost center,
and records a total of USD 0.00. A policy says equipment purchases require a cost
center before approval. A useful review can report the empty cost center and cite
that rule. It cannot invent a rule requiring a vendor or declare zero invalid.
Those might sound reasonable, but they are not established by the supplied facts.

The full v5 development review found unsupported summary claims of exactly this
kind. All its dedicated policy findings were supported, while summaries added
requirements or diagnosed zero as incorrect/missing. The source input was
correct; the vague instruction to identify missing information left room for
extra assumptions. Schema and quote-substring checks did not detect meaning.

## Changes and alternatives

Review prompt `purchase-review-2026-09-16-v6` explicitly distinguishes literal
purchase observations from cited policy obligations. It preserves a supplied
zero, limits normative language to the actual rule, and requires summaries to
meet the same support standard as findings. Extraction retains its original v5
prompt text. Each task records the version and hash actually sent.

The first ten-case development run improved the judged summaries/findings to
66/66 supported claims, but one `missing_information` list incorrectly included
the populated description. That became a separate reproducible failure.

Review schema `purchase-review-v5` now constrains that list to known purchase
fields that are actually absent, null, blank or empty lists. The worker checks
the same condition after the call and rejects invalid output, retaining the raw
response and safe failure code. String or numeric zero is present. If every
field is populated, the schema requires an empty missing-information list.

This is a routine implementation choice within the planned fixed AI pipeline.
A prompt-only solution leaves objectively checkable mistakes to the model.
Silently rewriting the response would conceal what the model returned. Instead,
we constrain generation and reject invalid output through the existing failure
path. The limitation is that a rejection makes that review unavailable, although
manual purchase editing remains usable. No policy inference is delegated to this
simple emptiness check, and it does not require the model to list every empty field.

Extraction model/prompt/schema, tenant access, policy retrieval and the approval
workflow are unchanged. Model choice and the USD 10 shared budget are unchanged.
The additional prompt adds input tokens. Standard prices were rechecked on
2026-09-16 against [the official model page](https://developers.openai.com/api/docs/models/gpt-4.1-mini):
USD 0.40 input / USD 1.60 output per million tokens, matching the existing ledger.

## Verification and evidence

- [Prompt-only ten cases](evidence/2026-09-16-r2/development-v6-10/ai-claim-review-notes.md):
  66/66 supported factual claims; one false missing-field report retained.
- [Ten cases with the code check](evidence/2026-09-16-r2/development-v6-guard-10/ai-claim-review-notes.md):
  78/78 supported factual claims; zero false missing-field reports among 40 entries.
- The corresponding v5 development subset had 63/70 supported claims. Assertion
  counts differ because the model wrote different text; these are not matched
  binary outcomes or an estimate of real-world improvement.
- Both ten-case runs scored 40/40 extraction fields, 8/8 text Recall@5, 2/2 correct
  abstentions and 0/8 false abstentions. Both completed all 20 jobs. No embedding
  comparison was requested in these review diagnostics.
- Worker regression tests passed 67 tests; evaluation tooling passed 42 tests.
  New tests cover task-specific prompt hashes, false missing description/total,
  unknown field names, a fully populated zero-price purchase, and stored rejected
  response evidence. Mock transport tests do not prove model quality.

The [full development run declaration](evidence/2026-09-16-r2/review-v6-full-plan.json)
freezes all 60 development cases, prompt/schema versions and the existing model.
Its raw results and final assessment are recorded separately. These development
examples are not a new unseen test. No previous held-out score is overwritten,
and no new held-out improvement or R2 release pass follows from the subset scores.

The completed full run scored **459/460 supported factual claims (99.78%)**, with
one unsupported policy attribution, no false missing-field reports in 240 entries,
and all 60 reviews completed. Extraction scored 217/240, including two rejected
outputs. See [the full assessment](evidence/2026-09-16-r2/summary.md) for the
unchanged baseline, costs and limitations. A separate complete USD 4,200 purchase
also returned no missing fields through the live API without changing the draft.

## Reproduce

Read [ai_provider.py](../services/worker/caseflow_worker/ai_provider.py), a Python
provider adapter, for task-specific instructions and provenance. Read
[ai_contracts.py](../services/worker/caseflow_worker/ai_contracts.py), Python with
Pydantic validation, for the boundary between observable data checks and meaning.

From the repository root in PowerShell:

```powershell
. ./scripts/dev-env.ps1
$env:PYTHONPATH = Join-Path (Get-Location) 'services/worker'
services/worker/.venv/Scripts/python.exe -m pytest services/worker/tests -q
services/worker/.venv/Scripts/python.exe -m pytest evals -q
```

The tests use disposable databases, not the demo database. `-q` reduces output;
success is a zero exit code with all tests passed. Offline scoring and grading
commands are in [the evaluation README](../evals/README.md). A live rerun requires
a new output directory and consumes the same existing allowance; old outputs
must never be overwritten.
