-- The worker may protect immutable artifact references during one external
-- deletion without acquiring UPDATE/DELETE privileges on artifact metadata.
-- This function grants only a lock; it neither returns data nor mutates it.
CREATE FUNCTION worker.lock_artifacts_for_cleanup() RETURNS void
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, worker
AS $$
BEGIN
    LOCK TABLE worker.artifacts IN SHARE MODE;
END;
$$;
REVOKE ALL ON FUNCTION worker.lock_artifacts_for_cleanup() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worker.lock_artifacts_for_cleanup() TO caseflow_worker;
