import hashlib
import json
from pathlib import Path

import pytest
from score_retrieval_challenges import score_challenges


def test_missing_probes_count_as_misses_and_prediction_answers_are_not_references(tmp_path):
    data=Path(__file__).with_name('retrieval-challenges.json').read_bytes()
    dataset=json.loads(data)
    first=dataset['cases'][0]['id']
    record=dict(id=first,reference=dict(relevantPassages=['invented']),
                retrievalComparisons=dict(fullText=['invented'],semantic=[first+'-policy'],hybrid=[]))
    raw=(json.dumps(record)+'\n').encode()
    (tmp_path/'predictions.jsonl').write_bytes(raw)
    run=dict(datasetVersion=dataset['version'],datasetSha256=hashlib.sha256(data).hexdigest(),
             selectedIds=[c['id'] for c in dataset['cases']],predictionsSha256=hashlib.sha256(raw).hexdigest())
    path=tmp_path/'run.json';path.write_text(json.dumps(run))
    report=score_challenges(tmp_path)
    assert report['recallAt5']['semantic']['numerator']==1
    assert report['recallAt5']['semantic']['denominator']==3
    assert report['recallAt5']['fullText']['numerator']==0
    assert len(report['missingComparisonIds'])==2 and report['releaseGatePassed'] is False
    (tmp_path/'predictions.jsonl').write_bytes(raw*2)
    with pytest.raises(ValueError,match='checksum'):score_challenges(tmp_path)
    run['predictionsSha256']=hashlib.sha256(raw*2).hexdigest();path.write_text(json.dumps(run))
    with pytest.raises(ValueError,match='Duplicate'):score_challenges(tmp_path)
