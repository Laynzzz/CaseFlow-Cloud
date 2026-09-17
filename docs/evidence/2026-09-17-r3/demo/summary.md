# Browser journey and clean-checkout rehearsal

Actual local evidence on September 17, 2026. The browser used the packaged
`telemetry-candidate` release recorded in `browser-release.json`; later images
have their own build and smoke records. No live AI calls or cloud resources.

Using Playwright CLI 0.1.20 and real Keycloak sign-in, the requester created a
synthetic USD 4,200 laptop request, selected the published workflow/template,
assigned manager then finance, and submitted. Separate manager and finance
sessions approved in order. The UI showed document success and its download
button produced a 36,720-byte DOCX containing the expected vendor, price and
description with no unresolved template markers. The SHA-256 is recorded in
`manifest.json`. The manual fallback message appeared with AI actions disabled.

Desktop and 390-pixel mobile screenshots were visually inspected. The mobile
document page's observed scroll width equaled its 390-pixel viewport. This is
a focused flow/layout check, not a complete accessibility or browser matrix.
The original in-app browser runtime could not initialize, so this evidence came
from an isolated Playwright browser, not the user's existing signed-in tab.

Known UI limits observed: favicon requests return 401, and organization selection
is in-memory. Reloading a deep link after sign-in can select the first organization
and correctly return Resource not found; choosing the intended organization and
opening the request from its list works. This is a usability limitation, not
cross-tenant access. Authentication timeout during the initial stale login page
was handled by restarting sign-in. No authentication snapshots/tokens are archived.

## Clean checkout

A fresh local clone at `91f15c3` had no tracked or untracked changes. With Node and
Docker only, the release helper built both images from that checkout and deployed
them. The helper completed a new synthetic request through PKCE, approvals,
Kafka/worker completion, tenant denial and verified DOCX download; it also checked
the prior approved case. The manifest records `dirty: false` and immutable IDs.

This rehearsal deliberately reused the existing isolated release database/object
volumes and copied their ignored synthetic credentials. It proves clean source
packaging and operation with existing data, not another empty-database deployment.
The separate [packaged baseline](../release-baseline/README.md) records that fresh
database gate. The original development preview and its volumes were untouched.
The final clean-checkout image scan is recorded separately in `scans/`; the worker
still has the documented expiring exceptions, not zero vulnerabilities.

Reproduce using the [packaged demo instructions](../../../demo-scenario.md).
