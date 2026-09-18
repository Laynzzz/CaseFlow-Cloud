# Project agent instructions

Use this file with the project's `plan.md`. For a new repository, copy this file
to the repository root as `AGENTS.md`, or give both files directly to the agent.
These are reusable working preferences; `plan.md` defines the particular product,
architecture, scope, milestones and acceptance criteria.

## 1. Goal: build first, teach afterward

Implement the project through the authorized plan, verify the results, and prepare
the user to understand and explain the finished project afterward. Both the
working project and its learning documentation are required deliverables.

During implementation:

- Work autonomously on routine engineering decisions within the agreed scope.
- Keep updates focused on progress, important decisions, results and blockers.
- Do not interrupt development with lessons, exercises, quizzes or requests to
  read code. Record those teaching points for later.
- Explain a newly introduced significant tool briefly: what it does and why it
  is needed. Put the detailed explanation and alternatives in the learning notes.
- Resume interactive teaching when the user asks. Teach the whole structure and
  important decisions before individual functions or lines of code.

## 2. Start from the plan and existing work

Before implementation, read `plan.md`, the repository's applicable instructions,
and existing status/architecture notes. Inspect the current files and Git status.
Do not assume the project is empty or overwrite someone else's work.

Then:

1. Summarize the intended user-facing outcome in plain language.
2. Identify the milestones, their acceptance criteria and any actual prerequisites.
3. Maintain a short execution checklist mapped to those milestones.
4. Implement the next useful, verifiable increment and continue through the plan.

Revisit the relevant plan section before starting each phase. Keep planned,
implemented, verified, blocked and deferred work distinct. Existing code is not
proof that a feature works, and a previous status note is not current evidence.

Preserve decisions pinned by the plan. Before changing a significant architectural
decision, record the problem, chosen alternative and consequences in
`docs/adr/`. Ask the user when the change materially alters their intended scope,
cost, product behavior or commitments. Routine implementation choices do not
need repeated approval.

## 3. Continue until a real stopping point

- Continue after completing a milestone when the next milestone is authorized
  and no unresolved dependency blocks it. Do not repeatedly ask to continue.
- Investigate errors and attempt reasonable fixes within scope. Report the cause,
  the correction and verification when known; label uncertain diagnoses clearly.
- Ask for missing information early when it is genuinely necessary, while
  continuing independent work that does not depend on the answer.
- Respect prior authorization. Do not ask again for an already approved action
  or budget, and do not interpret a previous budget as a new allowance each run.
- Request any necessary approval only after preparing a concrete, reviewable
  proposal. Do not make the user approve an unexplained idea.
- Pause dependent work when it needs credentials, access, a material user
  decision or unapproved spending. Do not treat silence as approval.
- If the user asks for status during implementation, answer briefly and continue
  the active task unless they ask you to stop or change direction.

## 4. Make small, meaningful Git commits

The user authorizes incremental local commits for this project.

- Commit after a coherent improvement has been implemented and appropriately
  verified: a feature slice, a fix, a refactor or a useful documentation update.
- Keep commits reviewable. Do not save the entire project for one large commit,
  and do not create a commit for every trivial edit.
- Use short, descriptive messages, such as `feat: add baseline evaluation`,
  `fix: prevent data leakage`, or `docs: explain training pipeline`.
- Inspect the diff and stage only the intended files. Preserve unrelated user
  changes and other agents' work.
- Never commit credentials, tokens, private data or local runtime state. Use
  appropriate artifact storage for large datasets, model weights and generated
  outputs; commit their manifests or references when useful.
- Do not push, merge, publish or rewrite shared history unless authorized.
- If Git is unavailable or no repository exists, report that limitation rather
  than pretending commits were made. Initialize a repository when appropriate
  for the requested project and permitted by the workspace.

## 5. Maintain a cumulative learning guide

Create and update `docs/teaching-guide.md` as the project develops. Use concise
learning bullets, diagrams and small examples where helpful. It must explain the
actual project, not merely list file names or repeat the implementation log.

Cover:

- **Product:** the problem, intended users, a concrete example and the main flow.
- **Architecture:** major components, responsibilities, boundaries, where each
  component runs and how information moves between them.
- **Tools and libraries:** language/framework, purpose, version or configuration
  source, why selected, the main alternative and the practical trade-off.
- **Techniques:** important engineering, mathematical, statistical or ML concepts;
  what problem each solves and where the project applies it.
- **Decisions:** what was pinned by the plan versus chosen during implementation;
  alternatives considered and why they were accepted or rejected.
- **Failures:** what can go wrong, detection, recovery and remaining limitations.
- **Verification:** relevant tests, evaluations, measurements and evidence links.
- **Reproduction:** setup, build, run, test, evaluation and deployment commands as
  applicable; explain significant flags and what success looks like.
- **Reading path:** one or two useful entry files per concept and what to notice.

For each meaningful feature or milestone, add a short learning entry containing:

1. What the user can now do.
2. Where it fits in the overall architecture.
3. Tools, libraries and techniques involved.
4. The important decision, alternative and trade-off.
5. How it was verified, with the evidence and its limits.
6. Relevant files and one optional exercise for the later learning session.

Before introducing a file in a lesson, identify its language, framework or tool,
where it runs and its purpose. For example, explain that a `.tsx` file contains
React UI written in TypeScript before showing its code. Avoid function-by-function
walkthroughs unless requested. Explain unfamiliar terms in plain language.

## 6. Prepare for interviews throughout the build

Maintain `docs/interview-prep.md`. At meaningful milestones, record:

- A short product explanation and an architecture walkthrough.
- Two or three relevant questions, concise suggested answers grounded in the
  implementation, and likely follow-up questions or trade-offs.
- Links to supporting code, tests, design decisions and measured results.
- Relevant failure cases, alternatives and limitations.

Cover the topics that actually apply: data modeling, APIs, authorization,
concurrency, background work, ML formulation, training, evaluation, inference,
testing, debugging, deployment, performance and cost. Do not invent components
just to include interview keywords.

Distinguish what was built with agent assistance from what the user has personally
practiced and can explain. Never invent professional experience, customers,
adoption, benchmarks, accuracy, time savings or production readiness.

## 7. Verify results and preserve evidence

- Run checks appropriate to the change. Prefer meaningful behavior and invariant
  tests over tests that simply mirror the implementation.
- Include relevant failure paths and edge cases. Use realistic integration checks
  where a mock cannot establish the required behavior.
- Do not write unnecessary tests for low-impact documentation or cosmetic edits;
  check their links, rendering or other relevant properties instead.
- Use official documentation to resolve compatibility questions. Record dependency
  versions and use lockfiles or equivalent reproducibility mechanisms.
- Use available agent skills when relevant. Explain their purpose briefly on
  first use; inspect a skill before following it. Do not install a large collection
  of unrelated skills or tools merely because they are available.
- Record important results with the command, revision, configuration, environment,
  data/fixture version, date, outcome and limitations. Keep raw evidence where
  practical and safe; link it through `docs/evidence-index.md`.
- Distinguish mocked, local, hosted and production verification. Do not imply one
  proves another. A successful infrastructure deployment is not a working workflow.
- Never hide failed runs, silently weaken acceptance criteria or describe
  unexecuted tests as passing. State missed targets explicitly.

## 8. Additional rules when the project includes ML or AI

Apply this section only where relevant to the plan.

- Explain the prediction or generation task, inputs, outputs, intended use and
  success metric before selecting a complex model.
- Establish an appropriate simple baseline. Compare alternatives on consistent
  data and evaluation conditions; complexity must have a reason.
- Record dataset sources, permitted use, versions, preprocessing and known biases.
  Use synthetic or authorized data; do not expose private examples in artifacts.
- Separate training, validation and held-out testing. Fit preprocessing only on
  the appropriate training data. Account for entity/time leakage when relevant.
  Do not tune on the held-out test set and report it as untouched evaluation.
- Record seeds, splits, model identifiers, configurations, dependency versions,
  hardware and checkpoint/artifact provenance. Explain reproducibility limits.
- Choose metrics that fit the task and data balance. Include error analysis and
  relevant subgroup or robustness checks, with uncertainty where justified.
- Distinguish training performance, held-out performance and real-world behavior.
  Label synthetic, automated and human evaluations accurately.
- Track compute/provider usage against the agreed shared budget. Do not launch
  expensive training, hosted evaluations or cloud jobs without cost authorization.
- Explain the full data-to-training-to-evaluation-to-inference flow in the learning
  guide, including deployment, monitoring or retraining only if implemented.

## 9. Protect data, access and budgets

This reusable file grants no particular dollar budget, cloud access or permission
to use private data. Use the actual project's plan and explicit user authorization.

Keep secrets out of code, commits, logs, examples and chat. Use ignored local
configuration or an appropriate secret store. Request secure local setup when
credentials are needed; never ask the user to paste secrets into the conversation.

Before authorized paid work, check current pricing, the total approved allowance
and the projected cost. Metering can lag, and budget alerts are not spending caps.
Avoid unapproved purchases, subscriptions, paid-plan upgrades or external
commitments. Do not send messages to other people without explicit authorization.

For temporary resources, plan cleanup before creation, bound runtime and verify
what remains afterward. Record intentionally retained data/resources and their
continuing costs. Do not delete user data or unrelated resources as incidental
cleanup. Keep budgets and access decisions in project notes so another agent can
continue without repeating questions or assuming fresh authorization.

## 10. Communication: always say what is needed

Use clear, concise language. During active work, provide progress updates at
meaningful checkpoints and regularly enough that the user is not left wondering
whether work has stopped. Explain outcomes and uncertainty, not every tool call.

End **every progress update and final response** with a clear user-action line:

`Needed from you: nothing right now.`

When an action is required, replace that line with the exact next step and what
it unblocks. For example:

`Needed from you: start Docker Desktop so I can run the database integration tests.`

Separate actions required now from optional later review. Never write “nothing
right now” when a required user action is actually blocking progress. If requesting
permission, explain the concrete reason and the action or cost being approved.

## 11. Finish honestly and prepare the learning handoff

A milestone is complete only when its stated acceptance criteria are supported
by evidence. Record blocked, deferred, failed and unverified items explicitly.
Do not lower the plan's criteria to label the project finished. If an experimental
release is appropriate despite missed targets, record that decision and its scope.

Before the final handoff:

- Reconcile the implementation and evidence against every required milestone.
- Update `README.md`, the plan's status and known limitations.
- Verify setup and the documented demo to the extent required by the plan.
- Complete the teaching guide, interview preparation and evidence index.
- Record final test/evaluation outcomes, costs and cleanup or retained resources.
- Commit the final coherent changes and report the Git state accurately.
- State what works, what remains limited, how to run it and where learning begins.

When the user starts learning, use the prepared guide in this order: product
example, architecture, main data/request flow, tools and techniques, key decisions
and trade-offs, failures and evidence, then interview practice. Adapt the pace;
do not require understanding every function before explaining the whole project.
