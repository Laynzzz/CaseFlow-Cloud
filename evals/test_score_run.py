import hashlib
import json
import pytest
from scoring import load_dataset
from score_run import score_run


def test_run_subset_keeps_missing_cases_and_refuses_changed_scope(tmp_path):
    manifest,splits=load_dataset()
    (tmp_path/'predictions.jsonl').write_bytes(b'')
    run=dict(split='development',selection='first N in frozen file order',selectedIds=[c['id'] for c in splits['development'][:2]],
             datasetVersion=manifest['version'],datasetSha256=manifest['files']['development.jsonl']['sha256'],predictionsSha256=hashlib.sha256(b'').hexdigest())
    path=tmp_path/'run.json';path.write_text(json.dumps(run))
    result=score_run(tmp_path)
    assert result['extraction']['denominator']==8 and result['failedOrMissingReviews']==2
    assert result['releaseGatePassed'] is False
    run['selectedIds'].reverse();path.write_text(json.dumps(run))
    with pytest.raises(ValueError,match='selection'):score_run(tmp_path)
    run['selectedIds'].reverse();path.write_text(json.dumps(run))
    (tmp_path/'predictions.jsonl').write_bytes(b'{}')
    with pytest.raises(ValueError,match='checksum'):score_run(tmp_path)
