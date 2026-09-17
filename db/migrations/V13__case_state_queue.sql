-- Equality on tenant/state followed by the stable descending cursor order.
-- Retain cases_queue for lists without a state filter. This additional index
-- consumes storage and adds maintenance on inserts and state transitions.
CREATE INDEX cases_state_queue ON core.cases(tenant_id,state,created_at DESC,id DESC);
