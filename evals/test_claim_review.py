import copy
import json
import pytest
from claim_review import grade_packet, review_packet


def fixture():
    packet=dict(datasetVersion='synthetic',datasetSha256='dataset',predictionsSha256='predictions',
                method='human-claim-review-v1',failedOrMissingReviews=1,
                claims=[dict(key='case/summary',textSha256='text')])
    review=dict(**{k:packet[k] for k in ('datasetVersion','datasetSha256','predictionsSha256','method')},
                reviewer='Synthetic test fixture, not a human grade',reviewedAt='2026-09-15',
                grades={'case/summary':dict(textSha256='text',coverageConfirmed=True,segments=[
                    dict(text='First factual claim',verdict='SUPPORTED',rationale='Synthetic supported judgment'),
                    dict(text='Second factual claim',verdict='UNSUPPORTED',rationale='Synthetic unsupported judgment'),
                    dict(text='A question',verdict='NOT_A_FACT',rationale='No assertion')])})
    return packet,review


def test_compound_claims_count_separately_and_failures_stay_visible():
    packet,review=fixture()
    result=grade_packet(packet,review)
    assert result['claimSupport']==dict(numerator=1,denominator=2,rate=.5)
    assert result['nonFactualSegments']==1 and result['failedOrMissingReviews']==1
    assert result['provisionalClaimTargetMet'] is False and result['releaseGatePassed'] is False
    assert result['method']=='human-claim-review-v1'
    assert result['profile']=='human-reviewed' and result['humanVerified'] is True


def test_ai_provenance_is_preserved_without_changing_claim_denominator():
    packet,review=fixture()
    packet.update(method='ai-claim-review-v1',profile='ai-reviewed-learning',humanVerified=False)
    review.update(method='ai-claim-review-v1',profile='ai-reviewed-learning',humanVerified=False)
    result=grade_packet(packet,review)
    assert result['claimSupport']==dict(numerator=1,denominator=2,rate=.5)
    assert result['unsupportedClaims']==1 and result['nonFactualSegments']==1
    assert result['method']=='ai-claim-review-v1'
    assert result['profile']=='ai-reviewed-learning' and result['humanVerified'] is False


@pytest.mark.parametrize('field,value', [
    ('method','human-claim-review-v1'),
    ('profile','human-reviewed'),
    ('humanVerified',True),
])
def test_ai_review_provenance_must_match_packet(field,value):
    packet,review=fixture()
    packet.update(method='ai-claim-review-v1',profile='ai-reviewed-learning',humanVerified=False)
    review.update(method='ai-claim-review-v1',profile='ai-reviewed-learning',humanVerified=False)
    review[field]=value
    with pytest.raises(ValueError):grade_packet(packet,review)


def test_human_method_rejects_explicit_ai_provenance():
    packet,review=fixture()
    packet.update(profile='human-reviewed',humanVerified=True)
    review.update(profile='ai-reviewed-learning',humanVerified=False)
    with pytest.raises(ValueError):grade_packet(packet,review)


def test_review_packet_selects_explicit_profile(tmp_path,monkeypatch):
    predictions=[dict(id='case',review=dict(result=dict(evidence={})),manualPurchase={})]
    (tmp_path/'predictions.jsonl').write_text('\n'.join(map(json.dumps,predictions)),encoding='utf-8')
    monkeypatch.setattr('claim_review.score_run',lambda _:dict(
        datasetVersion='synthetic',datasetSha256='dataset',predictionsSha256='predictions',
        split='heldout',ungradedClaims=[dict(id='case',location='summary',text='Claim')],
        failedOrMissingReviews=0))
    packet=review_packet(tmp_path,'ai-reviewed-learning')
    assert packet['method']=='ai-claim-review-v1'
    assert packet['profile']=='ai-reviewed-learning' and packet['humanVerified'] is False


def test_review_packet_rejects_unknown_profile(tmp_path):
    with pytest.raises(ValueError):review_packet(tmp_path,'unknown')


@pytest.mark.parametrize('change', ['hash','coverage','missing','ungraded','rationale'])
def test_incomplete_or_mismatched_grades_cannot_be_scored(change):
    packet,review=fixture();review=copy.deepcopy(review)
    if change=='hash':review['predictionsSha256']='another run'
    elif change=='coverage':review['grades']['case/summary']['coverageConfirmed']=False
    elif change=='missing':review['grades']={}
    elif change=='ungraded':review['grades']['case/summary']['segments'][0]['verdict']=None
    else:review['grades']['case/summary']['segments'][0]['rationale']=''
    with pytest.raises(ValueError):grade_packet(packet,review)
