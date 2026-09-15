"""Score the preselected first-N scope of a completed live-run manifest, never a release gate."""
import argparse
import hashlib
import json
from pathlib import Path
from scoring import load_dataset,score


def score_run(directory):
    manifest,splits=load_dataset()
    run=json.loads((directory/"run.json").read_text(encoding="utf-8"))
    raw=(directory/"predictions.jsonl").read_bytes()
    split=run["split"]
    selected=run["selectedIds"]
    if run["selection"]!="first N in frozen file order" or not selected or selected!=[c["id"] for c in splits[split][:len(selected)]]:
        raise ValueError("Run selection must match the declared first-N frozen order")
    if run["datasetVersion"]!=manifest["version"] or run["datasetSha256"]!=manifest["files"][split+".jsonl"]["sha256"]:
        raise ValueError("Run dataset differs from the frozen manifest")
    digest=hashlib.sha256(raw).hexdigest()
    if digest!=run.get("predictionsSha256"):
        raise ValueError("Run predictions checksum is absent or changed")
    report=score(splits[split][:len(selected)],[json.loads(line) for line in raw.decode().splitlines()],manifest["targets"])
    report.update(scope=f"First {len(selected)} {split} cases selected before calls; not a release report",
                  selectedIds=selected,datasetSha256=run["datasetSha256"],predictionsSha256=digest,
                  annotationStatus=manifest["annotationStatus"],split=split,datasetVersion=manifest["version"])
    return report


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    report=score_run(args.directory)
    with args.output.open("x",encoding="utf-8") as output:output.write(json.dumps(report,indent=2)+"\n")
    print(json.dumps({key:report[key] for key in ("caseCount","extraction","recallAt5","correctAbstention","falseAbstention","failedOrMissingReviews","claimSupport","releaseGatePassed")},indent=2))
