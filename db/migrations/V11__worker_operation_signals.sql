-- Operational metadata only; worker still cannot read core business tables.
CREATE VIEW core.worker_operation_signals AS
SELECT 'API_OUTBOX_PENDING'::text AS kind, o.tenant_id, o.case_id,
       NULL::uuid AS job_id, o.event_id, o.created_at AS observed_at
FROM core.outbox o WHERE o.published_at IS NULL
UNION ALL
SELECT 'APPROVED_MISSING_REQUEST', c.tenant_id, c.id, c.generation_id,
       NULL::uuid, c.updated_at
FROM core.cases c
WHERE c.state = 'APPROVED' AND NOT EXISTS (
    SELECT 1 FROM core.job_requests j
    WHERE j.tenant_id=c.tenant_id AND j.case_id=c.id
      AND j.job_id=c.generation_id AND j.kind='DOCUMENT')
UNION ALL
SELECT 'APPROVED_MISSING_WORKER_JOB', c.tenant_id, c.id, j.job_id,
       NULL::uuid, j.updated_at
FROM core.cases c JOIN core.job_requests j
  ON j.tenant_id=c.tenant_id AND j.case_id=c.id
 AND j.job_id=c.generation_id AND j.kind='DOCUMENT'
WHERE c.state='APPROVED' AND NOT EXISTS (
    SELECT 1 FROM worker.jobs w
    WHERE w.tenant_id=j.tenant_id AND w.job_id=j.job_id AND w.attempt=j.attempt);
GRANT SELECT ON core.worker_operation_signals TO caseflow_worker;
