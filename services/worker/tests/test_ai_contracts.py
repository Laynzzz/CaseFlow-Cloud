import pytest
from pydantic import ValidationError
from caseflow_worker.ai_contracts import Extraction, Review, Citation, validate_extraction, validate_review, validate_citations

CHUNKS = {"quote-1":dict(text="Vendor Synthetic Tools; USD; Equipment: 2 at 2100; Total 4200",start=100,page=2,sourceId="source-1")}


def extraction():
    cite=[dict(chunkId="quote-1",quote=CHUNKS["quote-1"]["text"])]
    return Extraction.model_validate(dict(vendor=dict(value="Synthetic Tools",citations=cite),currency=dict(value="USD",citations=cite),
        total=dict(value="4200",citations=cite),lineItems=dict(value=[dict(description="Equipment",quantity="2",unitPrice="2100")],citations=cite),warnings=[]))


def test_grounded_proposal_preserves_source_offsets():
    result=validate_extraction(extraction(),CHUNKS)
    assert result.vendor.value == "Synthetic Tools"
    resolved=validate_citations([Citation(chunkId="quote-1",quote="USD")],CHUNKS)
    assert resolved[0] == dict(chunkId="quote-1",sourceId="source-1",page=2,start=124,end=127,quote="USD")


def test_missing_values_remain_null():
    result=extraction()
    result.vendor.value=None;result.vendor.citations=[]
    assert validate_extraction(result,CHUNKS).vendor.value is None


def test_schema_rejects_currency_suffix_in_amount_from_live_failure():
    value=extraction().model_dump()
    value["total"]["value"]="4200.00 USD"
    with pytest.raises(ValidationError):Extraction.model_validate(value)


@pytest.mark.parametrize("field,value,code",[("total","4199","INCONSISTENT_TOTAL"),("total","NaN","INVALID_TOTAL"),("currency","ZZZ","AI_CURRENCY_UNSUPPORTED")])
def test_invalid_purchase_values_rejected(field,value,code):
    result=extraction();getattr(result,field).value=value
    with pytest.raises(ValueError,match=code):validate_extraction(result,CHUNKS)


def test_foreign_or_fabricated_citations_rejected():
    for cite in [Citation(chunkId="other-tenant",quote="USD"),Citation(chunkId="quote-1",quote="Purchase approved")]:
        with pytest.raises(ValueError,match="INVALID_CITATION"):validate_citations([cite],CHUNKS)
    result=extraction();result.vendor.citations=[]
    with pytest.raises(ValueError,match="UNSOURCED_EXTRACTION"):validate_extraction(result,CHUNKS)


def test_no_policy_evidence_requires_abstention():
    result=Review(summary="No policy evidence is available.",missing_information=[],policy_findings=[],citations=[],insufficient_evidence=True)
    assert validate_review(result,{})
    result.insufficient_evidence=False
    with pytest.raises(ValueError,match="EXPECTED_ABSTENTION"):validate_review(result,{})
    with pytest.raises(ValidationError):
        Review.model_validate(dict(summary="Approve",missing_information=[],policy_findings=[],citations=[],insufficient_evidence=True,approve=True))
