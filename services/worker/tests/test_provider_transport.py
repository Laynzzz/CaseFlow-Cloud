"""Real child-process checks; no network calls or live credentials required."""
import sys
import time

import pytest

from caseflow_worker import provider_transport as transport


def test_deadline_kills_child_before_it_can_write(tmp_path):
    marker=tmp_path/'must-not-exist'
    script=tmp_path/'sleeper.py'
    script.write_text('import sys,time\nfrom pathlib import Path\ntime.sleep(2)\nPath(sys.argv[1]).write_text("alive")\n')
    started=time.monotonic()
    with pytest.raises(transport.ProviderBoundaryError) as failure:
        transport.run_child([sys.executable,str(script),str(marker)],{},timeout=.2)
    assert failure.value.code=='provider_time_limit'
    assert time.monotonic()-started<2
    time.sleep(2)
    assert not marker.exists()


def test_child_cannot_inherit_database_or_object_store_credentials(monkeypatch):
    monkeypatch.setenv('DATABASE_URL','synthetic-private-db')
    monkeypatch.setenv('CASEFLOW_DB_PASSWORD','synthetic-private-password')
    monkeypatch.setenv('AWS_SECRET_ACCESS_KEY','synthetic-private-storage')
    monkeypatch.setenv('OPENAI_API_KEY','synthetic-provider-key')
    script='import os,json; print(json.dumps({"names":list(os.environ),"keyPresent":bool(os.environ.get("OPENAI_API_KEY"))}))'
    result=transport.run_child([sys.executable,'-c',script],{})
    assert result['keyPresent'] is True
    assert not {'DATABASE_URL','CASEFLOW_DB_PASSWORD','AWS_SECRET_ACCESS_KEY'} & set(result['names'])


def test_invalid_child_output_fails_closed(monkeypatch):
    for script in ('print("invalid JSON")','import sys; sys.exit(4)'):
        with pytest.raises(transport.ProviderBoundaryError):
            transport.run_child([sys.executable,'-c',script],{})
    monkeypatch.setattr(transport,'run_child',lambda *a,**k:{'error':'untrusted error text'})
    with pytest.raises(transport.ProviderBoundaryError):transport.BoundedProvider().responses.create()


def test_endpoint_returns_only_structured_result_and_safe_error(monkeypatch):
    monkeypatch.setattr(transport,'run_child',lambda *a,**k:dict(model='synthetic',usage=dict(input_tokens=3)))
    assert transport.BoundedProvider().responses.create().usage.input_tokens==3
    monkeypatch.setattr(transport,'run_child',lambda *a,**k:dict(error=dict(code=None,status=429)))
    with pytest.raises(transport.ProviderBoundaryError) as failure:transport.BoundedProvider().embeddings.create()
    assert transport.safe_error_code(failure.value)=='PROVIDER_HTTP_429'
