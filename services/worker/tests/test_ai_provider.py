from types import SimpleNamespace
from uuid import uuid4
import json
import hashlib
import pytest
from caseflow_worker import ai_provider, ai_budget, jobs
from test_ai_contracts import extraction, CHUNKS
from test_ai_budget import enable


class FakeProvider:
    """CI transport fixture, not a quality or live-provider evaluation."""
    def __init__(self, output, fail=False):self.responses=self;self.output=output;self.fail=fail;self.calls=0;self.arguments=None
    def create(self,**args):
        self.calls+=1
        self.arguments=args
        assert args["store"] is False and "tools" not in args
        assert args["model"]==ai_budget.MODEL
        if self.fail:raise TimeoutError("synthetic timeout")
        return SimpleNamespace(status="completed",output_text=self.output,model=ai_budget.MODEL,
                               usage=SimpleNamespace(input_tokens=1000,output_tokens=100))


@pytest.mark.parametrize('kind,version',[
    ('EXTRACTION','purchase-assistant-2026-09-15-v5'),
    ('REVIEW','purchase-review-2026-09-16-v6'),
])
def test_task_specific_prompt_provenance_matches_actual_request(kind,version,event,isolated_database):
    jobs.schedule(event);job=jobs.claim(uuid4());enable(isolated_database,1)
    facts={'description':'Synthetic equipment','total':'0.00','vendor':''}
    output=extraction().model_dump_json() if kind=='EXTRACTION' else json.dumps(dict(
        summary='The supplied total is 0.00.',missing_information=['vendor'],
        policy_findings=[],citations=[],insufficient_evidence=True))
    client=FakeProvider(output)
    result=ai_provider.request(job,kind,facts,CHUNKS,lambda:None,client)
    sent=client.arguments['input']
    assert result['promptVersion']==version
    assert result['promptHash']==hashlib.sha256((sent[0]['content']+sent[1]['content']).encode()).hexdigest()
    assert json.loads(sent[1]['content'])['purchase']==({} if kind=='EXTRACTION' else facts)
    if kind=='EXTRACTION':assert sent[0]['content']==ai_provider.SYSTEM
    from caseflow_worker.settings import database
    with database() as db:
        stored=db.execute('SELECT response_evidence FROM worker.ai_calls').fetchone()['response_evidence']
    assert stored['promptVersion']==version and stored['promptHash']==result['promptHash']


def test_provider_schema_validation_and_provenance(event,isolated_database):
    jobs.schedule(event);job=jobs.claim(uuid4());enable(isolated_database,1)
    client=FakeProvider(extraction().model_dump_json())
    result=ai_provider.request(job,"EXTRACTION",{"vendor":"Incorrect draft vendor","currency":"EUR"},CHUNKS,lambda:None,client)
    assert result["output"]["vendor"]["value"]=="Synthetic Tools"
    assert len(result["promptHash"])==64 and result["schemaVersion"]=="purchase-assistant-v4"
    assert client.calls==1
    assert json.loads(client.arguments["input"][1]["content"])["purchase"]=={}
    assert client.arguments["text"]["format"]["schema"]["$defs"]["Citation"]["properties"]["chunkId"]["enum"]==list(CHUNKS)


def test_bad_output_is_not_a_displayable_result(event,isolated_database):
    jobs.schedule(event);job=jobs.claim(uuid4());enable(isolated_database,1)
    with pytest.raises(ValueError,match="INVALID_AI_OUTPUT"):
        ai_provider.request(job,"EXTRACTION",{},CHUNKS,lambda:None,FakeProvider('{"approve":true}'))
    from caseflow_worker.settings import database
    with database() as db:
        row=db.execute("SELECT error_code,response_evidence FROM worker.ai_calls").fetchone()
        assert row["error_code"]=="AI_SCHEMA_INVALID"
        assert row["response_evidence"]["rawOutput"]=='{"approve":true}'
        assert db.execute("SELECT count(*) AS n FROM worker.ai_results").fetchone()["n"]==0


def test_empty_policy_evidence_requires_abstention_in_provider_schema(event,isolated_database):
    jobs.schedule(event);job=jobs.claim(uuid4());enable(isolated_database,1)
    client=FakeProvider(json.dumps(dict(summary="No policy evidence",missing_information=[],policy_findings=[],citations=[],insufficient_evidence=True)))
    ai_provider.request(job,"REVIEW",{"description":"Synthetic equipment"},{},lambda:None,client)
    properties=client.arguments["text"]["format"]["schema"]["properties"]
    assert properties["insufficient_evidence"]["enum"]==[True]
    assert properties["citations"]["maxItems"]==0 and properties["policy_findings"]["maxItems"]==0
    assert json.loads(client.arguments["input"][1]["content"])["purchase"]=={"description":"Synthetic equipment"}


def test_false_missing_field_is_rejected_and_recorded(event,isolated_database):
    jobs.schedule(event);job=jobs.claim(uuid4());enable(isolated_database,1)
    client=FakeProvider(json.dumps(dict(summary='Equipment kit.',missing_information=['description'],
        policy_findings=[],citations=[],insufficient_evidence=True)))
    with pytest.raises(ValueError,match='INVALID_AI_OUTPUT'):
        ai_provider.request(job,'REVIEW',dict(description='Equipment kit',total='0.00'),{},lambda:None,client)
    allowed=client.arguments['text']['format']['schema']['properties']['missing_information']['items']['enum']
    assert 'description' not in allowed and 'total' not in allowed and 'costCenter' in allowed
    from caseflow_worker.settings import database
    with database() as db:
        row=db.execute('SELECT error_code,response_evidence FROM worker.ai_calls').fetchone()
    assert row['error_code']=='INVALID_MISSING_INFORMATION'
    assert row['response_evidence']['schemaVersion']=='purchase-review-v5'


def test_complete_purchase_schema_forbids_missing_fields(event,isolated_database):
    jobs.schedule(event);job=jobs.claim(uuid4());enable(isolated_database,1)
    facts=dict(description='Gift',vendor='Synthetic',total='0.00',currency='USD',costCenter='OPS',
               justification='Trial',lineItems=[dict(description='Gift',quantity='1',unitPrice='0.00')])
    client=FakeProvider(json.dumps(dict(summary='No policy evidence.',missing_information=[],
        policy_findings=[],citations=[],insufficient_evidence=True)))
    ai_provider.request(job,'REVIEW',facts,{},lambda:None,client)
    schema=client.arguments['text']['format']['schema']['properties']['missing_information']
    assert schema['maxItems']==0 and 'enum' not in schema['items']


def test_timeout_has_no_hidden_transport_retry(event,isolated_database):
    jobs.schedule(event);job=jobs.claim(uuid4());enable(isolated_database,1)
    client=FakeProvider("",fail=True)
    with pytest.raises(ValueError,match="AI_PROVIDER_UNAVAILABLE"):
        ai_provider.request(job,"EXTRACTION",{},CHUNKS,lambda:None,client)
    assert client.calls==1


def test_parent_deadline_keeps_unknown_charge_reserved(event,isolated_database,monkeypatch):
    from caseflow_worker import provider_transport
    from caseflow_worker.settings import database
    jobs.schedule(event);job=jobs.claim(uuid4());enable(isolated_database,1)
    monkeypatch.setenv('OPENAI_API_KEY','synthetic-not-sent')
    calls=[]
    def deadline(*args,**kwargs):
        calls.append(1)
        raise provider_transport.ProviderBoundaryError('provider_time_limit')
    monkeypatch.setattr(provider_transport,'run_child',deadline)
    with pytest.raises(ValueError,match='AI_PROVIDER_UNAVAILABLE'):
        ai_provider.request(job,'EXTRACTION',{},CHUNKS,lambda:None)
    assert len(calls)==1
    with database() as db:
        row=db.execute('SELECT state,error_code,reserved_usd,actual_usd FROM worker.ai_calls').fetchone()
    assert row['state']=='UNKNOWN' and row['actual_usd'] is None and row['reserved_usd']>0
    assert row['error_code']=='PROVIDER_TIME_LIMIT'


def test_permission_revocation_before_send_prevents_call(event,isolated_database):
    jobs.schedule(event);job=jobs.claim(uuid4());enable(isolated_database,1)
    checks=0
    def authorize():
        nonlocal checks
        checks+=1
        if checks==2:raise ValueError("ACCESS_REVOKED")
    client=FakeProvider(extraction().model_dump_json())
    with pytest.raises(ValueError,match="ACCESS_REVOKED"):
        ai_provider.request(job,"EXTRACTION",{},CHUNKS,authorize,client)
    assert client.calls==0


def test_provider_failure_records_safe_code_not_response_text(event,isolated_database):
    jobs.schedule(event);job=jobs.claim(uuid4());enable(isolated_database,1)
    class RejectedProvider:
        @property
        def responses(self):return self
        def create(self,**args):
            error=RuntimeError("synthetic secret must not be recorded")
            error.status_code=429;error.code="insufficient_quota"
            raise error
    with pytest.raises(ValueError,match="AI_PROVIDER_UNAVAILABLE"):
        ai_provider.request(job,"EXTRACTION",{},CHUNKS,lambda:None,RejectedProvider())
    from caseflow_worker.settings import database
    with database() as db:
        row=db.execute("SELECT error_code,state,actual_usd FROM worker.ai_calls").fetchone()
    assert row["error_code"]=="PROVIDER_INSUFFICIENT_QUOTA"
    assert row["state"]=="UNKNOWN" and row["actual_usd"] is None
