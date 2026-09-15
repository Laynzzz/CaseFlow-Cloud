import hashlib
import json
import pytest
from report_operations import operations


def test_unknown_cost_and_retries_are_kept_and_foreign_calls_rejected(tmp_path):
    raw=b'{"id":"synthetic","review":{"jobId":"job"}}\n'
    (tmp_path/'predictions.jsonl').write_bytes(raw)
    (tmp_path/'run.json').write_text(json.dumps(dict(predictionsSha256=hashlib.sha256(raw).hexdigest())))
    base=dict(job_id='job',purpose='review',attempt=1,reserved_usd='0.02')
    ledger=dict(jobIds=['job'],calls=[dict(base,id='first',fence=1,state='UNKNOWN',actual_usd=None,elapsed_ms=None),
                                    dict(base,id='second',fence=2,state='SETTLED',actual_usd='0.001',elapsed_ms=100)])
    path=tmp_path/'calls.json';path.write_text(json.dumps(ledger))
    report=operations(tmp_path)
    assert report['accountedUsd']=='0.021' and report['unsettledReservedUsd']=='0.02'
    assert report['jobsWithMultipleCallAttempts']==1 and report['callsWithoutElapsed']==1
    assert report['providerElapsedMsByPurpose']['review']==dict(count=1,p50=100,p95=100)
    assert report['queueDelayMs'] is None and report['releaseGatePassed'] is False
    (tmp_path/'job-timings.json').write_text(json.dumps(dict(jobIds=['job'],jobs=[dict(job_id='job',
        requested_at='2026-09-15T12:00:00+00:00',first_claim_at='2026-09-15T12:00:01+00:00',completed_at='2026-09-15T12:00:03+00:00')])))
    report=operations(tmp_path)
    assert report['queueDelayMs']['p95']==1000 and report['jobEndToEndMs']['p95']==3000
    timing_path=tmp_path/'job-timings.json';timings=json.loads(timing_path.read_text())
    timings['jobs'][0]['first_claim_at']='2026-09-15T11:59:59+00:00';timing_path.write_text(json.dumps(timings))
    report=operations(tmp_path)
    assert report['queueDelayMs']['count']==0 and report['queueDelayMs']['p95'] is None
    assert report['invalidJobIntervals'][0]['elapsedMs']==-1000
    ledger['calls'][0]['job_id']='foreign';path.write_text(json.dumps(ledger))
    with pytest.raises(ValueError,match='Foreign'):operations(tmp_path)
