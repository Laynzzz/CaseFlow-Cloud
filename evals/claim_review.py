"""Create and validate human claim grades bound to an immutable synthetic run."""
import argparse
import hashlib
import json
from pathlib import Path
from score_run import score_run
from scoring import rate


def review_packet(directory):
    report=score_run(directory)
    records={row['id']:row for row in map(json.loads,(directory/'predictions.jsonl').read_text(encoding='utf-8').splitlines())}
    claims=[]
    for row in report['ungradedClaims']:
        result=records[row['id']]['review']['result']
        claims.append(dict(**row,key=row['id']+'/'+row['location'],
                           textSha256=hashlib.sha256(row['text'].encode()).hexdigest(),
                           purchase=records[row['id']].get('manualPurchase'),evidence=result.get('evidence',{})))
    return dict(datasetVersion=report['datasetVersion'],datasetSha256=report['datasetSha256'],
                predictionsSha256=report['predictionsSha256'],split=report['split'],claims=claims,
                failedOrMissingReviews=report['failedOrMissingReviews'],
                method='human-claim-review-v1',releaseGatePassed=False)


def grade_packet(packet,review):
    for key in ('datasetVersion','datasetSha256','predictionsSha256','method'):
        if review.get(key)!=packet[key]:raise ValueError('Claim review does not match this run')
    if not isinstance(review.get('reviewer'),str) or not review['reviewer'].strip() or not review.get('reviewedAt'):
        raise ValueError('Actual reviewer and review date are required')
    grades=review.get('grades',{})
    if not isinstance(grades,dict) or set(grades)!={claim['key'] for claim in packet['claims']}:
        raise ValueError('Review must cover every inventoried output, with no extra keys')
    supported=unsupported=nonfacts=0
    rows=[]
    for claim in packet['claims']:
        grade=grades[claim['key']]
        if grade.get('textSha256')!=claim['textSha256'] or grade.get('coverageConfirmed') is not True:
            raise ValueError('Human must confirm complete coverage of the exact output text')
        segments=grade.get('segments')
        if not isinstance(segments,list) or not segments:raise ValueError('Split and grade each output')
        for segment in segments:
            if not isinstance(segment.get('text'),str) or not segment['text'].strip() or not isinstance(segment.get('rationale'),str) or not segment['rationale'].strip():
                raise ValueError('Each segment needs text and a reason for its grade')
            verdict=segment.get('verdict')
            if verdict=='SUPPORTED':supported+=1
            elif verdict=='UNSUPPORTED':unsupported+=1
            elif verdict=='NOT_A_FACT':nonfacts+=1
            else:raise ValueError('Every segment needs a supported, unsupported or non-factual grade')
        rows.append(dict(key=claim['key'],segments=segments))
    result=rate(supported,supported+unsupported)
    return dict(claimSupport=result,unsupportedClaims=unsupported,nonFactualSegments=nonfacts,
                reviewedOutputs=len(rows),reviewer=review['reviewer'],reviewedAt=review['reviewedAt'],
                datasetSha256=packet['datasetSha256'],predictionsSha256=packet['predictionsSha256'],
                failedOrMissingReviews=packet['failedOrMissingReviews'],grades=rows,
                provisionalClaimTargetMet=result['rate'] is not None and result['rate']>=.95,
                releaseGatePassed=False,
                limitations=['Manual judgments require an actual human reviewer; this code checks completeness, not truth.',
                             'Compound-claim coverage is confirmed by the reviewer, not inferred by the scorer.',
                             'Missing/failed reviews are reported separately and must not disappear from the release decision.',
                             'Reference verification and other R2 gates remain separate.'])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--review',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=grade_packet(review_packet(args.directory),json.loads(args.review.read_text(encoding='utf-8')))
    with args.output.open('x',encoding='utf-8',newline='\n') as output:output.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps({key:result[key] for key in ('claimSupport','unsupportedClaims','reviewedOutputs','releaseGatePassed')},indent=2))
