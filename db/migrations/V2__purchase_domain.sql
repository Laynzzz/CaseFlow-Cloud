CREATE TABLE core.identities (
    id uuid PRIMARY KEY,
    issuer text NOT NULL,
    subject text NOT NULL,
    display_name text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (issuer, subject)
);
CREATE TABLE core.tenants (
    id uuid PRIMARY KEY,
    name text NOT NULL CHECK (length(name) BETWEEN 1 AND 120),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE core.memberships (
    tenant_id uuid NOT NULL REFERENCES core.tenants(id),
    user_id uuid NOT NULL REFERENCES core.identities(id),
    roles text[] NOT NULL CHECK (cardinality(roles) > 0 AND roles <@ ARRAY['ADMIN','REQUESTER','APPROVER','AUDITOR']::text[]),
    active boolean NOT NULL DEFAULT true,
    version bigint NOT NULL DEFAULT 0,
    PRIMARY KEY (tenant_id, user_id)
);
CREATE TABLE core.workflow_versions (
    tenant_id uuid NOT NULL REFERENCES core.tenants(id),
    id uuid NOT NULL,
    name text NOT NULL CHECK (length(name) BETWEEN 1 AND 120),
    steps jsonb NOT NULL CHECK (jsonb_typeof(steps) = 'array' AND jsonb_array_length(steps) = 2),
    published boolean NOT NULL DEFAULT false,
    version bigint NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, id)
);
CREATE TABLE core.cases (
    tenant_id uuid NOT NULL REFERENCES core.tenants(id),
    id uuid NOT NULL,
    owner_id uuid NOT NULL,
    state text NOT NULL DEFAULT 'DRAFT' CHECK (state IN ('DRAFT','ACTIVE','APPROVED','REJECTED','CANCELLED')),
    purchase jsonb NOT NULL CHECK (jsonb_typeof(purchase) = 'object'),
    workflow_id uuid,
    workflow_snapshot jsonb,
    original_case_id uuid,
    version bigint NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    approved_at timestamptz,
    document_status text CHECK (document_status IN ('QUEUED','RUNNING','RETRY_WAIT','SUCCEEDED','FAILED')),
    generation_id uuid UNIQUE,
    PRIMARY KEY (tenant_id, id),
    FOREIGN KEY (tenant_id, owner_id) REFERENCES core.memberships(tenant_id, user_id),
    FOREIGN KEY (tenant_id, workflow_id) REFERENCES core.workflow_versions(tenant_id, id),
    FOREIGN KEY (tenant_id, original_case_id) REFERENCES core.cases(tenant_id, id),
    CHECK ((state = 'APPROVED') = (approved_at IS NOT NULL)),
    CHECK (state <> 'APPROVED' OR generation_id IS NOT NULL)
);
CREATE TABLE core.assignments (
    tenant_id uuid NOT NULL,
    case_id uuid NOT NULL,
    step integer NOT NULL CHECK (step BETWEEN 0 AND 1),
    user_id uuid NOT NULL,
    outcome text CHECK (outcome IN ('APPROVED','REJECTED')),
    decided_at timestamptz,
    PRIMARY KEY (tenant_id, case_id, step),
    FOREIGN KEY (tenant_id, case_id) REFERENCES core.cases(tenant_id, id),
    FOREIGN KEY (tenant_id, user_id) REFERENCES core.memberships(tenant_id, user_id),
    CHECK ((outcome IS NULL) = (decided_at IS NULL))
);
CREATE TABLE core.audit (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES core.tenants(id),
    case_id uuid,
    actor_id uuid NOT NULL REFERENCES core.identities(id),
    event_type text NOT NULL,
    details jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (tenant_id, case_id) REFERENCES core.cases(tenant_id, id)
);
CREATE TABLE core.command_records (
    tenant_id uuid NOT NULL REFERENCES core.tenants(id),
    actor_id uuid NOT NULL REFERENCES core.identities(id),
    operation text NOT NULL,
    key text NOT NULL CHECK (length(key) BETWEEN 8 AND 128),
    request_hash text NOT NULL,
    response jsonb NOT NULL,
    expires_at timestamptz NOT NULL DEFAULT now() + interval '7 days',
    PRIMARY KEY (tenant_id, actor_id, operation, key)
);
CREATE TABLE core.outbox (
    event_id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES core.tenants(id),
    case_id uuid NOT NULL,
    event_type text NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    published_at timestamptz,
    FOREIGN KEY (tenant_id, case_id) REFERENCES core.cases(tenant_id, id)
);
CREATE INDEX cases_queue ON core.cases(tenant_id, created_at DESC, id DESC);
CREATE INDEX assignments_inbox ON core.assignments(tenant_id, user_id, case_id) WHERE outcome IS NULL;
CREATE INDEX audit_case ON core.audit(tenant_id, case_id, created_at DESC, id DESC);
CREATE INDEX outbox_pending ON core.outbox(created_at) WHERE published_at IS NULL;

CREATE FUNCTION core.guard_case_snapshot() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.state <> 'DRAFT' AND (NEW.purchase IS DISTINCT FROM OLD.purchase
       OR NEW.workflow_id IS DISTINCT FROM OLD.workflow_id
       OR NEW.workflow_snapshot IS DISTINCT FROM OLD.workflow_snapshot
       OR NEW.owner_id IS DISTINCT FROM OLD.owner_id) THEN
        RAISE EXCEPTION 'Started case inputs are immutable' USING ERRCODE = '23514';
    END IF;
    IF OLD.state IN ('APPROVED','REJECTED','CANCELLED') AND NEW.state <> OLD.state THEN
        RAISE EXCEPTION 'Terminal case state is immutable' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER immutable_case BEFORE UPDATE ON core.cases FOR EACH ROW EXECUTE FUNCTION core.guard_case_snapshot();
CREATE FUNCTION core.guard_workflow() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.published THEN
        RAISE EXCEPTION 'Published workflow is immutable' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER immutable_workflow BEFORE UPDATE OR DELETE ON core.workflow_versions FOR EACH ROW EXECUTE FUNCTION core.guard_workflow();

GRANT SELECT, INSERT, UPDATE ON core.identities, core.tenants, core.memberships, core.workflow_versions, core.cases, core.assignments TO caseflow_api;
GRANT SELECT, INSERT ON core.audit TO caseflow_api;
GRANT SELECT, INSERT, DELETE ON core.command_records TO caseflow_api;
GRANT SELECT, INSERT, UPDATE ON core.outbox TO caseflow_api;
