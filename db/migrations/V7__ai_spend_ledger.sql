-- Limits begin at zero. An operator must explicitly configure a synthetic-test budget.
CREATE TABLE worker.ai_budget (
    id boolean PRIMARY KEY DEFAULT true CHECK (id),
    total_limit_usd numeric(12,6) NOT NULL DEFAULT 0 CHECK (total_limit_usd>=0),
    tenant_daily_limit_usd numeric(12,6) NOT NULL DEFAULT 0 CHECK (tenant_daily_limit_usd>=0)
);
INSERT INTO worker.ai_budget(id) VALUES (true);
CREATE TABLE worker.ai_calls (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    job_id uuid NOT NULL,
    attempt integer NOT NULL,
    fence bigint NOT NULL,
    purpose text NOT NULL,
    model text NOT NULL,
    pricing_version text NOT NULL,
    reserved_usd numeric(12,6) NOT NULL CHECK (reserved_usd>0),
    actual_usd numeric(12,6) CHECK (actual_usd>=0),
    input_tokens integer CHECK (input_tokens>=0),
    output_tokens integer CHECK (output_tokens>=0),
    state text NOT NULL DEFAULT 'RESERVED' CHECK (state IN ('RESERVED','SETTLED','UNKNOWN')),
    error_code text,
    elapsed_ms bigint CHECK (elapsed_ms>=0),
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (tenant_id,job_id) REFERENCES worker.jobs(tenant_id,job_id),
    UNIQUE (tenant_id,job_id,attempt,fence,purpose),
    CHECK ((state='SETTLED')=(actual_usd IS NOT NULL AND input_tokens IS NOT NULL AND output_tokens IS NOT NULL))
);
CREATE INDEX ai_calls_daily ON worker.ai_calls(tenant_id,created_at);
GRANT SELECT ON worker.ai_budget TO caseflow_worker;
GRANT SELECT,INSERT,UPDATE ON worker.ai_calls TO caseflow_worker;
