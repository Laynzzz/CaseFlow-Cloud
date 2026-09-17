# Local restart check

Observed 2026-09-17 UTC (2026-09-16 local). Docker Desktop initially failed
on inaccessible temporary Windows socket entries. After stopping Desktop,
the two exact runtime directories were renamed to recovery backups and recreated.
No Docker volumes were reset. The engine and existing PostgreSQL, Kafka and
object-store containers then started.

Keycloak exposed a separate reproducible project configuration failure:
the entire generated directory was mounted as its realm import directory.
After previous demo runs, `demo-ids.json` was interpreted as a realm and startup
failed with `Unrecognized field "acmeId"`. Compose now mounts only
`caseflow-realm.json`. Existing identity data remains on the same volume.

Verification: `docker compose up -d keycloak`, followed by the existing
`tests/e2e/oidc-session.mjs` authorization-code/PKCE helper signing in the
synthetic requester and fetching `/api/v1/me`, succeeded with one organization.
This is an actual local restart/sign-in check, not a cloud deployment check.

The external socket symptoms match reports in Docker's
[issue tracker](https://github.com/docker/desktop-feedback/issues/531).
The project import failure was diagnosed directly from local container logs.
