"""Offline scoring of recorded synthetic runs. Never calls a model or fabricates outputs."""
import argparse
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
MISSING = object()
FIELDS = ("vendor", "currency", "total", "lineItems")


def load_dataset(root=ROOT):
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    splits = {}
    ids = set()
    for split in ("development", "heldout"):
        name = split+".jsonl"
        data = (root/name).read_bytes()
        specification = manifest["files"][name]
        if hashlib.sha256(data).hexdigest() != specification["sha256"]:
            raise ValueError(f"Dataset checksum changed: {name}")
        rows = [json.loads(line) for line in data.decode().splitlines() if line.strip()]
        if len(rows) != specification["count"]:
            raise ValueError(f"Dataset count changed: {name}")
        for row in rows:
            if row["id"] in ids:
                raise ValueError("Duplicate dataset ID")
            ids.add(row["id"])
            passages = {p["id"] for p in row["policyPassages"]}
            if not set(row["reference"]["relevantPassages"]).issubset(passages):
                raise ValueError("Reference passage is absent from its case corpus")
        if sorted({r["family"] for r in rows}) != specification["families"]:
            raise ValueError("Dataset family list changed")
        splits[split] = rows
    if {r["family"] for r in splits["development"]} & {r["family"] for r in splits["heldout"]}:
        raise ValueError("Development and held-out families overlap")
    return manifest, splits


def decimal(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", value):
        raise ValueError("Expected a decimal string")
    return Decimal(value)


def normalize(field, value):
    if value is None or value is MISSING:
        return value
    if field in ("vendor", "currency"):
        if not isinstance(value, str):
            raise ValueError("Expected a string")
        return " ".join(value.split()).casefold()
    if field == "total":
        return decimal(value)
    if not isinstance(value, list) or not value:
        raise ValueError("Expected line items")
    # Preserve line order and quantity/price; ignore formatting-only decimal differences.
    return [(" ".join(i["description"].split()).casefold(), decimal(i["quantity"]), decimal(i["unitPrice"])) for i in value]


def outcome(record, kind):
    job = record.get(kind) if record else None
    if not isinstance(job, dict) or job.get("status") != "SUCCEEDED":
        return None
    result = job.get("result")
    return result if isinstance(result, dict) and isinstance(result.get("output"), dict) else None


def rate(numerator, denominator):
    return dict(numerator=numerator, denominator=denominator,
                rate=numerator/denominator if denominator else None)


def score(cases, records, targets):
    by_id = {}
    allowed = {case["id"] for case in cases}
    for record in records:
        if record["id"] not in allowed or record["id"] in by_id:
            raise ValueError("Unknown or duplicate prediction ID")
        by_id[record["id"]] = record
    counts = {field: [0, 0] for field in FIELDS}
    categories = defaultdict(lambda: [0, 0])
    missing_correct = missing_count = 0
    recalled = relevant = 0
    correct_abstentions = unanswerable = false_abstentions = answerable = 0
    correct_answers = failed_extractions = failed_reviews = 0
    claim_rows = []
    known_cost = Decimal(0)
    successful_results_without_cost = 0
    for case in cases:
        record = by_id.get(case["id"], {})
        extraction = outcome(record, "extraction")
        review = outcome(record, "review")
        failed_extractions += extraction is None
        failed_reviews += review is None
        for field in FIELDS:
            suggestion = extraction["output"].get(field) if extraction else None
            proposed = suggestion.get("value", MISSING) if isinstance(suggestion,dict) else MISSING
            reference = case["reference"][field]
            try:
                matches = proposed is not MISSING and normalize(field, proposed) == normalize(field, reference)
            except (ValueError, TypeError, KeyError, AttributeError, InvalidOperation):
                matches = False
            counts[field][0] += matches; counts[field][1] += 1
            categories[case["category"]][0] += matches; categories[case["category"]][1] += 1
            if reference is None:
                missing_count += 1; missing_correct += matches
        expected = set(case["reference"]["relevantPassages"])
        retrieved = record.get("retrievedPassageIds", [])
        if not isinstance(retrieved, list) or not all(isinstance(v, str) for v in retrieved):
            raise ValueError("Retrieved passage IDs must be an ordered string list")
        recalled += len(expected & set(retrieved[:5])); relevant += len(expected)
        if case["reference"]["insufficientEvidence"]:
            unanswerable += 1
            correct_abstentions += bool(review and review["output"].get("insufficient_evidence") is True)
        else:
            answerable += 1
            false_abstentions += bool(review and review["output"].get("insufficient_evidence") is True)
            correct_answers += bool(review and review["output"].get("insufficient_evidence") is False)
        if review:
            # Inventory for manual semantic grading. Existence of citations is not a grade.
            output = review["output"]
            for index, finding in enumerate(output.get("policy_findings", [])):
                claim_rows.append(dict(id=case["id"], location=f"finding:{index}",
                                       text=finding["claim"], citations=finding.get("citations", [])))
            if output.get("summary"):
                claim_rows.append(dict(id=case["id"], location="summary", text=output["summary"], citations=output.get("citations", [])))
        for result in (extraction, review):
            if result:
                try:
                    known_cost += decimal(result["estimatedCostUsd"])
                except (KeyError, ValueError, InvalidOperation):
                    successful_results_without_cost += 1
    extraction_score = rate(sum(v[0] for v in counts.values()), sum(v[1] for v in counts.values()))
    retrieval_score = rate(recalled, relevant)
    return dict(caseCount=len(cases), recordedCaseCount=len(by_id), missingCaseIds=sorted(allowed-by_id.keys()),
                extraction=extraction_score, extractionByField={k:rate(*v) for k,v in counts.items()},
                extractionByCategory={k:rate(*v) for k,v in sorted(categories.items())},
                missingValueAccuracy=rate(missing_correct,missing_count), recallAt5=retrieval_score,
                correctAbstention=rate(correct_abstentions,unanswerable), falseAbstention=rate(false_abstentions,answerable),
                answeredAnswerableCases=rate(correct_answers,answerable), failedOrMissingExtractions=failed_extractions,
                failedOrMissingReviews=failed_reviews, ungradedClaims=claim_rows, claimSupport=None,
                knownSuccessfulResultCostUsd=str(known_cost), successfulResultsWithoutCost=successful_results_without_cost,
                costScope="Successful result metadata only; failed/unknown call ledger reconciliation required",
                targets=targets, releaseGatePassed=False,
                limitations=["Scores describe supplied synthetic run records, not independently verified provider calls.",
                             "Manual annotation verification, semantic claim grading, retrieval comparison and release checks remain required.",
                             "Failed and absent cases stay in accuracy denominators; they are not successful abstentions."])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate-dataset",action="store_true")
    parser.add_argument("--split",choices=["development","heldout"],default="development")
    parser.add_argument("--predictions",type=Path)
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    manifest,splits=load_dataset()
    if args.validate_dataset:
        print(json.dumps(dict(version=manifest["version"],counts={s:len(v) for s,v in splits.items()},
                              annotationStatus=manifest["annotationStatus"],qualityMeasured=False),indent=2))
        return
    if not args.predictions or not args.output:
        parser.error("Scoring requires --predictions and --output; no provider is called")
    if args.output.resolve()==args.predictions.resolve() or args.output.resolve() in {(ROOT/f).resolve() for f in ["manifest.json","development.jsonl","heldout.jsonl"]}:
        parser.error("The report must not replace inputs or the dataset")
    records=[json.loads(line) for line in args.predictions.read_text(encoding="utf-8").splitlines() if line.strip()]
    report=score(splits[args.split],records,manifest["targets"])
    report.update(datasetVersion=manifest["version"],split=args.split,annotationStatus=manifest["annotationStatus"],
                  datasetSha256=manifest["files"][args.split+".jsonl"]["sha256"],
                  predictionsSha256=hashlib.sha256(args.predictions.read_bytes()).hexdigest())
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open("x",encoding="utf-8") as output:
        output.write(json.dumps(report,indent=2)+"\n")
    print(f"Wrote {args.output}. This diagnostic report does not mark R2 complete.")


if __name__ == "__main__":
    main()
