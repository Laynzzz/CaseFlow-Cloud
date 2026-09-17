# Repeatable checks and scan review

The PR workflow builds and checks the frontend, generated API contract, Java and
Python services, declared critical-module coverage, images and Terraform source.
It uses synthetic database/broker/object-store dependencies and no live AI or AWS
credentials. Workflow source is implemented; a hosted GitHub run is not claimed.

From a clean checkout with Node, Java 21, Python, Docker and Terraform on PATH:

```text
node scripts/ci.mjs bootstrap
node scripts/ci.mjs install
node scripts/ci.mjs check
node scripts/ci.mjs up
node scripts/ci.mjs test
node scripts/ci.mjs images
node scripts/ci.mjs scan
node scripts/ci.mjs terraform
node scripts/ci.mjs stop
```

The owned `.env.ci` contains generated synthetic credentials and is ignored.
CI uses the development dependency ports, so stop an existing development stack
before `up`; never replace its credentials or volumes. For an already running
local development fixture, use `--env-file .env` for checks/tests instead of `up`.
Java and Python database suites run serially to avoid local connection exhaustion.

Manual workflow dispatch can enable `broad`; locally run `test --broad` for the
process-crash suites. The bounded load and packaged-release commands are in
[load methodology](../load-methodology.md) and [observability](observability.md).
Keep those results separate from PR tests and never infer child-process coverage
from the parent process. The numeric 80% target covers only four explicitly listed
modules in `tests/ci/coverage-scope.json`; authorization and other invariants have
separate tests. A green percentage does not prove correctness.

## Security scan policy

Pinned Gitleaks scans both a credential-free worktree snapshot and Git history.
The default rule set remains enabled. `.gitleaks.toml` narrowly matches reviewed
SHA-256 manifest entries and exact endpoint/prose strings with path AND content
conditions. No file, history commit or generic secret rule is globally exempted.
Raw JSON is fully redacted. Never upload source snapshots, image tarballs, scanner
caches, `.env` files or authentication artifacts as CI evidence.

Trivy scans dependencies and immutable API/worker image IDs. Tomcat was aligned
to 11.0.25; the worker moved to a pinned Debian 13 Python image with four explicit
OS package updates. Scanner reports retain all HIGH/CRITICAL findings, including
unfixed findings. The API and dependency scans had none at the verification date.

The September 17 worker report contains 44 HIGH package findings covering eight
unfixed CVEs. They remain visible, with exact package/version reviews in
[`vulnerability-reviews.json`](../../tests/ci/vulnerability-reviews.json), expiring
October 1. The review script rejects changed versions, a newly available fix,
CRITICAL severity, another image/distro or language package, unknown findings,
and expired reviews. Tests exercise these rejection paths. This is delegated
engineering review, not independent security certification or zero-vulnerability
status. The workflow must fail again when these assumptions change.

The reviewed paths are ncurses `infocmp`, privileged ACL/mount/nsenter operations,
systemd-homed and Perl Archive::Tar. Application source invokes Python children
for bounded parsing/provider work; it does not invoke those tools. A container
probe verifies UID 10001, zero effective capabilities, no-new-privileges, and
absence of systemd-homed/Archive::Tar. Read-only filesystem/no host mounts are
enforced by the local release profile. Cloud runtime assumptions require their
own confirmation before deployment acceptance. Each review links its Debian
security-tracker source; upstream classifies several as minor or postponed.

The review never substitutes for installing available fixes. Keep original raw
scan outputs and the adjudication side by side. Scanning uses exported image
tarballs without mounting the Docker socket. The Java vulnerability DB exceeds
the small scanner tmpfs; its temporary download uses the owned report directory.
An operational scanner failure cannot be treated as a clean scan or reuse a
previous image report.
