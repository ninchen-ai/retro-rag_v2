"""Regressionstests der schreibfreien DocLayout-YOLO-Konfliktanalyse."""

import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "experiments" / "pdf_layout_conflicts_v2.py"
SPEC = importlib.util.spec_from_file_location("pdf_layout_conflicts_v2", SCRIPT)
conflicts = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(conflicts)


def detection(kind, box, confidence=0.8):
    return {
        "class_name": kind,
        "bbox_pixels": box,
        "confidence": confidence,
        "review_status": "proposed",
    }


def manifest(*detections):
    return {
        "mode": "read_only_pdf_layout_proposals",
        "completed": True,
        "approved": False,
        "weights_sha256": "a" * 64,
        "runs": [{
            "case_id": "G200-p0522",
            "source_image": "G200-p0522/page.png",
            "image_sha256": "b" * 64,
            "image_width": 1190,
            "image_height": 1539,
            "status": "ok",
            "review_status": "proposed",
            "detections": list(detections),
        }],
    }


def test_identical_table_figure_and_title_caption_conflicts():
    bbox = [100.0, 200.0, 500.0, 800.0]
    header = [300.0, 100.0, 500.0, 150.0]
    raw = manifest(detection("figure", bbox), detection("table", bbox),
                   detection("title", header), detection("table_caption", header))
    original = copy.deepcopy(raw)
    report = conflicts.review_manifest(raw, source_sha256="0" * 64)
    assert raw == original
    findings = report["runs"][0]["review_findings"]
    assert {f["code"] for f in findings} == {
        "FIGURE_TABLE_CLASS_CONFLICT", "TITLE_CAPTION_CLASS_CONFLICT"
    }
    assert all(f["iou"] == 1.0 and f["approved"] is False
               and f["status"] == "REVIEW_REQUIRED" for f in findings)
    assert report["coordinate_space"] == "source_image_pixels"
    assert report["approved"] is False
    assert report["manifest_sha256"] == "0" * 64


def test_abandon_title_collision_never_discards_content():
    rectangle = [10, 30, 200, 60]
    findings = conflicts.detect_conflicts([
        detection("abandon", rectangle), detection("title", rectangle),
    ])
    assert [f["code"] for f in findings] == ["ABANDON_CONTENT_CONFLICT"]


def test_distant_regions_not_a_conflict():
    raw = manifest(detection("table", [5, 10, 55, 100]),
                   detection("figure", [500, 500, 700, 700]))
    report = conflicts.review_manifest(raw)
    assert report["runs"][0]["review_findings"] == []
    assert report["runs"][0]["status"] == "NO_CONFLICT_DETECTED"


def test_nested_table_regions_are_preserved_for_review():
    findings = conflicts.detect_conflicts([
        detection("table", [10, 10, 500, 500]),
        detection("table", [50, 50, 150, 250]),
    ])
    assert [f["code"] for f in findings] == ["OVERLAPPING_TABLE_REGIONS"]
    assert findings[0]["smaller_region_overlap"] == 1.0


@pytest.mark.parametrize("bbox", [
    [-1, 2, 5, 5], [1, 2, 1210, 400], [1, 8, 4, 3],
    [0, 0, float("nan"), 5], [0, 0, True, 50],
])
def test_invalid_boxes_fail_closed(bbox):
    with pytest.raises(ValueError, match="Bounding-Box|Bildgrenzen"):
        conflicts.review_manifest(manifest(detection("table", bbox)))


def test_unfinished_or_approved_manifest_refused():
    for patch in ({"completed": False}, {"approved": True}):
        raw = manifest()
        raw.update(patch)
        with pytest.raises(ValueError, match="Vollständiges"):
            conflicts.review_manifest(raw)


def test_mismatched_run_and_duplicate_case_refused():
    raw = manifest()
    raw["runs"].append(copy.deepcopy(raw["runs"][0]))
    with pytest.raises(ValueError, match="Fallidentität"):
        conflicts.review_manifest(raw)
    raw["runs"] = [{**raw["runs"][0], "status": "error"}]
    with pytest.raises(ValueError, match="Nur erfolgreiche"):
        conflicts.review_manifest(raw)


def test_cli_writes_derived_report_not_input(tmp_path, monkeypatch):
    raw = json.dumps(manifest(detection("figure", [20, 40, 100, 200]),
                              detection("table", [20, 40, 100, 200])))
    source = tmp_path / "manifest.json"
    source.write_text(raw, encoding="utf-8")
    dest = tmp_path / "review.json"
    monkeypatch.setattr(sys, "argv", ["conflicts", "--manifest", str(source),
                                     "--out", str(dest)])
    assert conflicts.main() == 0
    assert source.read_text(encoding="utf-8") == raw
    result = json.loads(dest.read_text(encoding="utf-8"))
    assert result["manifest_sha256"] == hashlib.sha256(raw.encode()).hexdigest()
    assert result["runs"][0]["review_findings"][0]["iou"] == 1.0
    with pytest.raises(SystemExit):
        conflicts.main()
