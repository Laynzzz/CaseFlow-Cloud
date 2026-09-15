"""Opt-in, bounded retrieval comparison over exactly the authorized policy corpus."""
import hashlib
import json
import math
import os
import time
from openai import OpenAI
from . import ai_budget
from .settings import database

MODEL=ai_budget.EMBEDDING_MODEL
VERSION="openai-small-256-v1"
DIMENSIONS=256
MAX_CHUNKS=200


def normalized(values):
    if not isinstance(values,(list,tuple)) or len(values)!=DIMENSIONS or any(type(v) not in (int,float) or not math.isfinite(v) for v in values):
        raise ValueError("INVALID_EMBEDDING")
    norm=math.sqrt(sum(v*v for v in values))
    if not math.isfinite(norm) or norm==0:raise ValueError("INVALID_EMBEDDING")
    return [v/norm for v in values]


def fused(keyword,semantic):
    """Reciprocal rank fusion, k=60; UUID tie-breaks are stable across executions."""
    scores={}
    for ranking in (keyword,semantic):
        for rank,chunk_id in enumerate(ranking,1):scores[chunk_id]=scores.get(chunk_id,0)+1/(60+rank)
    return sorted(scores,key=lambda chunk_id:(-scores[chunk_id],chunk_id))


def compare(job,source,query,baseline,authorize,client=None):
    started=time.monotonic();authorize()
    with database() as db:
        corpus=db.execute("""SELECT id,source_id,ordinal,sha256,text,
            ts_rank_cd(search,websearch_to_tsquery('english',%s)) AS rank,
            search @@ websearch_to_tsquery('english',%s) AS matches
            FROM worker.chunks WHERE tenant_id=%s AND source_id=ANY(%s::uuid[])
            ORDER BY source_id,ordinal LIMIT %s""",(query,query,job['tenant_id'],source['policyIds'],MAX_CHUNKS+1)).fetchall()
        if len(corpus)>MAX_CHUNKS:raise ValueError("AI_RETRIEVAL_LIMIT")
        cached=db.execute("""SELECT chunk_id,chunk_sha256,embedding FROM worker.embeddings
            WHERE tenant_id=%s AND chunk_id=ANY(%s::uuid[]) AND model=%s AND embedding_version=%s AND dimensions=%s""",
            (job['tenant_id'],[row['id'] for row in corpus],MODEL,VERSION,DIMENSIONS)).fetchall()
    metadata=dict(method="exact-cosine-rrf60-v1",model=MODEL,embeddingVersion=VERSION,dimensions=DIMENSIONS,
                  query=query,baselineChunkIds=list(baseline),corpusCount=len(corpus))
    if not corpus:
        return dict(**metadata,semanticChunkIds=[],hybridChunkIds=[],corpus=[],embeddingCallId=None,
                    embeddingCostUsd="0",elapsedMs=int((time.monotonic()-started)*1000),providerCalled=False)
    vectors={(str(row['chunk_id']),row['chunk_sha256']):normalized(row['embedding']) for row in cached}
    missing=[row for row in corpus if (str(row['id']),row['sha256']) not in vectors]
    texts=[query]+[row['text'] for row in missing]
    if any(not text or len(text.encode())>8191 for text in texts) or sum(len(text.encode()) for text in texts)>31744:
        raise ValueError("AI_INPUT_LIMIT")
    if client is None and not os.getenv('OPENAI_API_KEY'):raise ValueError("AI_NOT_CONFIGURED")
    authorize();call_id=ai_budget.reserve(job,"retrieval-embedding",MODEL)
    try:authorize()
    except Exception:
        ai_budget.settle(call_id,0,0,0,"ACCESS_CHANGED_BEFORE_SEND");raise
    owned=client is None;call_started=time.monotonic()
    try:
        if owned:client=OpenAI(api_key=os.environ['OPENAI_API_KEY'],base_url='https://api.openai.com/v1',max_retries=0,timeout=30.0)
        response=client.embeddings.create(model=MODEL,input=texts,dimensions=DIMENSIONS,encoding_format="float")
    except Exception:
        ai_budget.settle(call_id,None,None,int((time.monotonic()-call_started)*1000),"EMBEDDING_PROVIDER_UNAVAILABLE")
        raise ValueError("AI_PROVIDER_UNAVAILABLE") from None
    finally:
        if owned and client is not None:client.close()
    tokens=getattr(getattr(response,'usage',None),'total_tokens',None)
    ai_budget.settle(call_id,tokens,0,int((time.monotonic()-call_started)*1000))
    authorize()
    if type(tokens) is not int or tokens<0 or tokens>32768:raise ValueError("AI_TOKEN_LIMIT")
    if response.model!=MODEL or len(response.data)!=len(texts):raise ValueError("INVALID_EMBEDDING")
    indices=[row.index for row in response.data]
    if sorted(indices)!=list(range(len(texts))):raise ValueError("INVALID_EMBEDDING")
    ordered=sorted(response.data,key=lambda row:row.index)
    embedded=[normalized(row.embedding) for row in ordered]
    query_vector=embedded[0]
    ai_budget.record_response(call_id,dict(model=MODEL,embeddingVersion=VERSION,dimensions=DIMENSIONS,
        inputSha256=hashlib.sha256(json.dumps(texts,ensure_ascii=True).encode()).hexdigest(),
        responseSha256=hashlib.sha256(json.dumps([r.embedding for r in ordered]).encode()).hexdigest(),
        queryVector=query_vector,chunkIds=[str(row['id']) for row in missing]))
    with database() as db:
        if not db.execute("""SELECT 1 FROM worker.jobs WHERE tenant_id=%s AND job_id=%s AND attempt=%s AND fence=%s
            AND lease_owner=%s AND status='RUNNING' AND lease_until>now() FOR SHARE""",
            (job['tenant_id'],job['job_id'],job['attempt'],job['fence'],job['lease_owner'])).fetchone():
            raise ValueError("STALE_AI_EXECUTION")
        if not db.execute("SELECT 1 FROM core.worker_ai_eligible WHERE tenant_id=%s AND job_id=%s",(job['tenant_id'],job['job_id'])).fetchone():
            raise ValueError("AI_INPUT_STALE_OR_ACCESS_REVOKED")
        for row,vector in zip(missing,embedded[1:]):
            db.execute("""INSERT INTO worker.embeddings(tenant_id,chunk_id,chunk_sha256,model,embedding_version,dimensions,embedding,call_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                (job['tenant_id'],row['id'],row['sha256'],MODEL,VERSION,DIMENSIONS,vector,call_id))
            vectors[(str(row['id']),row['sha256'])]=vector
    scored=[dict(chunkId=str(row['id']),sourceId=str(row['source_id']),sha256=row['sha256'],
                 cosine=sum(a*b for a,b in zip(query_vector,vectors[(str(row['id']),row['sha256'])]))) for row in corpus]
    semantic=[row['chunkId'] for row in sorted(scored,key=lambda row:(-row['cosine'],row['chunkId']))]
    keyword=[str(row['id']) for row in sorted((row for row in corpus if row['matches']),key=lambda row:(-row['rank'],str(row['source_id']),row['ordinal']))]
    return dict(**metadata,semanticChunkIds=semantic[:5],hybridChunkIds=fused(keyword,semantic)[:5],corpus=scored,
                embeddingCallId=str(call_id),embeddingCostUsd=str(ai_budget.cost(tokens,0,MODEL)),
                cachedChunks=len(corpus)-len(missing),providerCalled=True,elapsedMs=int((time.monotonic()-started)*1000))
