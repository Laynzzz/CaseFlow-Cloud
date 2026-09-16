import copy
import hashlib
import json
import pytest
from compare_repeated_run import compare
from scoring import load_dataset,FIELDS


def fixture(tmp_path):
    manifest,splits=load_dataset()
    rows=[]
    for case in splits['development'][:2]:
        provenance=dict(promptVersion='frozen-test',model='synthetic-model',schemaVersion='test-schema')
        rows.append(dict(id=case['id'],extraction=dict(status='SUCCEEDED',result=dict(**provenance,
            sourceSha256='quote-content-hash',
            output={key:dict(value=case['reference'][key]) for key in FIELDS})),
            review=dict(status='SUCCEEDED',result=dict(**provenance,output=dict(summary='Synthetic test statement',
                policy_findings=[],insufficient_evidence=False))),retrievedPassageIds=case['reference']['relevantPassages'],
            manualPurchase=dict(vendor='',total='0.00'),
            policySources=[dict(passageId='policy-1',source=dict(sha256='policy-content-hash'))]))
    baseline=tmp_path/'baseline';repeat=tmp_path/'repeat'
    plan=tmp_path/'plan.json'
    plan.write_text(json.dumps(dict(datasetVersion=manifest['version'],promptVersion='frozen-test',selectedIds=[rows[0]['id']])))
    def write(path,records):
        path.mkdir(exist_ok=True)
        raw=''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in records).encode('utf-8')
        (path/'predictions.jsonl').write_bytes(raw)
        (path/'run.json').write_text(json.dumps(dict(datasetVersion=manifest['version'],split='development',
            selectedIds=[r['id'] for r in records],selection='first N in frozen file order',
            datasetSha256=manifest['files']['development.jsonl']['sha256'],predictionsSha256=hashlib.sha256(raw).hexdigest())))
    write(baseline,rows);write(repeat,rows[:1])
    return baseline,repeat,plan,copy.deepcopy(rows),write


def test_compares_same_subset_and_normalized_values(tmp_path):
    baseline,repeat,plan,rows,write=fixture(tmp_path)
    row=rows[0]
    row['extraction']['result']['output']['vendor']['value']='Different vendor'
    row['extraction']['result']['output']['total']['value']='175.000'
    row['review']['result']['output']['summary']='Different words'
    write(repeat,[row])
    report=compare(baseline,repeat,plan)
    assert report['changedExtractionFields']==[dict(id=row['id'],field='vendor')]
    assert report['summariesChanged']==1 and report['abstentionsChanged']==0
    assert report['baselineSubsetExtraction']['numerator']==4
    assert report['repeatSubsetExtraction']['numerator']==3
    assert report['releaseGatePassed'] is False
    assert report['comparisons'][0]['inputComparability']=='verified'


@pytest.mark.parametrize('change',['prompt','model','plan','checksum'])
def test_rejects_incomparable_or_tampered_runs(tmp_path,change):
    baseline,repeat,plan,rows,write=fixture(tmp_path)
    if change in ('prompt','model'):
        rows[0]['extraction']['result']['promptVersion' if change=='prompt' else 'model']='different'
        write(repeat,rows[:1])
    elif change=='plan':
        data=json.loads(plan.read_text());data['selectedIds']=[rows[1]['id']];plan.write_text(json.dumps(data))
    else:(repeat/'predictions.jsonl').write_text('{}')
    with pytest.raises(ValueError):compare(baseline,repeat,plan)


def test_failed_repeat_stays_in_denominator(tmp_path):
    baseline,repeat,plan,rows,write=fixture(tmp_path)
    rows[0]['extraction']=dict(status='FAILED')
    rows[0]['review']=dict(status='FAILED')
    write(repeat,rows[:1])
    report=compare(baseline,repeat,plan)
    assert report['repeatSubsetExtraction']['numerator']==0
    assert report['repeatSubsetExtraction']['denominator']==4
    assert report['comparisons'][0]['summaryTextChanged'] is None
    assert report['comparisons'][0]['inputComparability']=='unverified'
    assert report['comparisons'][0]['unverifiedInputs']==['extractionSource']


@pytest.mark.parametrize('change',['source','purchase','policy'])
def test_rejects_changed_inputs_even_with_valid_checksums(tmp_path,change):
    baseline,repeat,plan,rows,write=fixture(tmp_path)
    if change=='source':rows[0]['extraction']['result']['sourceSha256']='changed-quote'
    elif change=='purchase':rows[0]['manualPurchase']['total']='100.00'
    else:rows[0]['policySources'][0]['source']['sha256']='changed-policy'
    write(repeat,rows[:1])
    with pytest.raises(ValueError,match='Supplied inputs changed'):
        compare(baseline,repeat,plan)


def test_reads_non_ascii_predictions_as_utf8(tmp_path):
    baseline,repeat,plan,rows,write=fixture(tmp_path)
    rows[0]['review']['result']['output']['summary']='采购说明 — café'
    write(baseline,rows);write(repeat,rows[:1])
    assert compare(baseline,repeat,plan)['summariesChanged']==0


def test_task_specific_prompt_versions_allow_frozen_repeat_and_reject_drift(tmp_path):
    baseline,repeat,plan,rows,write=fixture(tmp_path)
    declared=json.loads(plan.read_text(encoding='utf-8'))
    declared['extractionPromptVersion']=declared.pop('promptVersion')
    declared['reviewPromptVersion']='review-v2'
    plan.write_text(json.dumps(declared),encoding='utf-8')
    for row in rows:row['review']['result']['promptVersion']='review-v2'
    write(baseline,rows);write(repeat,rows[:1])
    assert compare(baseline,repeat,plan)['summariesChanged']==0
    rows[0]['review']['result']['promptVersion']='review-v3'
    write(repeat,rows[:1])
    with pytest.raises(ValueError,match='Prompt changed'):
        compare(baseline,repeat,plan)
