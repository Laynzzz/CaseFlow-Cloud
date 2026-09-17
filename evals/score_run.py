"""Score the frozen preselected scope of a completed live run, never a release gate."""
import argparse
import hashlib
import json
from pathlib import Path
from scoring import load_dataset,score
from retrieval_scoring import compare_scores


def score_run(directory):
    run=json.loads((directory/"run.json").read_text(encoding="utf-8"))
    manifest,splits=load_dataset(version=run['datasetVersion'])
    if run.get('annotationReview'):
        review_raw=(directory/'annotation-review.json').read_bytes()
        if hashlib.sha256(review_raw).hexdigest()!=run['annotationReview']['sha256']:
            raise ValueError('Annotation review checksum changed')
    raw=(directory/"predictions.jsonl").read_bytes()
    split=run["split"]
    selected=run["selectedIds"]
    if split not in splits or not isinstance(selected,list) or not selected or any(not isinstance(id,str) for id in selected):
        raise ValueError('Run selection must contain nonempty in-split case IDs')
    by_id={case['id']:case for case in splits[split]}
    if len(set(selected))!=len(selected) or any(id not in by_id for id in selected):
        raise ValueError('Run selection contains duplicate or out-of-split case IDs')
    if run['selection']=='first N in frozen file order' and selected!=[c['id'] for c in splits[split][:len(selected)]]:
        raise ValueError("Run selection must match the declared first-N frozen order")
    if run['selection'] not in ('first N in frozen file order','explicit IDs in requested order'):
        raise ValueError('Unknown run selection method')
    cases=[by_id[id] for id in selected]
    if run["datasetVersion"]!=manifest["version"] or run["datasetSha256"]!=manifest["files"][split+".jsonl"]["sha256"]:
        raise ValueError("Run dataset differs from the frozen manifest")
    digest=hashlib.sha256(raw).hexdigest()
    if digest!=run.get("predictionsSha256"):
        raise ValueError("Run predictions checksum is absent or changed")
    records=[json.loads(line) for line in raw.decode().splitlines()]
    report=score(cases,records,manifest["targets"])
    if run.get('compareRetrieval'):report['retrievalComparison']=compare_scores(cases,records)
    report.update(scope=f"{len(selected)} {split} cases selected before calls ({run['selection']}); not a release report",
                  selectedIds=selected,datasetSha256=run["datasetSha256"],predictionsSha256=digest,
                  annotationStatus=manifest["annotationStatus"],split=split,datasetVersion=manifest["version"],
                  evaluationProfile=run.get('evaluationProfile','unreviewed'),
                  annotationReview=run.get('annotationReview'))
    return report


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    report=score_run(args.directory)
    with args.output.open("x",encoding="utf-8",newline="\n") as output:output.write(json.dumps(report,indent=2)+"\n")
    print(json.dumps({key:report[key] for key in ("caseCount","extraction","recallAt5","correctAbstention","falseAbstention","failedOrMissingReviews","claimSupport","releaseGatePassed")},indent=2))
