# CaseFlow Cloud

Multi-tenant purchase-approval platform with an evidence-grounded AI review assistant. The full specification is in `plan.md` (revision 2026-09-11). Read it before starting any phase.

Delivery is three gated releases: R1 working SWE product (tenants, approvals, async DOCX, basic cloud), R2 AI-assisted review (extraction, policy retrieval, cited brief, held-out evaluation), R3 reliability and portfolio evidence. A release is done when its exit gate passes, not when code exists. Do not claim AI implementation before R2.

## This is a learn-while-build project

Current user preference, 2026-09-14: implement the whole project first and teach
afterward. Record architecture, responsibilities, important decisions, alternatives,
trade-offs, failure handling, and verification in `docs/teaching-guide.md` while
building. Keep progress updates brief; defer walkthroughs, exercises, and interview
quizzes until requested. Teach structure and design before individual functions.
Identify language, framework, runtime, and purpose before introducing a file.
This overrides the timing of the teaching instructions below; preserve their
substance in the written guide.

The user is building this to learn, not only to ship. Treat every task as a teaching moment as well as an implementation task.

- **Explain the tool before using it.** When you introduce a tool, library, or command for the first time (Flyway, Testcontainers, Spring Data JDBC, the transactional outbox, k6, a Terraform module, a Gradle task, pgvector, an embedding provider), say in a few sentences what it is, what problem it solves in this project, and what the alternatives would have been.
- **Explain the why, not only the what.** When you make a design choice, state the reasoning and the trade-off. When plan.md pins a decision, connect the code back to the plan's stated reason.
- **Teach the concept behind the code.** For core ideas in this project (tenant isolation, idempotency keys bound to a request hash, optimistic concurrency, inbox/outbox, leases and fencing tokens, at-least-once delivery, RBAC, trace propagation, cursor pagination, presigned URLs, grounded retrieval and citations, held-out evaluation splits), give a short plain-language explanation the first time the concept shows up in code, and point to where in the code it is enforced.
- **Show the commands, and say what they do.** When running a build, migration, test, eval, or deploy, show the command and explain each significant flag. The user should be able to rerun it alone.
- **Point out what to look at.** After implementing something, name one or two files the user should read to understand the mechanism, and what to notice in them.
- **Invite the user to do parts themselves** when a task is a good learning exercise and low risk, but do not block on it. Say what they could try and continue.
- **Keep explanations proportional.** A one-line command gets one sentence. A new architectural pattern gets a short paragraph. Do not repeat an explanation already given in this session.
- **Be honest about limits.** If a tool behaves unexpectedly or a claim is unverified, say so. The plan forbids fabricated benchmarks, evaluations, users, and adoption, and that applies to explanations too.

## Working rules from plan.md section 21

- User direction (2026-09-15): after completing and verifying R2, proceed directly
  to R3 if no unresolved problem blocks it. No new confirmation is needed for
  authorized implementation. Preserve short commits and cumulative teaching notes.

- Work phase by phase and demonstrate the exit criterion before marking a phase complete.
- Create an ADR under `docs/adr/` before changing a pinned architecture decision. Routine implementation choices do not need confirmation unless they materially change scope, cost authority, or product behavior.
- Use official documentation for compatible versions. Pin versions, images, lockfiles, the Gradle Wrapper, and model/embedding identifiers. Installed global tooling does not establish compatibility.
- Keep changes reviewable and maintain `docs/evidence-index.md` linking claims to code, tests, and raw artifacts.
- Never fabricate benchmarks, evaluations, users, or adoption.
- Use synthetic data only. Never add credentials, personal resumes, contact details, tokens, or real application data.
- At phase end update README status, known limits, one or two files the user should read, and the next reproducible command.

## Toolchain on this machine

Installed and verified on 2026-09-11. Open a fresh terminal so PATH changes are visible.

| Tool | Notes |
| --- | --- |
| Java 21 (Temurin) | `JAVA_HOME` set at machine level |
| Gradle 9.7.1 | `~/.local/share/gradle-9.7.1/bin`, not from winget; use it once to generate the committed wrapper |
| Python 3.12 | use `py -3.12`; plain `python` in Git Bash is still 3.10 |
| Node 22 | npm global bin is `%APPDATA%\npm` |
| Docker Desktop | for `compose.yaml` |
| Terraform, k6, gh | installed via winget |
| jdtls, pyright, typescript-language-server | back the LSP plugins |
| winget | not on PATH; call `$env:LOCALAPPDATA\Microsoft\WindowsApps\winget.exe` |

## Claude Code plugins and skills in use

feature-dev, pr-review-toolkit, security-guidance, claude-security, commit-commands, claude-md-management, context7, playwright, terraform, github, jdtls-lsp, pyright-lsp, typescript-lsp, example-skills (webapp-testing, frontend-design). Use context7 for version-accurate library docs rather than memory. If the R2 model provider is Anthropic, load the `claude-api` skill before writing provider code.
