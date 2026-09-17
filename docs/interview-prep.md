# CaseFlow interview preparation

Status: local purchase, document and live AI checkpoint, September 15, 2026.
AI extraction, explicit acceptance and cited review run locally; held-out quality
and cloud gates remain open. Use the evidence index before making claims.

## Explain the product in 30 seconds

Latest AI checkpoint: real quote extraction, explicit selected-field acceptance,
and a cited policy review work locally. In the first ten development cases,
schema v3 produced 40/40 field matches and 8/8 relevant passages, but 3/8 answerable
reviews incorrectly flagged insufficient evidence. References and claim support
still need human review; these results do not establish held-out quality.

After clarifying missing facts versus missing policy evidence and constraining
the empty-evidence schema, the same ten development cases returned 40/40 field
matches, 8/8 retrieval, 2/2 correct abstentions and 0/8 false abstentions. Describe
this as a small development iteration; the preserved failures explain the
engineering decisions and are not evidence of broad model reliability.

- **Why use both a strict model schema and code validation?** The schema constrains
  decimal formats and allowed citation IDs; code still checks exact source quotes,
  arithmetic, permissions and draft versions. Live failures exposed a currency
  suffix and a malformed citation ID, both rejected before acceptance.
- **Does a valid citation make a claim true?** No. It proves the quoted text exists
  in authorized evidence. A person still needs to check whether the passage
  supports the whole claim. The release report keeps that measure ungraded.

CaseFlow lets an employee submit a purchase request, assign two reviewers and
track their decisions. For example, a $4,200 laptop request goes to a manager
then finance. Java enforces the order and records an audit trail. The browser
is React, and PostgreSQL stores the organization's records. Final approval
queues a document request; a Python worker renders it and records a downloadable
Word file. Inbox/outbox records and fenced leases handle duplicate delivery and
stale workers.
The planned AI assistant will extract quote details and cite policy evidence,
while people continue to accept suggestions and approve the purchase.

## Identity and tenant isolation

**Question:** Why does the API read memberships if the token already has roles?

**Answer:** Keycloak proves identity using a signed token with checked issuer,
audience and expiry. Application memberships determine access to each tenant.
Reading their current active status prevents an old token from retaining a
revoked membership. Queries also check case ownership or assignment, and SQL
foreign keys include tenant IDs to reject cross-tenant references.

**Follow-up:** Does a UUID protect a record? No. Authorization must precede reads,
updates, result replay and eventually download issuance.

Evidence: `tests/e2e/purchase-api.mjs` tests outsider reads, unassigned reviewers,
auditor mutations and deactivation. Implementation:
`services/case-api/src/main/java/dev/caseflow/identity/Access.java` and
`db/migrations/V2__purchase_domain.sql`. Token adversarial tests are still partial.

## Conflicts and duplicate requests

**Question:** What happens if finance clicks twice or two approvals arrive together?

**Answer:** Java locks the case and compares the expected version. Only one
conflicting transition can succeed. A scoped idempotency key stores the request
hash and response in the same transaction as the update, audit and outbox.
Repeating that key with the same body returns the original response after
checking current access. A changed body conflicts. The UI preserves a draft
editor's original version so background refresh cannot hide a conflict.

**Follow-up:** Is this exactly-once delivery? No. Receipts last seven days;
permanent business constraints still protect terminal state. Retries after
network failures can reach the server more than once. The draft key is held
in memory, so a page reload does not preserve it.

Evidence: concurrent final approval returns one success and one 409; duplicate
start/approval and hash mismatch assertions are in the API suite. Read
`services/case-api/src/main/java/dev/caseflow/common/Commands.java`.

## Approval and document execution

**Question:** Why not render the Word file inside the approval transaction?

**Answer:** Approval is a human business decision. Slow or failed rendering
should not keep a database transaction open or reverse that decision. The
implemented final approval commits a stable generation ID and outbox request.
The worker consumes it and reports document status through a completion outbox.

**Follow-up:** What if the server crashes after committing approval? The durable
outbox request survives. Duplicate delivery and lease recovery have targeted
tests; the complete crash matrix and cloud behavior are still unverified.

Read `services/case-api/src/main/java/dev/caseflow/cases/CaseController.java`.

## Money and published versions

**Question:** Why calculate totals on the server and freeze workflow versions?

**Answer:** A browser can send an incorrect total. Java uses BigDecimal and
currency minor units, rounds line totals HALF_UP, then sums them. Published
workflows are immutable; starting copies the workflow and freezes the purchase.
A later edit should not change what an earlier reviewer decided on.

**Follow-up:** What remains? Templates now pin a published version too; policies
still need version pinning when AI ingestion is implemented.
Taxes, exchange rates and actual payment settlement are outside this model.

Evidence: PurchaseTest covers fractional quantities, minor units and draft
versus complete validation. Read `services/case-api/src/main/java/dev/caseflow/cases/Purchase.java`.

## Testing and honest limits

Seven unit tests plus real PostgreSQL/Keycloak integration checks are targeted
evidence, not proof of comprehensive security or production reliability.
Browser inspection is currently an observed session rather than a committed
Playwright regression suite. No cloud smoke, crash matrix, AI evaluation,
performance benchmark, production users or adoption claims exist yet.

Later checkpoints will deepen failure tests and add retrieval, AI grounding and budget
controls, query measurements, deployment/rollback and failure diagnosis.

## New checkpoint: asynchronous documents

**Question:** What stops two workers from producing two final documents?

**Answer:** The logical job has a unique database key. A lease claim increments
its fencing token. Completion must match the current token, attempt, owner and
unexpired lease. The selected artifact has a unique tenant/job key and commits
with successful job state and completion outbox. Competing or stale workers can
upload unselected objects, but cannot choose another final artifact.

**Follow-up:** Is execution exactly once? No. Uploads and execution can repeat
after a crash. Garbage collection of unselected objects is still planned.

**Question:** How did you prove a delayed failure cannot undo success?

**Answer:** The worker rejects a failure update after successful finalization.
Java also checks current attempt, fence, stored worker state and prior success.
The broker probe publishes ten duplicate requests, ten duplicate completions
and a new delayed failure event. It asserts one selected artifact, one success
audit, and preserved SUCCEEDED status. That is targeted evidence, not a full
crash matrix or high-availability claim.

**Question:** What implementation failure did you diagnose?

**Answer:** Rendering succeeded but Java completion retried. PostgreSQL showed
permission denied for the worker schema. Granting SELECT on a view was not
enough; schema USAGE was also required. A new migration added USAGE while
preserving denied access to base tables. The durable event replayed successfully.

Supporting code: `services/worker/caseflow_worker/jobs.py`,
`services/worker/tests/test_jobs.py`, `services/worker/tools/replay_document.py`,
`db/migrations/V4__api_worker_view_access.sql`, and the document evidence folder.
# R2 evidence preparation checkpoint (2026-09-14)

- Why parse before calling AI? The assistant needs a bounded, immutable record of
  what the quote/policy says. Python extracts page text and hashes chunks so later
  citations can be checked against exact source versions. Follow-up: PDF text
  extraction can lose layout; source existence alone does not prove claim support.
- Why run a separate parser process? Memory/time limits contain oversized or
  pathological files without blocking the long-running worker. Follow-up: process
  limits are not a complete security sandbox; container restrictions remain work.
- Why freeze evaluation before prompts? A family-separated held-out split reduces
  tuning leakage. The 120 synthetic references currently await human review;
  there are no measured model-quality or user-time-saving claims.

Evidence: `services/worker/tests/test_parsing.py` (13 passing checks),
`docs/adr/0003-r2-evidence.md`, `evals/README.md`. Upload wiring and AI calls are
subsequent work; do not describe them as verified by these parser tests.
# R2 source integration checkpoint (2026-09-14)

- Why are policy jobs separate from cases? Policies belong to an organization and
  can support multiple purchases. Nullable case IDs plus explicit source owners
  model that relationship without fictitious cases. SQL checks and scoped event
  validation prevent attaching a job to the wrong owner.
- When is a policy usable? After immutable upload, successful bounded parsing and
  transactional chunk selection, Java records indexing success; an administrator
  explicitly publishes it. A failed parse cannot be published.
- Why does attaching a quote change the draft version but not purchase values?
  Evidence changes the input context. Incrementing the revision makes future
  stale AI suggestions detectable while preserving human control of purchase data.

Evidence: `tests/e2e/source-api.mjs`, `services/worker/tests/test_ingestion.py`,
`db/migrations/V5__evidence_sources.sql`. AI quality is not measured by these tests.
# R2 policy history checkpoint (2026-09-15)

- What happens when a policy changes? Upload/publish a new immutable version.
  Drafts explicitly refresh their selection; started purchases retain old pins.
  Deactivation excludes new use while preserving authorized historical evidence.
- Why PostgreSQL full-text search first? It is a small, inspectable baseline using
  the existing database and tenant/source filters. It may miss synonyms. The
  embedding/hybrid alternative must show improvement on identical frozen queries;
  no retrieval-quality improvement has been measured yet.
- Can a requester refresh policies during an approval? No. The Java command and
  SQL trigger reject pin changes outside DRAFT; this protects the review history.

Evidence: `tests/e2e/source-api.mjs`, `services/worker/tests/test_policy_pins.py`,
`db/migrations/V6__policy_pins.sql`, `PolicyPinController.java`.
# R2 AI contract checkpoint (2026-09-15)

- Does valid JSON mean reliable AI? No. Schema validation proves shape, citation
  validation proves a supplied passage contains the quote, and arithmetic checks
  prove numeric consistency. None alone proves that the passage supports the claim.
- How do you bound spend across retries? Reserve the worst-case cost before each
  call in a transaction. Unknown usage keeps the reservation; settled actual usage
  releases only unused budget. Concurrent reservations share a durable lock.
- What happens when access changes during a call? Recheck before sending and
  selecting the result. Stop further use after revocation; already-sent provider
  content cannot be recalled. SDK retries are disabled and no arbitrary tools exist.

Evidence: `test_ai_contracts.py`, `test_ai_budget.py`, `test_ai_provider.py` and
`docs/ai-provider.md`. Transport fixtures pass; application AI wiring and live
quality evaluation remain unfinished at this checkpoint.
# R2 human acceptance checkpoint (2026-09-15)

- How can you prove AI cannot silently change purchase data? Job results live in
  worker-owned storage. Only a separate authorized Java acceptance command writes
  chosen draft fields, with revision checks, decimal validation and an audit record.
- What if I click Accept twice? The same idempotency key replays the first response
  without another mutation. A new command using the old proposal is stale after
  the first acceptance increments the draft revision.
- What has actually been verified? Database-backed acceptance and access rules,
  worker eligibility/fencing and mocked transport contracts. Live AI quality and
  the full assisted browser journey have not yet been verified.

Evidence: Java `AssistantIntegrationTest` and Python `test_assistant.py`. The
running application explicitly leaves live AI disabled while budget/key setup is
pending. There is no production/adoption or measured time-saving claim.
# R2 evaluation accounting checkpoint (2026-09-15)

- Why include failed AI jobs in accuracy denominators? Users experience those
  failures. Dropping them would overstate successful task completion. A missing
  prediction also cannot masquerade as a correct null-valued extraction.
- Does a 100% fixture score establish model quality? No. Fixtures test the scorer.
  Actual provider outputs, verified references and semantic grading are separate
  evidence. The diagnostic scorer cannot mark the release complete.

Evidence: `evals/scoring.py`, `evals/test_scoring.py` (five passing checks), and
dataset checksum validation. Live runs and embedding comparison remain pending.
# Live-provider failure checkpoint — 2026-09-15

- **What happens if the AI provider rejects a request?** The worker records a
  failed job, the purchase stays unchanged, and manual entry remains available.
  Two real extraction attempts failed; the second recorded HTTP 429. This is
  failure-handling evidence, not AI-quality evidence.
- **Why reserve money before sending?** A shared PostgreSQL lock and ledger
  prevent concurrent workers spending the same allowance. Unknown usage retains
  its upper-bound reservation. The authorized USD 10 is global across runs;
  USD 0.039322 is currently reserved for two uncertain attempts, not proven billing.
  Follow-up: conservative reservations can exhaust the allowance earlier than
  actual provider billing; reconciliation needs evidence before releasing them.

Evidence: [provider contract](ai-provider.md),
[live test](../tests/e2e/assistant-live.mjs),
[safe diagnostic test](../services/worker/tests/test_ai_provider.py).
# R2 additions: retrieval choices and provider deadlines (2026-09-15)

Reference-review follow-up: the user delegated the 120-case reference audit to
the assistant. The AI audit found matching source-derived fields and one ambiguous
laboratory-policy sentence repeated in eight cases. No human verification is
claimed. **Why audit the expected answers?** A model score is only meaningful
against defensible references. Here the literal wording says purchases must be
completed, while the intended rule is to supply a cost center. A clarification
needs a new dataset version, not a silent change to old evidence. See the AI
reference-review summary in `docs/evidence/2026-09-15-r2/ai-reference-review/`.

Latest measured checkpoint: two full 60-case development runs, extraction
207/240 -> 225/240 after a prompt change; the latter still misses 12 vendor values
and three item descriptions. All three retrieval methods obtain 48/48 in simple
corpora, but three distractor probes give text 0/3, semantic 3/3, hybrid 0/3.
These are generated references awaiting a real reviewer. Claim support remains
ungraded and there are no held-out results. See `docs/evidence-index.md` for raw
outputs, ledger rows and tests.

- **Can you call the AI accurate because every job succeeded?** No. The first
  full run had no failed jobs but only 86.25% field match. Schema validation proves
  structure, not correctness. Follow-up: report vendor accuracy separately, keep
  null/missing cases in denominators, and verify references before held-out tests.
- **What did the deadline cost?** It adds a process and SDK startup for each call.
  The bounded v5 run observed review p50/p95 of 4077/4891 ms versus 2297/4030 ms
  in the earlier direct-transport run. These runs also changed prompts and shared
  a development host; they do not isolate causal overhead. Follow-up: design a
  controlled comparison before claiming a performance result.
- **How do you know an accepted suggestion did not overwrite everything?** The
  browser pasted a USD 70 quote into an existing USD 4200 draft, requested
  extraction and accepted only Vendor. The supplier changed and the version
  increased; the existing line items and USD 4200 total stayed unchanged. Java
  enforces selected fields and matching revision; AI does not approve purchases.

- **Why compare text and semantic retrieval?** A purchase can use different words
  from its policy. The implementation records three rankings for the same query
  and tenant-scoped pinned corpus. The displayed review retains the text baseline
  pending measured quality. Follow-up: Recall@5 does not measure whether generated
  claims are supported; that requires separate manual grading.
- **Why not install a vector database immediately?** The experimental corpus is
  capped at 200 chunks, so exact cosine comparison over PostgreSQL-cached vectors
  is sufficient for this measurement. Follow-up: this is linear work with a hard
  limit; a larger corpus requires an indexing decision and new measurements.
- **What happens when an AI call never finishes?** A parent-enforced deadline
  terminates the disposable provider process. A test verifies the child cannot
  write afterward. The reservation stays UNKNOWN because a missing response does
  not prove the provider charged nothing. Follow-up: deadlines add startup cost
  and can discard late valid answers; they are per call, not the whole job.

Evidence: ADRs 0004/0005, worker retrieval and provider transport tests. Live
development measurements are diagnostics; human review and held-out gates remain
open. No production usage or retrieval-quality guarantee is claimed.


## Delegated reference review checkpoint (2026-09-15)

This supersedes the earlier pending-user-review status. Under ADR 0006, all 120
v2 cases have AI reference review with no unresolved issues. Independent human
review, held-out model results and claim support are still unmeasured.

- **Why version a wording correction?** Eight laboratory policies were ambiguous.
  A separate v2 snapshot clarifies the cost-center requirement without changing
  quote facts or expected answers. Historical v1 runs retain their original inputs.
  Follow-up: if held-out outputs guide prompt tuning, retire those families rather
  than continuing to advertise them as held out.
- **Does 480/480 mean perfect extraction?** No. These are source/reference checks
  by an AI-assisted audit, not product predictions. The latest development model
  score remains 225/240. Follow-up: AI reviewers can share model errors, so later
  independent human grading provides stronger evidence.
- **How do you prevent review provenance from getting lost?** Live runs require
  an explicit AI profile and complete resolved judgments with case/file hashes.
  They copy the review artifact and its checksum. The human profile rejects AI
  artifacts. Follow-up: checksums ensure consistent bytes, not truthful judgment.

Evidence: docs/adr/0006-ai-assisted-evaluation-review.md,
evals/test-dataset.mjs, evals/test_audit_references.py, and
docs/evidence/2026-09-15-r2/ai-reference-review-v2/summary.md.


## Held-out evaluation checkpoint (2026-09-16)

Supersedes earlier pending-evaluation notes. All 60 held-out cases were run and
all 108 review outputs received explicitly labeled AI grading. Field accuracy was
221/240 (92.08%); factual support 360/412 (87.38%) missed the 95% target. R2 remains
experimental, with no independent human validation or real-user outcome claim.

- **Why is a valid citation insufficient?** The 48 policy findings were supported,
  but summaries added unsupported requirements and diagnoses of zero totals.
  Citation validation proves that a passage exists and can be quoted; semantic
  evaluation checks whether each actual assertion follows. Follow-up: separate
  supplied purchase facts from policy requirements and never infer extra rules.
- **Why retain failed attempts?** The first run stopped on a child-process error.
  Its unknown charge reservation remains in the shared ledger, and its missing
  cases remain failures. The complete rerun is separate. Follow-up: a retry's
  success does not identify the first error's underlying cause or erase its cost.
- **Is the model repeatable?** One fixed ten-case repeat changed four vendor
  fields and accuracy 35/40 → 37/40, with unchanged abstention decisions. This
  narrow one-family repeat demonstrates observed variation, not a general rate.
  Follow-up: freeze configuration and compare the same denominator; different
  wording alone is not proof of changed factual support.

Evidence: docs/evidence/2026-09-15-r2/heldout-summary.md; evals/claim_review.py;
evals/compare_repeated_run.py; browser-file-and-fallback.json. The fresh evaluation
suite has 41 Python tests; tests establish scorer behavior, not model accuracy.

## Review quality and ordinary code (2026-09-16)

- **Which AI errors can ordinary code prevent?** The application knows whether
  the saved description is empty and whether zero was supplied. Review schema v5
  permits only actually missing field names, and post-validation rejects a false
  report. It cannot prove whether a policy sentence supports a new obligation.
  Follow-up: constrain and validate objective facts; evaluate semantic claims.
- **Why keep separate prompt versions?** A review-instruction change should not
  silently alter quote extraction. Each task records the actual prompt hash and
  version, and repetition checks validate the two task versions separately.
  Follow-up: valid JSON and reproducible configuration do not make output deterministic.
- **Did the prompt fix establish general accuracy?** No. The full sixty-case
  development result improved from 377/437 to 459/460 supported claims, but these
  examples are already part of development. One unsupported claim remains.
  The old held-out baseline remains intact, and broader/fresh evidence is required.
  Follow-up: test assertions outside the scored summary too; one missing-field
  list was wrong despite supported summary/finding text.

Evidence and trade-offs: [review-quality notes](r2-review-quality.md),
[architecture overview](architecture.md), and their linked code and raw runs.
## Local assisted browser journey (2026-09-16)

**How do you prove AI cannot approve a purchase?** The browser journey accepted
selected quote fields into a draft, then required manager and finance actions in
order. Finance had no approval control before the manager acted; the API's separate
permission/order tests enforce the same boundary. Final approval queued the DOCX.
Follow-up: UI hiding alone is insufficient; Java must reject unauthorized actions.

**What happens when a draft changes after AI runs?** Results retain their input
revision, show a stale notice and disable acceptance. The browser verified this
after saving suggestions and refreshing policies. A fast stale upload also
received HTTP 409 instead of overwriting newer state. Follow-up: optimistic
concurrency protects state, but the user may need to retry after refresh.

**What does the browser evidence actually establish?** One local synthetic flow
from admin setup through real model suggestions, explicit acceptance, sequential
approvals and a checksum-matched download. Focused keyboard and narrow-screen
checks passed. It is not a human usability study, full accessibility audit or
cloud-readiness claim. Evidence: `evidence/2026-09-16-r2/browser-journey/README.md`.
## Workflow comparison: claims and limits

**Did AI make users faster?** We have not measured that. A nine-task automated
API self-test completed three workflows successfully and recorded actual model
waiting, corrections and failures. It cannot establish human reading/typing time,
adoption or time savings. Evidence:
`evidence/2026-09-16-r2/workflow-comparison/README.md`.

**Why distinguish assisted completion from final-draft correctness?** A provider
failure followed by manual entry could still produce a correct draft. Reporting
only that outcome would hide a broken assistant. The harness records both; all
nine tasks completed their assigned mode in this particular small run.
## Fresh held-out results and experimental release

**What did the new test reveal?** Quote extraction matched164/240 fields (68.33%)
on60 fresh synthetic cases. Nineteen outputs were rejected for nonliteral source
quotes, while the41 accepted outputs matched all references. This exposes a
formatting-generalization and reliability weakness. Follow-up: failing safely
protects displayed results but still counts as a task failure, not a correct answer.

**Can you claim the AI is accurate?** Only report the measured scope:48/48
retrieval,12/12 correct abstention,0/48 false abstention,463/463 AI-supported
review assertions, and the missed90% extraction goal. These are AI-reviewed,
correlated synthetic cases, not independent human or production validation.
Follow-up: repeat scores vary; do not choose the best run or pool repeated cases
as new independent examples.

**Why move to R3 with a missed target?** The plan's R2 deliverable is the working
assisted/manual product plus actual evaluation. It explicitly leaves AI experimental
when provisional goals are missed. We document that limitation and preserve
manual entry; R3 verifies recovery/operations without claiming the model was fixed.
Evidence: `evidence/2026-09-16-r2/r2-acceptance.md` and `heldout-v3-summary.md`.

## R3 recovery architecture checkpoint

**What happens if finance approves a purchase and the document worker fails?**
Approval stays recorded. Java commits the document request and outgoing event
with the final approval. Python schedules durable work, leases execution and
stores a result only if it still owns the current attempt and fencing token.
The page can show a failed document job without reversing the purchase decision.
Follow-up: bounded retries can exhaust; automatic retry is not a guarantee that
every job eventually succeeds without operator action.

**Why can the same completion event be sent twice?** Kafka may acknowledge a
send just before the publisher loses its database transaction. The outbox row
then remains pending and is sent again. Java checks its event receipt and the
current job/result before committing visible status and audit together.
Follow-up: this protects the selected business result, not exactly-once network
delivery, rendering work or provider billing.

**How do you know a recovery test proves enough?** Name its failure boundary,
the real dependencies, the substituted dependencies and the durable assertions.
An exception before database commit can prove rollback and replay behavior.
A fake transport cannot prove Kafka broker recovery. Process termination,
dependency restart and sustained redelivery need separate observed runs.
Follow-up: forcing a lease expiry through SQL tests fencing, but it does not
measure recovery time after a real process failure.

Implementation: Python `services/worker/caseflow_worker/jobs.py` and `runtime.py`;
Java `services/case-api/src/main/java/dev/caseflow/documents/CompletionHandler.java`.
The [R3 map](r3-status.md) separates verified checks from remaining release gates.

Evidence checkpoint: [11 new recovery tests](evidence/2026-09-16-r3/recovery-contracts.md)
now exercise these boundaries. The duplicate-completion test observes the second
transaction waiting on a PostgreSQL lock before allowing the first to commit.
This establishes real contention for that pair, not scheduler fairness or
high-volume broker behavior. Full suites passed 73 Python and 20 Java tests;
focused final reruns cover the strengthened assertions.

## R3 process-crash and broker evidence checkpoint

**How did you test an actual process failure?** We launched owned Python/JVM
children that execute production transaction components against isolated real
databases. A boundary handshake confirmed the child was alive at the intended
point before forced termination. Five worker scenarios and two Java completion
scenarios passed. Negative controls allowing normal exit failed the tests.
Follow-up: these are component subprocesses, not complete service, machine or
dependency outages; those broader gates remain open.

**What happens when the worker dies after uploading a file?** The test observes
an uploaded but unselected DOCX. The real lease expires; a new owner with a
higher fence writes a different immutable key and selects its result. The old
owner cannot finalize and its object bytes remain unchanged. We verify hashes
and the selected document's synthetic contents.
Follow-up: abandoned objects still need production garbage collection; deleting
test fixtures does not implement that operational feature.

**What does the 10,000-redelivery result actually prove?** We injected 5,000
request and 5,000 completion duplicates for one completed synthetic job, plus
one late failure. We retained all acknowledged broker coordinates and checked
both consumer groups advanced beyond them. One execution, one artifact and one
success audit remained; the late failure was stale. The run took 73.187 seconds.
Follow-up: this is duplicate-handling evidence, not a sustained-throughput
benchmark, 10,000 distinct purchases, or exactly-once transport.

Evidence: [results, commands and limits](evidence/2026-09-17-r3/summary.md).
Implementation: Python `services/worker/tests/test_process_recovery.py` and
`services/worker/tools/replay_document.py`; Java
`services/case-api/src/test/java/dev/caseflow/documents/CompletionProcessRecoveryTest.java`.
Full recorded regression suites: 95 Python and 22 Java tests, no failures/skips.

## R3 real Kafka acknowledgement checkpoint

**Why is commit ordering important?** The worker first stores its inbox receipt
and durable job in PostgreSQL, then acknowledges consumption to Kafka. A crash
between them causes redelivery, and the stored receipt makes the repeated
database effect harmless. Committing the offset first could lose work. The new
Python process test observes the offset at the boundary and a fresh process
receiving exactly the same record after a kill.
Follow-up: an event receipt means scheduling finished, not that document
rendering finished; those are separate transactions.

**Why does the publisher sometimes send twice?** A real broker acknowledgement
can occur before the outbox's published marker commits. The test kills the
publisher in that gap, then observes the same event ID at two different Kafka
offsets after restart. It is safer to retry than to mark an unacknowledged send
as complete. Consumer idempotency protects business state.
Follow-up: idempotent producer configuration alone cannot make Kafka and
PostgreSQL one atomic transaction.

**Why add a constructor just for testing?** Java's messaging component used
concrete clients and fixed topics internally. An internal constructor accepts
client interfaces and test topics while the public Spring constructor keeps
the production configuration. Tests can then pause real clients at observed
boundaries without rewriting the business loop or touching demo groups.
Follow-up: the child uses Spring's transactional proxy around the real handler;
calling a manually created annotated object would not reproduce that boundary.

Evidence scope and current results: [recovery matrix](recovery-matrix.md) and
[Kafka process report](evidence/2026-09-17-r3/kafka-boundaries/summary.md).
Full regression suites passed 102 Python and 29 Java tests without failures or
skips. These counts include controls and existing regressions, not 131 crash
scenarios; the map counts thirteen distinct business-boundary process crashes.

## R3 storage timeout checkpoint

**Does a timeout mean the document upload failed?** No. The server may have
stored the bytes before its response was lost. Our test endpoint writes a real
DOCX to local S3, withholds acknowledgement, and records that the write finished
before the SDK's read timeout. The worker leaves the artifact unselected and
retries after backoff using a new immutable key.
Follow-up: this can leave an orphan object; production garbage collection is
still separate work.

**What prevents the original execution from replacing the recovered result?**
The new execution owns a higher fencing token. Finalization is conditional on
current ownership, attempt and lease; old finalization and a delayed failure
are rejected. The timeout tests verify both objects' checksums and the selected
DOCX's contents after retry.
Follow-up: a fence protects selection in PostgreSQL; immutable keys separately
protect the stored bytes from overwrites.

Evidence: [two socket-timeout integration cases](evidence/2026-09-17-r3/dependencies/storage.md).
The full worker suite now passes 104 tests. The test uses a shortened SDK
timeout and controlled response stalls; do not describe this as a production S3
outage or a measured recovery-time guarantee.

## R3 dependency restart checkpoint

**What happens when Kafka is unavailable?** A real failed publish leaves the
worker's outbox row unpublished. The same runtime keeps retrying. Our isolated
broker test stops and restarts the same persisted container, then verifies one
broker record with the original event ID and one published outbox row.
Follow-up: the test covers a pending publish with a single broker, not broker
high availability or all ambiguous-send duplicate cases; those require the
separate acknowledgement-gap evidence.

**How do you prove a database restart did not lose a scheduled job?** The test
interrupts the real SQL transaction before commit. The Kafka offset stays
uncommitted; after restart, an independent connection sees no partial job or
inbox. The same consumer retries, producing one job and receipt. Another
delivery advances the offset without creating another business record.
Follow-up: this tests the Python connection/retry path. Do not generalize it to
Java pool reconnection or cloud failover without separate evidence.

**How do you avoid breaking the demo during failure tests?** A separate Compose
project owns distinct ports, containers, volumes and network. Destructive
commands validate exact names and project labels, and evidence records what
was stopped/restarted/removed. Negative controls omit the stop and must fail
the unavailable-operation assertions.
Follow-up: test cleanup needs the same care as production operations; image
declared anonymous volumes and failure-path worker shutdown can otherwise leak.

Evidence and limitations: [dependency batch](evidence/2026-09-17-r3/dependencies/summary.md).

## R3 operational reporting and cleanup checkpoint

**How would you diagnose an approved purchase whose document never appears?**
Use the read-only operational report to distinguish expired ownership, overdue
work, pending publication and a missing current generation attempt. It emits
IDs and timestamps rather than purchase or policy contents. Check worker and
dependency health before retrying through the application's audited action.
Follow-up: reports are bounded snapshots, not automatic repair or universal
health checks. Our first local run identified two preserved legacy approvals
from before durable document jobs existed; no synthetic job history was invented.

**Why check the attempt number as well as the job ID?** A retry keeps the
logical job ID but advances its attempt. An old failed worker row can exist
while the new attempt never arrives. The report compares the current attempt
and ages it from the retry's update time. Independent review found this gap;
a regression failed before the fix and passes afterward.
Follow-up: distinguish a new business retry attempt from a higher fencing token
when a worker reclaims the same attempt after lease expiry.

**How do you avoid deleting a file another transaction selects?** Cleanup is
explicitly job scoped, requires a consistent successful document, protects all
artifact references and rechecks state under locks through deletion. A narrow
SQL function takes an artifact SHARE lock without granting artifact writes.
Concurrent reference creation is blocked; unrelated heartbeat updates proceed.
Follow-up: artifact selection across jobs pauses briefly, so this manual tool
trades throughput for a simpler safety argument. It is not a bucket-wide collector.

**Can you roll back a file delete if the database transaction fails?** No.
Storage and PostgreSQL do not share a commit. We flush a deletion intent into
an exclusive journal first and record acknowledged or unknown outcomes afterward.
Actual child-process exits before/after deletion leave pending intent and preserve
the selected document. Operators inspect uncertain outcomes rather than assuming
rollback restored bytes.
Follow-up: conditional ETags rely on immutable key usage; cloud/versioned-bucket
behavior and a real 24-hour retention soak remain unverified.

Evidence: [15 reporting tests, 33 cleanup tests and full regressions](evidence/2026-09-17-r3/operations/summary.md).
Current full regression result: 152 Python and 29 Java tests; these totals
include earlier tests and must not be described as 181 failure scenarios.

## R3 query optimization checkpoint

**What did you optimize, and how do you know it helped?** I measured the actual
tenant-scoped purchase-list query on a 100,000-case tenant and a 200-case tenant.
An index on tenant, state and cursor order reduced buffer accesses for the
large selective ACTIVE query from 1,281 to 29 in repeated before/after pairs.
The same rows and cursors were returned. This is a synthetic warm-cache SQL
result, not a production adoption or HTTP-throughput claim.
Follow-up: retain unfiltered/common-state comparisons; the latter increased
from five to six buffer accesses. More indexes are not universally better.

**Why keep the original index? What is the cost of the new one?** The original
tenant/time index supports unfiltered lists. The new index efficiently selects
a tenant/state range before walking cursor order. It adds 7.41 MiB on this
fixture and needs maintenance on inserts and state transitions; write throughput
was not measured. An ACTIVE-only partial index is narrower but less general.
Follow-up: ordinary CREATE INDEX blocks writes during construction. The local
build duration does not establish a safe production maintenance window.

**How did you guard correctness and measurement validity?** Real API-role
integration tests check permissions, tenant isolation and pagination while a
recording JdbcTemplate counts SQL without replacing database results. The
benchmark captures actual SQL/binds, plans, result hashes and source fingerprints,
then alternates before/after twice with fixed data. A no-index control fails
the buffer-reduction gate. Millisecond samples are reported rather than used
as universal thresholds.
Follow-up: a fresh-connection test fixture hit Windows socket-allocation errors
during concurrent suites. A small Hikari pool reduced connection churn, and
the final results use that revised fixture. EXPLAIN timings and pooled Java
timings are separate observations, neither a sustained system load test.

Evidence and reproducible commands: [query performance](query-performance.md).

## Packaged local release checkpoint

**What does Docker add here?** It packages the Java/API/frontend and Python worker
with pinned runtimes/dependencies. The isolated Compose profile tests their real
network paths and persistent dependencies together. A successful local container
run is deployment rehearsal, not evidence of AWS operation or production users.

**How would you roll back safely?** Keep immutable prior image IDs, apply only
backward-compatible migrations, health-check the candidate and run the approval
smoke, then restore the prior images if needed. Never automatically undo business
data or SQL migrations. The initial packaged baseline and data-preservation smoke
passed; executed candidate rollback is recorded separately when completed.

**Why have internal and public endpoints?** Containers resolve service names that
a browser cannot. The issuer remains the public OIDC identity, while Java fetches
keys internally. Object reads use internal storage; signed download URLs must be
signed with the host the browser actually reaches. Follow-up: an issued signed
URL remains a bearer capability until its short expiry.

Evidence: [local baseline](evidence/2026-09-17-r3/release-baseline/README.md).

## Correlated telemetry checkpoint

**How do you trace asynchronous work after the HTTP request ends?** Persist the
trace parent in the Java outbox envelope and durable Python job, then propagate
it through worker completion and Java consumption. Each operation gets its own
span while retaining request ancestry; storage and restart do not require an
in-memory HTTP context. V14 is additive for prior-image compatibility.

**Why distinguish HTTP, queue and execution latency?** A fast acknowledgement can
hide an ever-growing job backlog. Ready-to-claim timing excludes deliberate retry
backoff; reclaimed work becomes ready at lease expiry. Execution includes result
persistence; client-observed completion is measured independently by load tests.

**What happens when monitoring fails?** Export is asynchronous/bounded, does not
control business commits, and starts only when explicitly configured. DB/broker
metrics publish an unavailable signal and omit invented zero backlog/lag. Metric
labels have finite kind/status/operation values; raw text, tokens and arbitrary
baggage are excluded. Follow-up: 100% sampling is a bounded evidence setting, not
a production-wide promise.

Evidence: [actual trace and regression suites](evidence/2026-09-17-r3/telemetry/summary.md).

**Can dead-letter messages repeat?** Yes. If the process crashes after the broker
acknowledges the diagnosis but before committing the original offset, the source
record replays and emits the same redacted diagnosis again. Four forced-kill tests
prove that boundary across Java and Python, with zero business database effects.
Follow-up: a dead-letter queue is diagnosis, not an authorization bypass; arbitrary
payload replay and offset resets are not supplied as an operator shortcut.
Evidence: [dead-letter crashes](evidence/2026-09-17-r3/deadletters/summary.md).

## Sustained-load interview checkpoint

**What did you measure beyond fast APIs?** A fixed mixed arrival rate, actual
approved DOCX completions, bounded backlog and drain, error/dropped work, queue
and execution metrics, pool/CPU/memory observations and two tenant boundaries.
The local measured phase completed72 documents, with observed p95 completion
3.835s and no workload failures. Total including warmup:84/84 documents.

**Can you claim maximum throughput or production performance?** No. This was one
180-second measured local operating point at2 mixed arrivals/s, not a saturation
search or long soak. Completion observations include polling. Raw point-sampled
CPU and Kafka lag do not exclude transient peaks. Exact image/workload hashes,
limits and warm-cache state make the experiment reproducible without exaggeration.

[Actual load evidence](../tests/load/results/2026-09-17T15-04-19-100Z/analysis.md).

## Monitoring and rollback checkpoint

**What happens if Kafka goes down after finance approves?** Approval and the
outbox remain durable. In the actual isolated release fault, the job stayed
queued and the Kafka-unavailable alert fired. When the broker returned, the same
application processes completed it with one completion audit and a matching
download checksum. This does not prove recovery from lost broker/database data.

**What did rollback prove?** Older API/worker images ran against additive V14,
completed a new purchase and preserved four existing artifacts. Restoring the
candidate repeated those checks. The database was retained; this is application
rollback, not a database restore or a claim about arbitrary schema compatibility.

**Why filter traces if applications already avoid business data?** Defense at
the export boundary: framework exceptions or dynamic span names may still carry
unwanted text. The collector removes events and unsupported attributes; a real
probe verified sentinel removal and parent retention. Dropping unsupported
linked spans and normalizing Java framework names reduces diagnostic detail.

Evidence: [monitoring and recovery](evidence/2026-09-17-r3/monitoring-recovery/summary.md).

## CI and security-scan checkpoint

**What does the coverage number establish?** The four declared critical modules
exceed 80% branch coverage; the actual range is 96.15–100%. It demonstrates those
branches executed, not that all outcomes or the whole repository are correct.
Separate concurrency, role, tenant and process-crash invariants provide stronger
behavioral evidence. The latest broad run passed 60 Java and 174 Python tests;
one Java performance benchmark was separately opt-in and skipped in that run.

**What did you do with vulnerability findings?** Patched Tomcat and four worker
OS packages, retained raw scan failures, then documented eight unfixed CVEs with
exact package versions, runtime reasoning and October 1 expiry. No fixed or
CRITICAL finding is exempted. This is engineering risk review, not independent
certification. A future fix or expired review blocks CI again.

**Has CI run in the cloud?** Workflow source and its commands are verified
locally; no GitHub-hosted run is claimed. Similarly, Terraform validation and
mocked plans do not establish that AWS deployment works.

Evidence: [local checks and scans](evidence/2026-09-17-r3/ci/summary.md).

## Cloud design checkpoint — planned runtime, verified source only

**Why AWS if the application already works locally?** The plan requires cloud
delivery evidence: run the purchase flow through public TLS/identity, managed
database and object storage, then deploy and roll back actual images. AWS does
not implement the AI behavior; it hosts the application and its dependencies.

**What is the main cloud trade-off?** A short-lived single VM hosts broker,
identity and monitoring to reduce rehearsal overhead. They share a failure
domain; this is explicitly not broker HA or a production availability design.
ECS runs the application separately, RDS is private, and runtime roles restrict
S3/secret access. Retaining data after compute teardown still costs money.

**What cloud experience can you honestly claim now?** Implemented Terraform,
mocked safety checks, bootstrap redaction, configurable smoke and cost/runbook
preparation, plus live read-only account/region discovery. The account and domain
are now available; actual AWS deployment and rollback remain pending deployment
permissions, DNS delegation and separate credit-usage authorization. Do not
present a local Docker rehearsal as a completed AWS deployment.

**Why change server sizes after writing Terraform?** Account preflight revealed
that the Free plan excludes the original sizes. We selected a supported 8 GiB
host and a smaller supported PostgreSQL instance while preserving the service
architecture. Follow-up: the database's reduced memory is an explicit capacity
trade-off; mocked plans and catalog listings cannot prove the workflow runs.

**Does USD 100 in credits mean every AWS service is free?** No. Plan eligibility,
resource list prices, remaining account-wide credits and actual billing are
different concerns. We recorded them separately and kept provisioning blocked
until a bounded cloud allowance and deployment access are established.
Evidence: [preflight](evidence/2026-09-17-r3/cloud-preflight/summary.md),
[ADR 0008](adr/0008-free-plan-rehearsal-sizing.md).

**How did you separate deployment and runtime permissions?** A one-time owner
bootstrap grants the operator selected infrastructure actions. Terraform gives
the application roles narrower policies and an owner-controlled permissions
boundary. The operator cannot edit that boundary or remove it. Follow-up:
some deployment actions are regional/account-wide; stronger isolation would be
needed in a shared production account.

**What did permission testing catch before deployment?** Review found that
preexisting unbounded role names could permit escalation, and that an EC2
instance-size condition incorrectly blocked ancillary launch resources. Added
preflight guards and separate launch statements address both. Offline tests,
AWS policy validation and selected read-only simulations passed. Those checks
do not prove a real deployment works. The USD 10 AWS-credit allowance is now
approved; the owner grant and actual deployment remain pending.
