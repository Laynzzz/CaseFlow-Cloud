import copy
import pytest
from audit_references import audit_case,audit_dataset
from scoring import load_dataset


def test_full_audit_is_not_human_verification():
    report=audit_dataset()
    assert report['summary']['reviewedCases']==120
    assert report['summary']['matchingFieldChecks']==480
    assert report['summary']['issueCounts']=={'AMBIGUOUS_POLICY_WORDING':8}
    assert report['humanVerified'] is False and report['releaseGatePassed'] is False


@pytest.mark.parametrize('field', ['vendor','total','lineItems','currency'])
def test_source_values_are_not_copied_from_reference(field):
    _,splits=load_dataset();case=copy.deepcopy(splits['development'][0])
    case['reference'][field]=None
    result=audit_case(case)
    assert result['fieldChecks'][field] is False
    assert any(i.get('field')==field and i['code']=='REFERENCE_MISMATCH' for i in result['issues'])


def test_changed_policy_is_flagged_for_review():
    _,splits=load_dataset();case=copy.deepcopy(splits['development'][0])
    case['policyPassages'][0]['text']='Equipment purchases do not require a cost center.'
    codes={i['code'] for i in audit_case(case)['issues']}
    assert 'POLICY_REQUIRES_NEW_SEMANTIC_REVIEW' in codes and 'POLICY_REFERENCE_MISMATCH' in codes


def test_v2_changes_only_eight_policy_passages_preserving_reference_answers():
    old_manifest,old=load_dataset()
    new_manifest,new=load_dataset(version='synthetic-v2')
    assert old_manifest['targets']==new_manifest['targets']
    assert old['development']==new['development']
    changed=[]
    for before,after in zip(old['heldout'],new['heldout'],strict=True):
        if before==after:continue
        changed.append(before['id'])
        original=copy.deepcopy(before)
        original['policyPassages'][0]['text']='Laboratory purchase requests must include a cost center before approval.'
        assert original==after
    assert changed==new_manifest['changedCaseIds']
    assert len(changed)==8
    report=audit_dataset('synthetic-v2')
    assert report['status']=='ai-reviewed'
    assert report['summary']['issueCounts']=={}
    assert report['summary']['matchingFieldChecks']==480
    assert report['humanVerified'] is False and report['releaseGatePassed'] is False
