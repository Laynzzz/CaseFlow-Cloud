CREATE TABLE worker.embeddings (
    tenant_id uuid NOT NULL,
    chunk_id uuid NOT NULL,
    chunk_sha256 text NOT NULL CHECK (chunk_sha256 ~ '^[a-f0-9]{64}$'),
    model text NOT NULL,
    embedding_version text NOT NULL,
    dimensions integer NOT NULL CHECK (dimensions=256),
    embedding double precision[] NOT NULL CHECK (cardinality(embedding)=256 AND array_ndims(embedding)=1),
    call_id uuid NOT NULL REFERENCES worker.ai_calls(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id,chunk_id,chunk_sha256,model,embedding_version,dimensions),
    FOREIGN KEY (tenant_id,chunk_id) REFERENCES worker.chunks(tenant_id,id)
);
GRANT SELECT,INSERT ON worker.embeddings TO caseflow_worker;
