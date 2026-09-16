# Development skills installed on 2026-09-15

Installed from the official `openai/skills` curated collection at revision
`49f948faa9258a0c61caceaf225e179651397431`, using the system skill-installer.
These are local agent instructions and helper scripts, not application packages.
They become available for automatic skill selection on the next user turn.

| Skill | Intended use | Limit |
| --- | --- | --- |
| security-best-practices | Review React/TypeScript and Python security choices | Does not supply Java/Spring-specific guidance |
| security-threat-model | Examine tenant boundaries, hostile uploads, prompt injection and spend abuse | Repository-grounded review, not proof of complete security |
| playwright | Maintain repeatable browser acceptance tests | Existing in-app browser control continues to use its own installed skill |
| gh-fix-ci | Diagnose GitHub Actions failures when CI is exercised | Installation does not authenticate GitHub or execute workflows |

The installer reported all four as installed and a second inventory confirmed
them. Existing browser, OpenAI documentation and document skills remain available.
No application dependency, cloud resource or paid service was added. Skills are
selected when their actual task applies; installation alone does not run reviews.


## User-requested additions

Installed frontend-design from anthropics/skills at
`34040c9c568585f6929bedeaad110ad08f079624`, and all 14 skills from
obra/superpowers at `b36e0829c6d0140e93cfef2ca599b1b07d4a7797`.
Frontend design informs future interface work. Superpowers supplies planning,
implementation, debugging, review and verification workflows. All installations
contain SKILL.md and become automatically discoverable on the next user turn.
Existing user instructions to act independently and teach afterward take priority
over optional workflow pauses; no application or model dependency was added.
