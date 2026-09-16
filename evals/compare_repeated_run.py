"""Compare two completed frozen runs; ignores tenant-specific citation identifiers."""
import argparse
import hashlib
import json
from pathlib import Path
from scoring import FIELDS, load_dataset, normalize, outcome, score
from score_run import score_run


def compare(baseline, repeat, plan_path):
    # Validate each run's selection and hashes before pairing their results.
    reports = [score_run(path) for path in (baseline, repeat)]
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    if reports[0]['datasetSha256'] != reports[1]['datasetSha256'] or any(
        r['datasetVersion'] != plan['datasetVersion'] for r in reports
    ):
        raise ValueError('Runs must use the same frozen split and dataset')
    ids = plan['selectedIds']
    if reports[1]['selectedIds'] != ids or not set(ids).issubset(reports[0]['selectedIds']):
        raise ValueError('Repeat differs from the declared subset')
    records = [{row['id']: row for row in map(json.loads, (path/'predictions.jsonl').read_text().splitlines())}
               for path in (baseline, repeat)]
    manifest,splits=load_dataset(version=plan['datasetVersion'])
    cases=[case for case in splits[reports[0]['split']] if case['id'] in ids]
    subset_scores=[score(cases,[rows[case_id] for case_id in ids if case_id in rows],manifest['targets'])
                   for rows in records]
    changed = []; comparisons = []
    for case_id in ids:
        pair = [rows.get(case_id, {}) for rows in records]
        for kind in ('extraction', 'review'):
            for row in pair:
                result = outcome(row, kind)
                if result and result.get('promptVersion') != plan['promptVersion']:
                    raise ValueError('Prompt changed between repetitions')
            successful = [outcome(row, kind) for row in pair]
            if all(successful) and any(successful[0].get(key) != successful[1].get(key)
                                       for key in ('model', 'schemaVersion', 'retrievalMethod')):
                raise ValueError('Generation configuration changed')
        fields = []
        for field in FIELDS:
            values = []
            for row in pair:
                result = outcome(row, 'extraction')
                suggestion = result['output'].get(field) if result else None
                values.append(normalize(field, suggestion['value']) if isinstance(suggestion, dict) and 'value' in suggestion else ('MISSING',))
            if values[0] != values[1]:fields.append(field)
        reviews = [outcome(row, 'review') for row in pair]
        comparison = dict(id=case_id, changedExtractionFields=fields,
                          extractionStatuses=[row.get('extraction', {}).get('status', 'MISSING') for row in pair],
                          reviewStatuses=[row.get('review', {}).get('status', 'MISSING') for row in pair])
        if all(reviews):
            outputs = [r['output'] for r in reviews]
            comparison.update(summaryTextChanged=outputs[0]['summary'] != outputs[1]['summary'],
                              findingTextsChanged=[f['claim'] for f in outputs[0]['policy_findings']] != [f['claim'] for f in outputs[1]['policy_findings']],
                              abstentionChanged=outputs[0]['insufficient_evidence'] != outputs[1]['insufficient_evidence'])
        else:
            comparison.update(summaryTextChanged=None, findingTextsChanged=None, abstentionChanged=None)
        comparisons.append(comparison)
        changed.extend(dict(id=case_id, field=field) for field in fields)
    return dict(datasetVersion=plan['datasetVersion'], selectedIds=ids,
                baselineSubsetExtraction=subset_scores[0]['extraction'],
                repeatSubsetExtraction=subset_scores[1]['extraction'],
                planSha256=hashlib.sha256(plan_path.read_bytes()).hexdigest(),
                predictionHashes=[report['predictionsSha256'] for report in reports],
                changedExtractionFields=changed, comparisons=comparisons,
                summariesChanged=sum(row['summaryTextChanged'] is True for row in comparisons),
                findingsChanged=sum(row['findingTextsChanged'] is True for row in comparisons),
                abstentionsChanged=sum(row['abstentionChanged'] is True for row in comparisons),
                releaseGatePassed=False,
                limitations=['One repeat of ten cases from one family; not an estimate of all-model variability.',
                             'Text differences are not automatically factual errors; citation IDs differ by tenant and are not compared.',
                             'Both runs share a local worker; timings are not a controlled performance comparison.'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--repeat', type=Path, required=True)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = compare(args.baseline, args.repeat, args.plan)
    with args.output.open('x', encoding='utf-8', newline='\n') as output:
        output.write(json.dumps(report, indent=2)+'\n')
    print(json.dumps({key:report[key] for key in ('changedExtractionFields','summariesChanged','findingsChanged','abstentionsChanged')},indent=2))
