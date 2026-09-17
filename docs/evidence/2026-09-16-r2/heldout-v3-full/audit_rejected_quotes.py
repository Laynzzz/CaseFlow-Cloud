"""Offline diagnostic of recorded rejection evidence; does not alter scoring."""
import hashlib
import json
from pathlib import Path

folder = Path(__file__).resolve().parent
root = folder.parents[3]
run = json.loads((folder / 'run.json').read_text(encoding='utf-8'))
raw = (folder / 'predictions.jsonl').read_bytes()
assert hashlib.sha256(raw).hexdigest() == run['predictionsSha256']
rows = {row['extraction']['jobId']: row for row in map(json.loads, raw.decode().splitlines())}
source_bytes = (root / 'evals/datasets/synthetic-v3/heldout.jsonl').read_bytes()
assert hashlib.sha256(source_bytes).hexdigest() == run['datasetSha256']
cases = {row['id']: row for row in map(json.loads, source_bytes.decode().splitlines())}
calls = json.loads((folder / 'calls.json').read_text(encoding='utf-8'))['calls']
rejections = []
for call in calls:
    if call['error_code'] != 'INVALID_CITATION':
        continue
    row = rows[call['job_id']]
    quote = cases[row['id']]['quote']
    assert hashlib.sha256(quote.encode()).hexdigest() == row['quote']['sha256']
    evidence = call['response_evidence']
    assert not evidence['truncated']
    assert hashlib.sha256(evidence['rawOutput'].encode()).hexdigest() == evidence['rawOutputSha256']
    output = json.loads(evidence['rawOutput'])
    invalid = [dict(field=field, quote=citation['quote'])
               for field in ('vendor', 'currency', 'total', 'lineItems')
               for citation in output[field]['citations'] if citation['quote'] not in quote]
    assert invalid, 'Recorded rejection needs an observed nonliteral quote'
    rejections.append(dict(id=row['id'], jobId=call['job_id'], sourceSha256=row['quote']['sha256'],
                           rawOutputSha256=evidence['rawOutputSha256'], invalidQuotes=invalid))
report = dict(method='Exact substring comparison against hash-matched original synthetic quote',
              predictionsSha256=run['predictionsSha256'], rejectedJobs=len(rejections), rejections=rejections,
              limitation='This explains nonliteral quotation failures. It does not validate all model values, repair citations, change denominators, or evaluate extraction independently of rejection.')
with (folder / 'rejected-quotes.json').open('x', encoding='utf-8', newline='\n') as handle:
    handle.write(json.dumps(report, indent=2) + '\n')
print(f'Observed nonliteral quotes in all {len(rejections)} rejected extractions; original scores unchanged.')
