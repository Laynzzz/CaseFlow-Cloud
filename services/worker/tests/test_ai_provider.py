from types import SimpleNamespace
from uuid import uuid4
import json
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


def test_timeout_has_no_hidden_transport_retry(event,isolated_database):
    jobs.schedule(event);job=jobs.claim(uuid4());enable(isolated_database,1)
    client=FakeProvider("",fail=True)
    with pytest.raises(ValueError,match="AI_PROVIDER_UNAVAILABLE"):
        ai_provider.request(job,"EXTRACTION",{},CHUNKS,lambda:None,client)
    assert client.calls==1


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
