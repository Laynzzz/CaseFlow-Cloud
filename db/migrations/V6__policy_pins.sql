ALTER TABLE core.cases ADD COLUMN policies_initialized boolean NOT NULL DEFAULT false;
CREATE TABLE core.case_policy_pins (
    tenant_id uuid NOT NULL,
    case_id uuid NOT NULL,
    source_id uuid NOT NULL,
    source_version bigint NOT NULL,
    pinned_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id,case_id,source_id),
    FOREIGN KEY (tenant_id,case_id) REFERENCES core.cases(tenant_id,id),
    FOREIGN KEY (tenant_id,source_id) REFERENCES core.sources(tenant_id,id)
);
CREATE FUNCTION core.guard_policy_pin() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE case_state text;
BEGIN
    IF TG_OP='UPDATE' THEN RAISE EXCEPTION 'Replace draft pins explicitly' USING ERRCODE='23514'; END IF;
    SELECT state INTO case_state FROM core.cases
        WHERE tenant_id=COALESCE(NEW.tenant_id,OLD.tenant_id) AND id=COALESCE(NEW.case_id,OLD.case_id) FOR UPDATE;
    IF case_state<>'DRAFT' THEN RAISE EXCEPTION 'Started policy pins are immutable' USING ERRCODE='23514'; END IF;
    IF TG_OP='INSERT' AND NOT EXISTS(SELECT 1 FROM core.sources WHERE tenant_id=NEW.tenant_id
        AND id=NEW.source_id AND kind='POLICY' AND state='PUBLISHED' AND version=NEW.source_version) THEN
        RAISE EXCEPTION 'Only published policy versions can be pinned' USING ERRCODE='23514';
    END IF;
    IF TG_OP='DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER valid_policy_pin BEFORE INSERT OR UPDATE OR DELETE ON core.case_policy_pins
    FOR EACH ROW EXECUTE FUNCTION core.guard_policy_pin();
GRANT SELECT,INSERT,DELETE ON core.case_policy_pins TO caseflow_api;
