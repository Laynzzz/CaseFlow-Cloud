# 0003: R2 evidence ingestion and sequencing

Date: 2026-09-14. Status: accepted implementation direction.

The user explicitly requested starting R2 while R1 cloud and broader operations
gates remain open. R1 is not marked complete. This changes implementation order,
not the release gates or the pinned Java/Python/PostgreSQL architecture.

Quote and policy bytes become immutable tenant-owned sources. Java controls
upload authorization, source versions, publication, case pins and human
acceptance. Python parses and indexes through durable leased jobs. Policy jobs
must have a policy/source aggregate, not an invented purchase case. Generalize
the existing job contract while preserving document behavior and ownership views.

Text parsing runs in a child process: 10 MiB input, 50 pages, one million extracted
characters, 512 MiB process memory and 20 seconds wall time. Linux also bounds CPU
time; Windows uses an OS Job Object memory limit. Fail closed if limits cannot be
installed. This contains parser resource use; it is not a complete hostile-code
sandbox. Container/network isolation and deployment checks remain separate gates.

Page-local character offsets refer to the exact extracted text, not positions in
the original PDF binary. Fixed overlapping page chunks preserve deterministic
citations; they may split sentences or tables. Version parser and chunk strategy
so later quality changes cannot silently reinterpret an old citation.

Before prompt work, check in a family-separated synthetic evaluation split and
rubric. Generated reference consistency is not human annotation verification.
Human review, live budgeted runs, retrieval comparison and claim grading remain
required; no mock score may be presented as model quality.

Sources checked: [pypdf text extraction](https://pypdf.readthedocs.io/en/stable/user/extract-text.html),
[OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs).
Structured output constrains response shape; it does not prove source support.
