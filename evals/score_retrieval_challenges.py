"""Score supplementary development probes against their predeclared relevant policies."""
import argparse
import hashlib
import json
from pathlib import Path
from retrieval_scoring import compare_scores


def score_challenges(directory):
    dataset_bytes=Path(__file__).with_name('retrieval-challenges.json').read_bytes()
    dataset=json.loads(dataset_bytes)
    run=json.loads((directory/'run.json').read_text(encoding='utf-8'))
    raw=(directory/'predictions.jsonl').read_bytes()
    digest=hashlib.sha256(raw).hexdigest()
    if run.get('datasetSha256')!=hashlib.sha256(dataset_bytes).hexdigest() or run.get('datasetVersion')!=dataset['version']:
        raise ValueError('Challenge dataset differs from the declared run')
    if digest!=run.get('predictionsSha256'):raise ValueError('Predictions checksum is absent or changed')
    cases=[dict(id=row['id'],reference=dict(relevantPassages=[row['id']+'-policy'])) for row in dataset['cases']]
    selected=[case['id'] for case in cases]
    if run.get('selectedIds')!=selected:raise ValueError('Run must preselect all challenge cases')
    records=[json.loads(line) for line in raw.decode().splitlines()]
    actual=[row['id'] for row in records]
    if len(set(actual))!=len(actual) or not set(actual)<=set(selected):raise ValueError('Duplicate or unknown prediction IDs')
    report=compare_scores(cases,records)
    report.update(datasetVersion=dataset['version'],datasetSha256=run['datasetSha256'],predictionsSha256=digest,
                  annotationStatus=dataset['annotationStatus'],scope=dataset['purpose'])
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    report=score_challenges(args.directory)
    with args.output.open('x',encoding='utf-8',newline='\n') as output:output.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps({key:report[key] for key in ('caseCount','recallAt5','knownEmbeddingCostUsd','missingComparisonIds')},indent=2))
