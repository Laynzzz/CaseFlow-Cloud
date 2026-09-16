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
