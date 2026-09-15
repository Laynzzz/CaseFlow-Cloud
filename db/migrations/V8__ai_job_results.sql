CREATE TABLE worker.ai_results (
    tenant_id uuid NOT NULL,
    job_id uuid NOT NULL,
    attempt integer NOT NULL,
    fence bigint NOT NULL,
    result jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id,job_id),
    FOREIGN KEY (tenant_id,job_id) REFERENCES worker.jobs(tenant_id,job_id)
);
CREATE VIEW worker.assistant_results AS SELECT * FROM worker.ai_results;
CREATE VIEW worker.ai_availability AS SELECT total_limit_usd>0 AND tenant_daily_limit_usd>0 AS enabled FROM worker.ai_budget;
CREATE OR REPLACE VIEW worker.job_results AS
    SELECT j.tenant_id,j.job_id,j.case_id,j.source_id,j.kind,j.attempt,j.fence,j.status,j.failure_code,
        CASE WHEN j.kind='DOCUMENT' THEN a.object_key IS NOT NULL
             WHEN j.kind='INGESTION' THEN i.source_id IS NOT NULL
             ELSE ai.job_id IS NOT NULL END AS result_exists
    FROM worker.jobs j LEFT JOIN worker.artifacts a USING (tenant_id,job_id)
    LEFT JOIN worker.ingestions i USING (tenant_id,job_id)
    LEFT JOIN worker.ai_results ai USING (tenant_id,job_id);
-- Current authorization is recomputed before sending facts and selecting results.
CREATE VIEW core.worker_ai_eligible AS
    SELECT j.tenant_id,j.job_id FROM core.job_requests j
    JOIN core.cases c ON c.tenant_id=j.tenant_id AND c.id=j.case_id
    JOIN core.memberships m ON m.tenant_id=j.tenant_id AND m.user_id=j.requested_by AND m.active
    WHERE j.kind IN ('EXTRACTION','REVIEW') AND c.version=(j.input->>'revision')::bigint
      AND c.state IN ('DRAFT','ACTIVE')
      AND (('ADMIN'=ANY(m.roles)) OR c.owner_id=j.requested_by OR EXISTS(
          SELECT 1 FROM core.assignments a WHERE a.tenant_id=c.tenant_id AND a.case_id=c.id AND a.user_id=j.requested_by))
      AND m.roles && ARRAY['ADMIN','REQUESTER','APPROVER']::text[]
      AND (j.kind<>'EXTRACTION' OR (c.state='DRAFT' AND c.owner_id=j.requested_by AND 'REQUESTER'=ANY(m.roles)
          AND EXISTS(SELECT 1 FROM core.sources s WHERE s.tenant_id=j.tenant_id AND s.id=j.source_id AND s.case_id=j.case_id AND s.state='INDEXED')))
      AND (j.kind<>'REVIEW' OR NOT EXISTS (
          SELECT 1 FROM jsonb_array_elements_text(j.input->'policyIds') requested(id)
          WHERE NOT EXISTS(SELECT 1 FROM core.case_policy_pins p JOIN core.sources s ON s.tenant_id=p.tenant_id AND s.id=p.source_id
              WHERE p.tenant_id=j.tenant_id AND p.case_id=j.case_id AND p.source_id=requested.id::uuid
                AND (s.state='PUBLISHED' OR (c.state='ACTIVE' AND s.state='DEACTIVATED')))));
GRANT SELECT ON core.worker_ai_eligible TO caseflow_worker;
GRANT SELECT,INSERT ON worker.ai_results TO caseflow_worker;
GRANT SELECT ON worker.assistant_results,worker.ai_availability TO caseflow_api;
