import hashlib
import json
import pytest
from scoring import load_dataset
from score_run import score_run


def explicit_run(tmp_path, selected=None):
    manifest,splits=load_dataset(version='synthetic-v3')
    cases=[splits['heldout'][15],splits['heldout'][0]]
    prediction=dict(id=cases[0]['id'],extraction=dict(status='SUCCEEDED',result=dict(
        output={field:dict(value=cases[0]['reference'][field]) for field in ('vendor','currency','total','lineItems')})))
    raw=(json.dumps(prediction)+'\n').encode()
    (tmp_path/'predictions.jsonl').write_bytes(raw)
    run=dict(split='heldout',selection='explicit IDs in requested order',
        selectedIds=selected if selected is not None else [case['id'] for case in cases],
        datasetVersion=manifest['version'],datasetSha256=manifest['files']['heldout.jsonl']['sha256'],
        predictionsSha256=hashlib.sha256(raw).hexdigest())
    (tmp_path/'run.json').write_text(json.dumps(run),encoding='utf-8')
    return run,cases


def test_explicit_subset_scores_selected_references_including_missing_cases(tmp_path):
    run,cases=explicit_run(tmp_path)
    result=score_run(tmp_path)
    assert result['selectedIds']==run['selectedIds']
    assert result['caseCount']==2 and result['recordedCaseCount']==1
    assert result['extraction']['numerator']==4 and result['extraction']['denominator']==8
    assert result['missingCaseIds']==[cases[1]['id']]
    assert 'First' not in result['scope']
    assert result['releaseGatePassed'] is False


@pytest.mark.parametrize('selected',[[],['unknown'],['equipment-001'],['calibration-001','calibration-001'],[None],'calibration-001'])
def test_explicit_subset_rejects_invalid_selection(tmp_path,selected):
    explicit_run(tmp_path,selected)
    with pytest.raises(ValueError,match='selection'):score_run(tmp_path)


def test_explicit_subset_rejects_prediction_outside_selection(tmp_path):
    explicit_run(tmp_path,['calibration-001'])
    with pytest.raises(ValueError,match='Unknown or duplicate'):score_run(tmp_path)


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
