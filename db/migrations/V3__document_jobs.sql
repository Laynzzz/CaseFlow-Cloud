CREATE TABLE core.template_versions (
    tenant_id uuid NOT NULL REFERENCES core.tenants(id),
    id uuid NOT NULL,
    name text NOT NULL CHECK (length(name) BETWEEN 1 AND 120),
    state text NOT NULL DEFAULT 'UPLOADING' CHECK (state IN ('UPLOADING','VALIDATED','PUBLISHED')),
    upload_key text NOT NULL UNIQUE,
    object_key text UNIQUE,
    sha256 text,
    byte_size integer NOT NULL CHECK (byte_size BETWEEN 1 AND 10485760),
    version bigint NOT NULL DEFAULT 0,
    created_by uuid NOT NULL REFERENCES core.identities(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id,id),
    CHECK (state='UPLOADING' OR (object_key IS NOT NULL AND sha256 ~ '^[a-f0-9]{64}$'))
);
CREATE FUNCTION core.guard_template() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.state='PUBLISHED' THEN
        RAISE EXCEPTION 'Published template is immutable' USING ERRCODE='23514';
    END IF;
    IF OLD.state='VALIDATED' AND (NEW.object_key IS DISTINCT FROM OLD.object_key
        OR NEW.sha256 IS DISTINCT FROM OLD.sha256 OR NEW.byte_size<>OLD.byte_size) THEN
        RAISE EXCEPTION 'Validated template bytes are immutable' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER immutable_template BEFORE UPDATE OR DELETE ON core.template_versions
    FOR EACH ROW EXECUTE FUNCTION core.guard_template();
ALTER TABLE core.cases ADD COLUMN template_id uuid;
ALTER TABLE core.cases ADD CONSTRAINT case_template FOREIGN KEY (tenant_id,template_id)
    REFERENCES core.template_versions(tenant_id,id);
CREATE FUNCTION core.guard_case_template() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.state<>'DRAFT' AND NEW.template_id IS DISTINCT FROM OLD.template_id THEN
        RAISE EXCEPTION 'Started case template is immutable' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER immutable_case_template BEFORE UPDATE ON core.cases
    FOR EACH ROW EXECUTE FUNCTION core.guard_case_template();

CREATE TABLE core.job_requests (
    tenant_id uuid NOT NULL,
    job_id uuid NOT NULL,
    case_id uuid NOT NULL,
    kind text NOT NULL CHECK (kind IN ('DOCUMENT','INGESTION','EXTRACTION','REVIEW')),
    attempt integer NOT NULL DEFAULT 1 CHECK (attempt>0),
    status text NOT NULL DEFAULT 'QUEUED' CHECK (status IN ('QUEUED','RUNNING','RETRY_WAIT','SUCCEEDED','FAILED')),
    input jsonb NOT NULL,
    input_hash text NOT NULL CHECK (input_hash ~ '^[a-f0-9]{64}$'),
    requested_by uuid NOT NULL REFERENCES core.identities(id),
    failure_code text,
    last_fence bigint NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id,job_id),
    FOREIGN KEY (tenant_id,case_id) REFERENCES core.cases(tenant_id,id)
);
CREATE FUNCTION core.guard_job_input() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.input IS DISTINCT FROM OLD.input OR NEW.input_hash<>OLD.input_hash
       OR NEW.case_id<>OLD.case_id OR NEW.kind<>OLD.kind OR NEW.requested_by<>OLD.requested_by THEN
        RAISE EXCEPTION 'Job input is immutable' USING ERRCODE='23514';
    END IF;
    IF OLD.status='SUCCEEDED' AND NEW IS DISTINCT FROM OLD THEN
        RAISE EXCEPTION 'Successful job is terminal' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER immutable_job_input BEFORE UPDATE ON core.job_requests
    FOR EACH ROW EXECUTE FUNCTION core.guard_job_input();
CREATE TABLE core.event_inbox (
    event_id uuid PRIMARY KEY,
    received_at timestamptz NOT NULL DEFAULT now(),
    disposition text NOT NULL CHECK (disposition IN ('APPLIED','DUPLICATE','STALE','QUARANTINED')),
    reason text
);
CREATE TABLE worker.inbox (
    event_id uuid PRIMARY KEY,
    received_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE worker.jobs (
    tenant_id uuid NOT NULL,
    job_id uuid NOT NULL,
    case_id uuid NOT NULL,
    kind text NOT NULL,
    attempt integer NOT NULL CHECK (attempt>0),
    input_hash text NOT NULL,
    status text NOT NULL CHECK (status IN ('QUEUED','RUNNING','RETRY_WAIT','SUCCEEDED','FAILED')),
    fence bigint NOT NULL DEFAULT 0 CHECK (fence>=0),
    lease_owner uuid,
    lease_until timestamptz,
    executions integer NOT NULL DEFAULT 0,
    available_at timestamptz NOT NULL DEFAULT now(),
    failure_code text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id,job_id),
    FOREIGN KEY (tenant_id,job_id) REFERENCES core.job_requests(tenant_id,job_id),
    FOREIGN KEY (tenant_id,case_id) REFERENCES core.cases(tenant_id,id),
    CHECK ((status='RUNNING')=(lease_owner IS NOT NULL AND lease_until IS NOT NULL))
);
CREATE INDEX worker_dispatch ON worker.jobs(available_at,created_at)
    WHERE status IN ('QUEUED','RETRY_WAIT','RUNNING');
CREATE TABLE worker.artifacts (
    tenant_id uuid NOT NULL,
    job_id uuid NOT NULL,
    attempt integer NOT NULL,
    fence bigint NOT NULL,
    object_key text NOT NULL UNIQUE,
    sha256 text NOT NULL CHECK (sha256 ~ '^[a-f0-9]{64}$'),
    byte_size bigint NOT NULL CHECK (byte_size>0),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id,job_id),
    FOREIGN KEY (tenant_id,job_id) REFERENCES worker.jobs(tenant_id,job_id)
);
CREATE TABLE worker.outbox (
    event_id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    job_id uuid NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    published_at timestamptz,
    FOREIGN KEY (tenant_id,job_id) REFERENCES worker.jobs(tenant_id,job_id)
);
CREATE INDEX worker_outbox_pending ON worker.outbox(created_at) WHERE published_at IS NULL;
CREATE VIEW core.worker_job_inputs AS
    SELECT tenant_id,job_id,case_id,kind,attempt,input,input_hash,status FROM core.job_requests;
CREATE VIEW worker.document_results AS
    SELECT j.tenant_id,j.job_id,j.case_id,j.attempt,j.fence,j.status,j.failure_code,
           a.object_key,a.sha256,a.byte_size,a.created_at
    FROM worker.jobs j LEFT JOIN worker.artifacts a USING (tenant_id,job_id)
    WHERE j.kind='DOCUMENT';
GRANT SELECT,INSERT,UPDATE ON core.template_versions,core.job_requests TO caseflow_api;
GRANT SELECT,INSERT ON core.event_inbox TO caseflow_api;
GRANT SELECT ON worker.document_results TO caseflow_api;
GRANT USAGE ON SCHEMA core TO caseflow_worker;
GRANT SELECT ON core.worker_job_inputs TO caseflow_worker;
GRANT SELECT,INSERT ON worker.inbox,worker.artifacts TO caseflow_worker;
GRANT SELECT,INSERT,UPDATE ON worker.jobs,worker.outbox TO caseflow_worker;
