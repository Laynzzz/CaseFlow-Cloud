"""Summarize recorded local timings and ledger estimates, never provider invoices or load benchmarks."""
import argparse
from collections import Counter,defaultdict
from datetime import datetime
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path


def distribution(values):
    ordered=sorted(values)
    if not ordered:return dict(count=0,p50=None,p95=None)
    return dict(count=len(ordered),p50=ordered[math.ceil(.5*len(ordered))-1],p95=ordered[math.ceil(.95*len(ordered))-1])


def operations(directory):
    run=json.loads((directory/'run.json').read_text(encoding='utf-8'))
    raw=(directory/'predictions.jsonl').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=run.get('predictionsSha256'):raise ValueError('Predictions checksum is absent or changed')
    records=[json.loads(line) for line in raw.decode().splitlines()]
    ledger_bytes=(directory/'calls.json').read_bytes();ledger=json.loads(ledger_bytes)
    requested={record[kind]['jobId'] for record in records for kind in ('extraction','review') if record.get(kind)}
    if set(ledger['jobIds'])!=requested:raise ValueError('Call export does not cover these requested jobs')
    calls=ledger['calls']
    if any(call['job_id'] not in requested for call in calls) or len({call['id'] for call in calls})!=len(calls):
        raise ValueError('Foreign or duplicated call rows')
    known=Decimal(0);held=Decimal(0);groups=defaultdict(list);attempts=defaultdict(set);states=Counter();scenario=[]
    for call in calls:
        states[call['state']]+=1
        if call['actual_usd'] is None:held+=Decimal(call['reserved_usd'])
        else:known+=Decimal(call['actual_usd'])
        if call['elapsed_ms'] is not None:groups[call['purpose']].append(call['elapsed_ms'])
        attempts[call['job_id']].add((call['attempt'],call['fence']))
    for row in records:
        if row.get('startedAt') and row.get('finishedAt'):
            scenario.append(round((datetime.fromisoformat(row['finishedAt'])-datetime.fromisoformat(row['startedAt'])).total_seconds()*1000))
    queue=[];end_to_end=[];timings_hash=None;timing_rows=0;invalid_intervals=[]
    timing_path=directory/'job-timings.json'
    if timing_path.exists():
        timing_bytes=timing_path.read_bytes();timings=json.loads(timing_bytes)
        if set(timings['jobIds'])!=requested or len({r['job_id'] for r in timings['jobs']})!=len(timings['jobs']) or any(r['job_id'] not in requested for r in timings['jobs']):
            raise ValueError('Job timing export does not match the requested jobs')
        timings_hash=hashlib.sha256(timing_bytes).hexdigest();timing_rows=len(timings['jobs'])
        for row in timings['jobs']:
            for field,values in [('first_claim_at',queue),('completed_at',end_to_end)]:
                if row.get(field):
                    elapsed=(datetime.fromisoformat(row[field])-datetime.fromisoformat(row['requested_at'])).total_seconds()*1000
                    if elapsed<0:
                        invalid_intervals.append(dict(jobId=row['job_id'],endpoint=field,elapsedMs=round(elapsed),reason='NEGATIVE_WALL_CLOCK_INTERVAL'))
                    else:values.append(round(elapsed))
    return dict(predictionsSha256=run['predictionsSha256'],callsSha256=hashlib.sha256(ledger_bytes).hexdigest(),
                jobTimingsSha256=timings_hash,exportedTimingRows=timing_rows,
                invalidJobIntervals=invalid_intervals,
                requestedJobCount=len(requested),recordedCallCount=len(calls),states=dict(states),
                jobsWithoutCalls=sorted(requested-set(attempts)),jobsWithMultipleCallAttempts=sum(len(v)>1 for v in attempts.values()),
                knownEstimatedUsd=str(known),unsettledReservedUsd=str(held),accountedUsd=str(known+held),
                providerElapsedMsByPurpose={key:distribution(value) for key,value in sorted(groups.items())},
                callsWithoutElapsed=sum(row['elapsed_ms'] is None for row in calls),scenarioElapsedMs=distribution(scenario),
                queueDelayMs=distribution(queue) if timing_path.exists() else None,
                jobEndToEndMs=distribution(end_to_end) if timing_path.exists() else None,releaseGatePassed=False,
                definitions={'quantile':'Nearest rank, ceil(q*N), without interpolation.',
                             'providerElapsedMs':'Parent-observed admission/transport interval; includes child startup when enabled, not server-only inference.',
                             'scenarioElapsedMs':'Runner-observed setup, sign-in, uploads, indexing and both assistant jobs; not user completion time.',
                             'queueDelayMs':'API request transaction to first RUNNING worker outbox transaction; includes messaging/scheduling. Null if not exported. Invalid intervals excluded and listed.',
                             'jobEndToEndMs':'API request transaction to terminal API job update; includes worker processing and completion delivery. Invalid intervals excluded and listed.',
                             'accountedUsd':'Dated local pricing estimate plus full unknown reservations; not a provider invoice.'},
                limitations=['Sequential local synthetic run, not a controlled load benchmark.',
                             'Host sleep, startup, polling and other concurrent work can affect observations.',
                             'Wall-clock timestamps are not monotonic; negative intervals are preserved as anomalies, never clamped to zero.',
                             'Failed and unknown costs remain accounted; no user time-saving claim.'])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();report=operations(args.directory)
    with args.output.open('x',encoding='utf-8',newline='\n') as output:output.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps({key:report[key] for key in ('recordedCallCount','accountedUsd','providerElapsedMsByPurpose')},indent=2))
