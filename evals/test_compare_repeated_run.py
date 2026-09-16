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
            output={key:dict(value=case['reference'][key]) for key in FIELDS})),
            review=dict(status='SUCCEEDED',result=dict(**provenance,output=dict(summary='Synthetic test statement',
                policy_findings=[],insufficient_evidence=False))),retrievedPassageIds=case['reference']['relevantPassages']))
    baseline=tmp_path/'baseline';repeat=tmp_path/'repeat'
    plan=tmp_path/'plan.json'
    plan.write_text(json.dumps(dict(datasetVersion=manifest['version'],promptVersion='frozen-test',selectedIds=[rows[0]['id']])))
    def write(path,records):
        path.mkdir(exist_ok=True)
        raw=''.join(json.dumps(row)+'\n' for row in records).encode()
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
