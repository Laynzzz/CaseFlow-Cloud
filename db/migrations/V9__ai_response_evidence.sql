-- Private operational evidence, including rejected model output. Never exposed by API views.
ALTER TABLE worker.ai_calls ADD COLUMN response_evidence jsonb
    CHECK (response_evidence IS NULL OR octet_length(response_evidence::text)<=131072);
