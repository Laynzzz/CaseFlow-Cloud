CREATE TABLE core.sources (
    tenant_id uuid NOT NULL REFERENCES core.tenants(id),
    id uuid NOT NULL,
    case_id uuid,
    kind text NOT NULL CHECK (kind IN ('QUOTE','POLICY')),
    name text NOT NULL CHECK (length(name) BETWEEN 1 AND 120),
    media_type text NOT NULL CHECK (media_type IN ('text/plain','application/pdf')),
    state text NOT NULL DEFAULT 'UPLOADING' CHECK (state IN ('UPLOADING','INDEXING','INDEXED','FAILED','PUBLISHED','DEACTIVATED')),
    upload_key text NOT NULL UNIQUE,
    object_key text UNIQUE,
    sha256 text,
    byte_size integer NOT NULL CHECK (byte_size BETWEEN 1 AND 10485760),
    version bigint NOT NULL DEFAULT 0,
    ingestion_job_id uuid,
    failure_code text,
    created_by uuid NOT NULL REFERENCES core.identities(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id,id),
    FOREIGN KEY (tenant_id,case_id) REFERENCES core.cases(tenant_id,id),
    CHECK ((kind='QUOTE')=(case_id IS NOT NULL)),
    CHECK (state='UPLOADING' OR (object_key IS NOT NULL AND sha256 ~ '^[a-f0-9]{64}$' AND ingestion_job_id IS NOT NULL)),
    CHECK (kind='POLICY' OR state NOT IN ('PUBLISHED','DEACTIVATED'))
);
CREATE INDEX sources_by_owner ON core.sources(tenant_id,case_id,created_at DESC,id DESC);
ALTER TABLE core.job_requests ALTER COLUMN case_id DROP NOT NULL;
ALTER TABLE core.job_requests ADD COLUMN source_id uuid;
ALTER TABLE core.job_requests ADD FOREIGN KEY (tenant_id,source_id) REFERENCES core.sources(tenant_id,id);
ALTER TABLE core.job_requests ADD CHECK ((kind='INGESTION' AND source_id IS NOT NULL) OR (kind<>'INGESTION' AND case_id IS NOT NULL));
ALTER TABLE core.sources ADD FOREIGN KEY (tenant_id,ingestion_job_id) REFERENCES core.job_requests(tenant_id,job_id);
ALTER TABLE worker.jobs ALTER COLUMN case_id DROP NOT NULL;
ALTER TABLE worker.jobs ADD COLUMN source_id uuid;
ALTER TABLE worker.jobs ADD FOREIGN KEY (tenant_id,source_id) REFERENCES core.sources(tenant_id,id);
ALTER TABLE core.outbox ALTER COLUMN case_id DROP NOT NULL;
CREATE OR REPLACE FUNCTION core.guard_job_input() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.input IS DISTINCT FROM OLD.input OR NEW.input_hash<>OLD.input_hash
       OR NEW.case_id IS DISTINCT FROM OLD.case_id OR NEW.source_id IS DISTINCT FROM OLD.source_id
       OR NEW.kind<>OLD.kind OR NEW.requested_by<>OLD.requested_by THEN
        RAISE EXCEPTION 'Job input is immutable' USING ERRCODE='23514';
    END IF;
    IF OLD.status='SUCCEEDED' AND NEW IS DISTINCT FROM OLD THEN
        RAISE EXCEPTION 'Successful job is terminal' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END $$;
CREATE FUNCTION core.guard_source() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Sources are retained' USING ERRCODE='23514'; END IF;
    IF NEW.tenant_id<>OLD.tenant_id OR NEW.id<>OLD.id OR NEW.kind<>OLD.kind
       OR NEW.case_id IS DISTINCT FROM OLD.case_id OR NEW.created_by<>OLD.created_by THEN
        RAISE EXCEPTION 'Source ownership is immutable' USING ERRCODE='23514';
    END IF;
    IF OLD.state<>'UPLOADING' AND (NEW.object_key IS DISTINCT FROM OLD.object_key
        OR NEW.sha256 IS DISTINCT FROM OLD.sha256 OR NEW.byte_size<>OLD.byte_size
        OR NEW.media_type<>OLD.media_type OR NEW.name<>OLD.name
        OR NEW.ingestion_job_id IS DISTINCT FROM OLD.ingestion_job_id) THEN
        RAISE EXCEPTION 'Finalized source is immutable' USING ERRCODE='23514';
    END IF;
    IF NEW.state<>OLD.state AND NOT ((OLD.state='UPLOADING' AND NEW.state='INDEXING')
        OR (OLD.state='INDEXING' AND NEW.state IN ('INDEXED','FAILED'))
        OR (OLD.state='INDEXED' AND NEW.state='PUBLISHED')
        OR (OLD.state='PUBLISHED' AND NEW.state='DEACTIVATED')) THEN
        RAISE EXCEPTION 'Invalid source transition' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER source_immutable BEFORE UPDATE OR DELETE ON core.sources FOR EACH ROW EXECUTE FUNCTION core.guard_source();
CREATE FUNCTION core.guard_ingestion_owner() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.kind='INGESTION' AND NOT EXISTS (SELECT 1 FROM core.sources s
        WHERE s.tenant_id=NEW.tenant_id AND s.id=NEW.source_id AND s.case_id IS NOT DISTINCT FROM NEW.case_id) THEN
        RAISE EXCEPTION 'Job source owner mismatch' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER ingestion_owner BEFORE INSERT ON core.job_requests FOR EACH ROW EXECUTE FUNCTION core.guard_ingestion_owner();
CREATE TABLE worker.ingestions (
    tenant_id uuid NOT NULL,
    source_id uuid NOT NULL,
    job_id uuid NOT NULL,
    attempt integer NOT NULL,
    fence bigint NOT NULL,
    source_sha256 text NOT NULL CHECK (source_sha256 ~ '^[a-f0-9]{64}$'),
    parser_version text NOT NULL,
    chunk_version text NOT NULL,
    page_count integer NOT NULL CHECK (page_count BETWEEN 1 AND 50),
    warnings jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id,source_id),
    UNIQUE (tenant_id,job_id),
    FOREIGN KEY (tenant_id,source_id) REFERENCES core.sources(tenant_id,id),
    FOREIGN KEY (tenant_id,job_id) REFERENCES worker.jobs(tenant_id,job_id)
);
CREATE TABLE worker.chunks (
    tenant_id uuid NOT NULL,
    source_id uuid NOT NULL,
    id uuid NOT NULL,
    ordinal integer NOT NULL CHECK (ordinal>=0),
    page integer NOT NULL CHECK (page BETWEEN 1 AND 50),
    section text NOT NULL,
    start_offset integer NOT NULL CHECK (start_offset>=0),
    end_offset integer NOT NULL,
    text text NOT NULL CHECK (length(text) BETWEEN 1 AND 1200),
    sha256 text NOT NULL CHECK (sha256 ~ '^[a-f0-9]{64}$'),
    search tsvector GENERATED ALWAYS AS (to_tsvector('english',text)) STORED,
    PRIMARY KEY (tenant_id,id),
    UNIQUE (tenant_id,source_id,ordinal),
    FOREIGN KEY (tenant_id,source_id) REFERENCES worker.ingestions(tenant_id,source_id),
    CHECK (end_offset-start_offset=length(text))
);
CREATE INDEX chunks_text_search ON worker.chunks USING gin(search);
CREATE VIEW worker.source_results AS SELECT * FROM worker.ingestions;
CREATE VIEW worker.source_chunks AS SELECT * FROM worker.chunks;
CREATE VIEW worker.job_results AS
    SELECT j.tenant_id,j.job_id,j.case_id,j.source_id,j.kind,j.attempt,j.fence,j.status,j.failure_code,
        CASE WHEN j.kind='DOCUMENT' THEN a.object_key IS NOT NULL
             WHEN j.kind='INGESTION' THEN i.source_id IS NOT NULL ELSE false END AS result_exists
    FROM worker.jobs j LEFT JOIN worker.artifacts a USING (tenant_id,job_id)
    LEFT JOIN worker.ingestions i USING (tenant_id,job_id);
CREATE OR REPLACE VIEW core.worker_job_inputs AS
    SELECT tenant_id,job_id,case_id,kind,attempt,input,input_hash,status,source_id FROM core.job_requests;
GRANT SELECT,INSERT,UPDATE ON core.sources TO caseflow_api;
GRANT SELECT ON worker.source_results,worker.source_chunks,worker.job_results TO caseflow_api;
GRANT SELECT,INSERT ON worker.ingestions,worker.chunks TO caseflow_worker;
