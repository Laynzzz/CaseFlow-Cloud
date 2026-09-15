import copy
import pytest
from claim_review import grade_packet


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


@pytest.mark.parametrize('change', ['hash','coverage','missing','ungraded','rationale'])
def test_incomplete_or_mismatched_grades_cannot_be_scored(change):
    packet,review=fixture();review=copy.deepcopy(review)
    if change=='hash':review['predictionsSha256']='another run'
    elif change=='coverage':review['grades']['case/summary']['coverageConfirmed']=False
    elif change=='missing':review['grades']={}
    elif change=='ungraded':review['grades']['case/summary']['segments'][0]['verdict']=None
    else:review['grades']['case/summary']['segments'][0]['rationale']=''
    with pytest.raises(ValueError):grade_packet(packet,review)
