# CaseFlow Cloud agent instructions

Read `plan.md` before starting work on a phase. Preserve the learn-while-build guidance in `CLAUDE.md`; this file makes that guidance explicit for agents working in this repository.

## Learn while building

### Current user preference (2026-09-14): build first, teach afterward

Implement the full project through the plan's release gates. During implementation,
keep commentary to concise progress, important outcomes, and actual blockers.
Do not interrupt work for lessons, code walkthroughs, exercises, or interview quizzes.
This preference supersedes the timing of the teaching instructions below.

Maintain `docs/teaching-guide.md` as a separate, cumulative guide for later lessons.
Focus on the whole architecture, component responsibilities, request/job flows,
important decisions, alternatives, trade-offs, failure handling, and evidence.
For each component/file introduced in a lesson, identify its language, framework,
where it runs, and purpose before showing code. Avoid function-by-function teaching
unless requested. Keep planned, implemented, and verified behavior distinct.
Update the guide and interview preparation as features land so later teaching
reflects the actual project. Resume interactive lessons only when the user asks.

This is a learning project as well as a product implementation. Help the user understand, explain, and independently work on the system. Shipping code alone does not satisfy the user's goal.

- Start with the user-facing behavior and a concrete purchase-request example before introducing implementation details. Use plain language and define unfamiliar terms.
- Before first using a new tool, library, service, or significant command, explain what it does, why this project needs it, and the main alternative or trade-off. Keep routine explanations short and avoid repeating explanations already given in the session.
- Explain design decisions: the problem, the chosen approach, why it fits, and its limitations. Distinguish decisions pinned by the plan from choices made during implementation.
- Teach the concept behind the implementation and link to the actual files where it is enforced. Examples include permissions, tenant isolation, SQL constraints, transactions, optimistic concurrency, idempotency, outboxes, job leases, fencing tokens, retrieval, and AI evaluation.
- Show reproducible build, migration, test, evaluation, and deployment commands. Explain significant flags and how to recognize success or diagnose a relevant failure. Never expose secrets in examples.
- After a meaningful feature, explain what changed, why it works, how it was verified, and any remaining limits. Identify one or two files to read and what to notice in them.
- Offer occasional small, optional exercises that let the user practice. Continue authorized work without making quizzes or exercises a prerequisite.
- Keep lessons proportional to the work and the user's current understanding. If the user is confused, return to a concrete example before adding more terminology.

## Prepare the user for project interviews

Interview preparation is an ongoing part of building this project, not only a final resume task.

- At meaningful feature or phase milestones, include a short interview checkpoint with two or three relevant questions, a concise suggested answer grounded in this implementation, and a likely follow-up or trade-off.
- Cover both the product explanation and implementation details: what problem it solves, the request lifecycle, architecture boundaries, data modeling, SQL, authorization, concurrency, background processing, AI grounding and evaluation, testing, debugging, deployment, performance, and cost as those areas are built.
- Connect answers to actual code, tests, design records, and measured results. Teach the user to explain the reasoning and failure cases rather than memorize terminology.
- Maintain `docs/interview-prep.md` as implementation progresses, recording completed features, questions and answers, supporting file or evidence links, trade-offs, and known limitations. Clearly separate planned behavior from implemented and verified behavior.
- Help the user practice a short project overview and deeper walkthroughs of specific decisions. Explain what happens when a dependency fails, requests repeat, permissions change, or simultaneous actions conflict where relevant.
- Never invent experience, users, adoption, benchmarks, AI quality, or production readiness. Suggested interview answers must accurately describe the work and evidence available.

## Execution expectations

- Follow the releases and acceptance gates in `plan.md`; demonstrate the relevant exit criteria before marking work complete.
- Preserve the plan's architecture and scope. Record an ADR before changing a pinned architectural decision.
- Use synthetic data, keep changes reviewable, and link engineering claims to evidence.
- Explain and continue authorized work. Do not repeatedly ask for permission for routine implementation or turn teaching into a reason to leave work unfinished.
