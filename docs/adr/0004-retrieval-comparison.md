# ADR 0004: bounded retrieval comparison in the existing worker

Date: 2026-09-15. Status: accepted for experimental R2 comparison.

The plan requires comparing PostgreSQL full-text retrieval with an embedding or
hybrid candidate on identical queries. The current application keeps full-text
evidence for its displayed review. An explicit comparison flag on a review job
also records semantic and reciprocal-rank-fusion rankings over the same authorized
corpus and query. It does not silently change the review's evidence.

Use OpenAI `text-embedding-3-small`, 256 dimensions, float encoding, version
`openai-small-256-v1`. Store immutable chunk-hash/model/version/dimension cache
entries in worker-owned PostgreSQL arrays. Compute exact cosine similarity in
Python over at most 200 eligible chunks, failing clearly above that bound. This
keeps the comparison small and reproducible without a separate vector database.
pgvector remains a scaling candidate; no approximate-index performance claim is
made. A measured retrieval benefit is required before changing the product default.

Embedding calls reserve from the existing global lifetime/tenant-day ledger at
USD 0.02 per million input tokens, maximum 32,768 aggregate input tokens, no
output-token charge. Reserve before sending, disable transport retries, retain
unknown costs, and recheck eligibility and the job lease before cache writes.
No cross-tenant cache reuse. Cache keys include text hash and embedding version.

Official specification/pricing checked 2026-09-15:
[model](https://developers.openai.com/api/docs/models/text-embedding-3-small),
[API](https://developers.openai.com/api/reference/python/resources/embeddings/methods/create).
The provider exposes this model identifier without a dated snapshot. Record that
limitation: the cache version must change for an intentional rebuild or model
change; exact numeric reproducibility across provider revisions is not promised.

Trade-offs: comparison adds provider cost and latency; corpus/input bounds limit
coverage; ranking all passages does not establish a relevance threshold or claim
support. The simple one-passage synthetic fixtures cannot demonstrate a semantic
advantage on their own. Report ties and limits honestly.
