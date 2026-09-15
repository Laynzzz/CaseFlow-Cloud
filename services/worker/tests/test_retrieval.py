from types import SimpleNamespace
from uuid import uuid4
import os
import psycopg
from psycopg.types.json import Jsonb
import pytest
from caseflow_worker import jobs,assistant,retrieval,ai_budget
from caseflow_worker.parsing import parse
from caseflow_worker.settings import database
from test_ingestion import policy_event
from test_ai_budget import enable


class FakeEmbeddings:
    def __init__(self,after=None):self.embeddings=self;self.inputs=[];self.after=after
    def create(self,**args):
        self.inputs.append(args['input'])
        assert args['dimensions']==256 and args['model']==retrieval.MODEL and args['encoding_format']=='float'
        if self.after:self.after()
        return SimpleNamespace(model=retrieval.MODEL,usage=SimpleNamespace(total_tokens=100),
            data=[SimpleNamespace(index=i,embedding=[1.0]+[0.0]*255) for i in range(len(args['input']))])


@pytest.fixture
def corpus(event,isolated_database):
    request,data=policy_event(isolated_database,event)
    jobs.schedule(request);job=jobs.claim(uuid4());assert jobs.finish(job,parse(data,'text/plain'))
    with psycopg.connect(**isolated_database) as db:
        db.execute("UPDATE core.sources SET state='INDEXED' WHERE id=%s",(request.aggregateId,))
        db.execute("UPDATE core.sources SET state='PUBLISHED' WHERE id=%s",(request.aggregateId,))
        db.execute("INSERT INTO core.case_policy_pins(tenant_id,case_id,source_id,source_version) VALUES (%s,%s,%s,1)",
                   (event.tenantId,event.aggregateId,request.aggregateId))
    def make_job():
        job_id=uuid4()
        source=dict(revision=0,policyIds=[str(request.aggregateId)],purchase={'description':'Equipment'},compareRetrieval=True)
        with psycopg.connect(**isolated_database) as db:
            db.execute("""INSERT INTO core.job_requests(tenant_id,job_id,case_id,kind,input,input_hash,requested_by)
                SELECT tenant_id,%s,case_id,'REVIEW',%s,input_hash,requested_by FROM core.job_requests WHERE job_id=%s""",
                (job_id,Jsonb(source),event.jobId))
        jobs.schedule(event.model_copy(update=dict(eventId=uuid4(),jobId=job_id,eventType='review.requested',correlationId=job_id)))
        return jobs.claim(uuid4()),source
    enable(isolated_database,1)
    return make_job


def test_paid_embedding_cache_is_scoped_and_reused(corpus,isolated_database):
    client=FakeEmbeddings();job,source=corpus()
    result=retrieval.compare(job,source,'cost center',[],lambda:assistant.authorized(job),client)
    assert result['corpusCount']==1 and len(result['semanticChunkIds'])==1 and result['cachedChunks']==0
    assert result['embeddingCostUsd']=='0.000002'
    assert jobs.finish(job,{'fixture':True})
    second,source=corpus()
    cached=retrieval.compare(second,source,'cost center',[],lambda:assistant.authorized(second),client)
    assert cached['cachedChunks']==1 and [len(items) for items in client.inputs]==[2,1]
    assert cached['semanticChunkIds']==result['semanticChunkIds']
    with database() as db:
        assert db.execute('SELECT count(*) AS n FROM worker.embeddings').fetchone()['n']==1
        assert db.execute('SELECT model,actual_usd FROM worker.ai_calls LIMIT 1').fetchone()['model']==retrieval.MODEL
    with psycopg.connect(**dict(isolated_database,user='caseflow_api',password=os.environ['DB_API_PASSWORD'])) as db:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):db.execute('SELECT * FROM worker.embeddings')


def test_revoked_access_during_embedding_cannot_write_cache(corpus,isolated_database):
    job,source=corpus()
    def revoke():
        with psycopg.connect(**isolated_database) as db:db.execute('UPDATE core.memberships SET active=false WHERE tenant_id=%s',(job['tenant_id'],))
    with pytest.raises(ValueError,match='ACCESS_REVOKED'):
        retrieval.compare(job,source,'cost center',[],lambda:assistant.authorized(job),FakeEmbeddings(revoke))
    with database() as db:
        assert db.execute('SELECT count(*) AS n FROM worker.embeddings').fetchone()['n']==0
        assert db.execute('SELECT state FROM worker.ai_calls').fetchone()['state']=='SETTLED'


def test_invalid_vectors_and_stable_rank_fusion():
    for values in ([],[float('nan')]*256,[0.0]*256,[True]*256):
        with pytest.raises(ValueError,match='INVALID_EMBEDDING'):retrieval.normalized(values)
    assert retrieval.fused(['b','a'],['a','b'])==['a','b']


def test_embedding_and_generation_share_one_allowance(event,isolated_database):
    jobs.schedule(event);job=jobs.claim(uuid4())
    upper=ai_budget.cost(32768,0,retrieval.MODEL);enable(isolated_database,upper)
    call=ai_budget.reserve(job,'embedding',retrieval.MODEL)
    with pytest.raises(ValueError,match='BUDGET_EXCEEDED'):ai_budget.reserve(job,'generation')
    ai_budget.settle(call,None,None,5,'TIMEOUT')
    with pytest.raises(ValueError,match='BUDGET_EXCEEDED'):ai_budget.reserve(job,'embedding-repeat',retrieval.MODEL)


def test_expired_lease_cannot_write_embedding_cache(corpus,isolated_database):
    job,source=corpus()
    def expire():
        with psycopg.connect(**isolated_database) as db:
            db.execute("UPDATE worker.jobs SET lease_until=now()-interval '1 second' WHERE job_id=%s",(job['job_id'],))
    with pytest.raises(ValueError,match='STALE_AI_EXECUTION'):
        retrieval.compare(job,source,'cost center',[],lambda:assistant.authorized(job),FakeEmbeddings(expire))
    with database() as db:assert db.execute('SELECT count(*) AS n FROM worker.embeddings').fetchone()['n']==0


def test_corpus_bound_rejects_before_any_paid_call(corpus,monkeypatch):
    job,source=corpus();client=FakeEmbeddings();monkeypatch.setattr(retrieval,'MAX_CHUNKS',0)
    with pytest.raises(ValueError,match='AI_RETRIEVAL_LIMIT'):
        retrieval.compare(job,source,'cost center',[],lambda:assistant.authorized(job),client)
    assert client.inputs==[]


def test_empty_corpus_has_no_embedding_charge(event,isolated_database):
    from test_assistant import review_event
    request=review_event(event,isolated_database);jobs.schedule(request);job=jobs.claim(uuid4());client=FakeEmbeddings()
    result=retrieval.compare(job,jobs.input_for(job),'cost center',[],lambda:assistant.authorized(job),client)
    assert not result['providerCalled'] and result['semanticChunkIds']==[] and client.inputs==[]
    with database() as db:assert db.execute('SELECT count(*) AS n FROM worker.ai_calls').fetchone()['n']==0
