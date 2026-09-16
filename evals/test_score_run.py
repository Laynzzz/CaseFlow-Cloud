import hashlib
import json
import pytest
from scoring import load_dataset
from score_run import score_run


@pytest.mark.parametrize('version',['synthetic-v1','synthetic-v2'])
def test_run_subset_keeps_missing_cases_and_refuses_changed_scope(tmp_path,version):
    manifest,splits=load_dataset(version=version)
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


def test_run_preserves_review_provenance_and_refuses_changed_artifact(tmp_path):
    manifest,splits=load_dataset(version='synthetic-v2')
    (tmp_path/'predictions.jsonl').write_bytes(b'')
    review=b'{"method":"ai-reference-review-v1"}\n'
    (tmp_path/'annotation-review.json').write_bytes(review)
    run=dict(split='heldout',selection='first N in frozen file order',selectedIds=[splits['heldout'][0]['id']],
             datasetVersion=manifest['version'],datasetSha256=manifest['files']['heldout.jsonl']['sha256'],
             predictionsSha256=hashlib.sha256(b'').hexdigest(),evaluationProfile='ai-reviewed-learning',
             annotationReview=dict(sha256=hashlib.sha256(review).hexdigest(),humanVerified=False))
    (tmp_path/'run.json').write_text(json.dumps(run))
    report=score_run(tmp_path)
    assert report['evaluationProfile']=='ai-reviewed-learning'
    assert report['annotationReview']['humanVerified'] is False
    (tmp_path/'annotation-review.json').write_bytes(b'{}')
    with pytest.raises(ValueError,match='Annotation review checksum'):score_run(tmp_path)
