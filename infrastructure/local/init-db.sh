#!/usr/bin/env bash
set -euo pipefail
# psql quotes each variable as a SQL literal; credentials never enter source files.
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=ON_ERROR_STOP=1 \
  --set=api_password="$DB_API_PASSWORD" \
  --set=worker_password="$DB_WORKER_PASSWORD" \
  --set=migrator_password="$DB_MIGRATOR_PASSWORD" <<'SQL'
CREATE ROLE caseflow_migrator LOGIN PASSWORD :'migrator_password';
CREATE ROLE caseflow_api LOGIN PASSWORD :'api_password';
CREATE ROLE caseflow_worker LOGIN PASSWORD :'worker_password';
REVOKE ALL ON DATABASE caseflow FROM PUBLIC;
GRANT CONNECT ON DATABASE caseflow TO caseflow_migrator, caseflow_api, caseflow_worker;
GRANT CREATE ON DATABASE caseflow TO caseflow_migrator;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA public TO caseflow_migrator;
SQL
