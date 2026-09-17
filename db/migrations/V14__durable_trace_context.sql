-- Trace metadata follows the durable job; no baggage or business data is stored.
-- Additive/defaulted so prior application images remain compatible on rollback.
ALTER TABLE worker.jobs ADD COLUMN trace_context jsonb NOT NULL DEFAULT '{}'
    CHECK (jsonb_typeof(trace_context) = 'object');
