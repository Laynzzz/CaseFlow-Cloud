"""Fresh benchmark inputs must not erase or silently revise historical evidence."""
from collections import Counter
from decimal import Decimal
import pytest

from scoring import ROOT, load_dataset


def historical_bytes(root):
    return {str(path.relative_to(root)): path.read_bytes()
            for directory in (root, root / "datasets" / "synthetic-v2")
            for path in directory.iterdir() if path.suffix in (".jsonl", ".json")}


def copy_inputs(destination):
    destination.mkdir()
    for name, content in historical_bytes(ROOT).items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return destination


def test_construction_is_deterministic_preserves_history_and_refuses_overwrite(tmp_path):
    from build_fresh_dataset import build

    left, right = (copy_inputs(tmp_path / name) for name in ("left", "right"))
    original = historical_bytes(left)
    first, second = build(left), build(right)
    assert historical_bytes(left) == original
    assert {p.name: p.read_bytes() for p in first.iterdir()} == {
        p.name: p.read_bytes() for p in second.iterdir()}
    for path in first.iterdir():
        assert path.read_bytes() == (ROOT / "datasets/synthetic-v3" / path.name).read_bytes()
    expected = (left / "datasets/synthetic-v2/development.jsonl").read_bytes() + (
        left / "datasets/synthetic-v2/heldout.jsonl").read_bytes()
    assert (first / "development.jsonl").read_bytes() == expected
    frozen = {p.name: p.read_bytes() for p in first.iterdir()}
    with pytest.raises(FileExistsError):
        build(left)
    assert {p.name: p.read_bytes() for p in first.iterdir()} == frozen
    manifest, splits = load_dataset(left, "synthetic-v3")
    assert [len(splits[k]) for k in ("development", "heldout")] == [120, 60]
    assert manifest["annotationStatus"] == "awaiting-versioned-review"
    assert manifest["targets"] == {"extraction": .90, "recallAt5": .90, "claimSupport": .95}


def test_corrupt_parent_snapshot_is_rejected_before_creating_new_version(tmp_path):
    from build_fresh_dataset import build

    root = copy_inputs(tmp_path / "corrupt")
    parent = root / "datasets/synthetic-v2/heldout.jsonl"
    parent.write_bytes(parent.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="Dataset checksum changed"):
        build(root)
    assert not (root / "datasets/synthetic-v3").exists()


def test_frozen_v3_has_balanced_new_families_explicit_references_and_exact_retirement():
    manifest, splits = load_dataset(ROOT, "synthetic-v3")
    _, prior = load_dataset(ROOT, "synthetic-v2")
    assert splits["development"] == prior["development"] + prior["heldout"]
    old_families = {r["family"] for r in splits["development"]}
    fresh = splits["heldout"]
    new_families = {r["family"] for r in fresh}
    assert len(new_families) == 6 and not new_families & old_families
    assert len({r["id"] for rows in splits.values() for r in rows}) == 180
    assert len({r["layout"] for r in fresh}) == 6
    assert {r["requiredPurchaseField"] for r in fresh} == {"costCenter", "justification"}
    categories = {"ordinary", "missing_fields", "conflicting_totals", "insufficient_policy", "hostile_instructions"}
    for family in new_families:
        assert Counter(r["category"] for r in fresh if r["family"] == family) == dict.fromkeys(categories, 2)
    for case in fresh:
        ref = case["reference"]
        assert case["purchase"][case["requiredPurchaseField"]] is None
        assert len(ref["lineItems"]) == 1
        line = ref["lineItems"][0]
        calculated = Decimal(line["quantity"]) * Decimal(line["unitPrice"])
        assert f"{calculated:.2f}" in case["quote"]
        if case["category"] == "conflicting_totals":
            assert ref["total"] is None and ref["warnings"] == ["CONFLICTING_TOTALS"]
        else:
            assert Decimal(ref["total"]) == calculated
        if case["category"] == "missing_fields":
            assert ref["vendor"] is None and ref["currency"] is None
        else:
            assert ref["vendor"] in case["quote"] and ref["currency"] in case["quote"]
        assert ref["insufficientEvidence"] == (case["category"] == "insufficient_policy")
        assert ref["relevantPassages"] == ([] if ref["insufficientEvidence"] else [case["family"] + "-p1"])
        if case["category"] == "hostile_instructions":
            assert "ignore" in case["quote"] and "approve" in case["quote"]
    assert manifest["frozenCandidate"]["commit"] == "38fab84"


@pytest.mark.parametrize("version", ["synthetic-v1", "synthetic-v2", "synthetic-v3"])
def test_python_loader_supports_only_named_versions(version):
    manifest, _ = load_dataset(ROOT, version)
    assert manifest["version"] == version
    with pytest.raises(ValueError, match="Unknown frozen dataset"):
        load_dataset(ROOT, "../synthetic-v3")
