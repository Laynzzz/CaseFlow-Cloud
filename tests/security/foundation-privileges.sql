-- Read-only assertions against PostgreSQL's real privilege catalog.
DO $$
BEGIN
    IF NOT has_table_privilege('caseflow_api', 'core.system_metadata', 'SELECT') THEN
        RAISE EXCEPTION 'API cannot read readiness metadata';
    END IF;
    IF has_table_privilege('caseflow_api', 'core.system_metadata', 'INSERT,UPDATE,DELETE,TRUNCATE') THEN
        RAISE EXCEPTION 'API can mutate migration-owned metadata';
    END IF;
    IF has_schema_privilege('caseflow_api', 'core', 'CREATE')
       OR has_schema_privilege('caseflow_api', 'public', 'CREATE')
       OR has_database_privilege('caseflow_api', 'caseflow', 'CREATE') THEN
        RAISE EXCEPTION 'API unexpectedly has DDL privileges';
    END IF;
    IF has_schema_privilege('caseflow_api', 'worker', 'USAGE')
       OR has_schema_privilege('caseflow_worker', 'core', 'USAGE') THEN
        RAISE EXCEPTION 'Runtime schema boundary is not enforced';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles
               WHERE rolname IN ('caseflow_api', 'caseflow_worker', 'caseflow_migrator')
                 AND (rolsuper OR rolcreaterole OR rolcreatedb OR rolbypassrls)) THEN
        RAISE EXCEPTION 'Application or migration role has excessive cluster privileges';
    END IF;
    IF (SELECT count(*) FROM public.flyway_schema_history WHERE version = '1' AND success) <> 1 THEN
        RAISE EXCEPTION 'Expected one successful foundation migration';
    END IF;
END $$;
SELECT 'PASS: runtime grants, schema boundaries, non-superuser roles, one migration' AS result;
