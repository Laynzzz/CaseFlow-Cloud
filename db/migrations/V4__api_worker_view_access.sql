-- SELECT on a view also requires USAGE on its schema. This does not grant
-- access to worker base tables, which remain private to the worker role.
GRANT USAGE ON SCHEMA worker TO caseflow_api;
