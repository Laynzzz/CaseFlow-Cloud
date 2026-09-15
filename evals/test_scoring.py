import copy
import pytest
from scoring import load_dataset, score


def cases():
    return [dict(id="synthetic-1",category="missing_fields",reference=dict(vendor=None,currency="USD",total="10.00",
        lineItems=[dict(description="Test item",quantity="2",unitPrice="5.00")],relevantPassages=["policy-1"],insufficientEvidence=False)),
        dict(id="synthetic-2",category="insufficient_policy",reference=dict(vendor="Synthetic",currency="USD",total="10",
        lineItems=[dict(description="Test item",quantity="2",unitPrice="5")],relevantPassages=[],insufficientEvidence=True))]


def predictions():
    result=[]
    for case in cases():
        output={key:dict(value=case["reference"][key]) for key in ("vendor","currency","total","lineItems")}
        result.append(dict(id=case["id"],extraction=dict(status="SUCCEEDED",result=dict(output=output)),
            review=dict(status="SUCCEEDED",result=dict(output=dict(summary="Synthetic grading fixture",policy_findings=[],
                insufficient_evidence=case["reference"]["insufficientEvidence"]))),retrievedPassageIds=case["reference"]["relevantPassages"]))
    return result


def test_dataset_checksum_counts_and_family_separation():
    manifest,splits=load_dataset()
    assert len(splits["development"])==len(splits["heldout"])==60
    assert manifest["annotationStatus"]=="awaiting-human-review"


def test_missing_or_failed_records_never_receive_null_match_credit():
    report=score(cases(),[],{})
    assert report["extraction"]==dict(numerator=0,denominator=8,rate=0)
    assert report["missingValueAccuracy"]["numerator"]==0
    assert report["correctAbstention"]["numerator"]==0
    records=predictions();records[0]["extraction"]["status"]="FAILED"
    report=score(cases(),records,{})
    assert report["extraction"]["numerator"]==4 and report["failedOrMissingExtractions"]==1


def test_normalized_matches_do_not_imply_claim_support_or_release_completion():
    records=predictions();records[0]["extraction"]["result"]["output"]["total"]["value"]="10"
    report=score(cases(),records,{})
    assert report["extraction"]["rate"]==1 and report["recallAt5"]["rate"]==1
    assert report["claimSupport"] is None and not report["releaseGatePassed"]
    assert len(report["ungradedClaims"])==2 and report["successfulResultsWithoutCost"]==4


def test_retrieval_rank_cutoff_duplicates_and_unknown_predictions():
    records=predictions();records[0]["retrievedPassageIds"]=["noise"]*5+["policy-1"]
    assert score(cases(),records,{})["recallAt5"]["numerator"]==0
    with pytest.raises(ValueError,match="Unknown or duplicate"):score(cases(),records+[copy.deepcopy(records[0])],{})
    records[0]["id"]="foreign-case"
    with pytest.raises(ValueError,match="Unknown or duplicate"):score(cases(),records,{})


def test_absent_value_and_bad_decimal_are_failures_not_null():
    records=predictions();records[0]["extraction"]["result"]["output"]["vendor"]={}
    records[0]["extraction"]["result"]["output"]["total"]["value"]="NaN"
    report=score(cases(),records,{})
    assert report["extraction"]["numerator"]==6 and report["missingValueAccuracy"]["numerator"]==0
