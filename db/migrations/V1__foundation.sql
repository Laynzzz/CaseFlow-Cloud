-- The migration role owns DDL. Runtime roles receive only explicit grants.
CREATE SCHEMA core AUTHORIZATION caseflow_migrator;
CREATE SCHEMA worker AUTHORIZATION caseflow_migrator;
REVOKE ALL ON SCHEMA core, worker FROM PUBLIC;
GRANT USAGE ON SCHEMA core TO caseflow_api;
GRANT USAGE ON SCHEMA worker TO caseflow_worker;

CREATE TABLE core.system_metadata (
    key text PRIMARY KEY,
    value text NOT NULL
);
INSERT INTO core.system_metadata (key, value) VALUES ('schema_version', '1');
GRANT SELECT ON core.system_metadata TO caseflow_api;
