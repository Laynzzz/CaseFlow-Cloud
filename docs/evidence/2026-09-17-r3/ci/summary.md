# Local CI and patched release verification

September 17, 2026, Windows/Docker Desktop. Workflow source is prepared for Linux
GitHub runners; no hosted workflow execution is claimed. The archive records the
base revision, dirty source hashes, immutable image IDs, actual reports and
normalization in [archive-manifest.json](archive-manifest.json). Larger reports
are gzip-compressed; decompress before inspection. Original scan/coverage failures
are retained in the initial-findings and before-os-patches folders.

- Static gate: frontend formatting/type/build, generated contract stability,
  Python fatal-error lint, CI policy tests and Node helper guards pass.
- Targeted gate: 49 Java and 121 Python tests pass.
- Broader release gate: 60 Java tests pass, one separately opt-in query benchmark
  skips; 174 Python tests pass. The measured query benchmark has its own prior
  evidence and is not silently counted as rerun here.
- Declared branch coverage: Purchase 25/26 (96.15%); tenant-filtered CaseQueries
  36/36; CompletionHandler 59/60 (98.33%); worker jobs 24/24. Every module exceeds
  the unchanged 80% gate. This is not repository-wide coverage or proof of all
  authorization behavior. New tests cover invalid completion provenance,
  monotonic status, pagination/visibility and durable job admission invariants.
- Terraform format/init with backend disabled/schema validation, two mocked
  plans and bootstrap-error redaction pass offline. No account plan/apply ran.
- Default and configurable-origin smoke paths pass against the local release,
  including the immutable network-disabled helper image used by the configured
  path. No cloud, real-user or hosted-AI behavior is implied.

## Scan outcome and limits

Gitleaks worktree/history and dependency scans pass. Exact path-and-content
allowlists remove reviewed source-checksum, endpoint and ordinary-prose false
positives while retaining default secret rules. The patched Java image has zero
reported HIGH/CRITICAL findings in this scan after the Tomcat 11.0.25 update.

The worker moved to the pinned Python 3.12.14 Debian 13 image and applied four
version-pinned OS security updates. Its raw scanner exit remains **1** because
44 HIGH package findings cover eight unfixed CVEs. The review gate accepts only
these documented exact versions until October 1; it rejects fixed, CRITICAL,
unknown, expired or out-of-scope findings. The result is **passed with reviewed
exceptions**, never zero vulnerabilities. Rationale, Debian advisory links and
limitations are in the [CI runbook](../../../runbooks/ci.md) and policy JSON.
This is Codex engineering review under delegated decisions, not an independent
security assessment. A runtime probe verifies the local privilege assumptions
and absent affected modules; cloud assumptions remain unverified.

The initial Java container scan failed downloading its large vulnerability DB
into a 256 MiB tmpfs. Moving temporary download storage to the owned report
directory allowed scanning to complete; a scanner operational failure was never
treated as a clean result. Raw image archives and scanner caches are not committed.

## Patched image smoke

`security-patched` deployed with monitoring. PKCE, SPA routes, anonymous API and
management denial, cross-tenant denial, two approvals, real DOCX/checksum/content
and preservation of the prior approved case passed. Earlier load/rollback/browser
evidence belongs to its recorded images; it is not relabeled as this candidate.
No new model calls or cloud resources were used.
