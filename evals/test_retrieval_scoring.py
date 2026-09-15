from retrieval_scoring import compare_scores


def test_missing_comparison_and_lower_rank_stay_in_recall_denominator():
    cases=[dict(id='a',reference=dict(relevantPassages=['p'])),dict(id='b',reference=dict(relevantPassages=['q']))]
    records=[dict(id='a',retrievalComparisons=dict(fullText=[],semantic=['p'],hybrid=['a','b','c','d','e','p']))]
    result=compare_scores(cases,records)
    assert result['recallAt5']['semantic']==dict(numerator=1,denominator=2,rate=.5)
    assert result['recallAt5']['hybrid']['numerator']==0
    assert result['missingComparisonIds']==['b'] and result['releaseGatePassed'] is False
