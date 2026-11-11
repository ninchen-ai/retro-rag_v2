"""Review-only conflict analysis of DocLayout-YOLO batch manifests.

Adapted from V1 pdf_layout_conflict_review.py; remains in image pixel space.
No PDF reads, no inference, and no automatic decisions or DB writes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

CLASS_CONFLICTS = {
    frozenset(("figure", "table")): "FIGURE_TABLE_CLASS_CONFLICT",
    frozenset(("title", "table_caption")): "TITLE_CAPTION_CLASS_CONFLICT",
}
CONTENT_CLASSES = {"title", "plain text", "table", "table_caption", "figure_caption"}


def box_area(box: list[float]) -> float:
    return (box[2] - box[0]) * (box[3] - box[1])


def intersection_area(a: list[float], b: list[float]) -> float:
    return (max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
            * max(0.0, min(a[3], b[3]) - max(a[1], b[1])))


def box_iou(a: list[float], b: list[float]) -> float:
    intersection = intersection_area(a, b)
    union = box_area(a) + box_area(b) - intersection
    return intersection / union if union > 0 else 0.0


def _validate_run(run: dict) -> None:
    if run.get("status") != "ok" or run.get("review_status") != "proposed":
        raise ValueError("Nur erfolgreiche, nicht freigegebene YOLO-Läufe erlaubt")
    width, height = run.get("image_width"), run.get("image_height")
    if not isinstance(width, int) or isinstance(width, bool) or width <= 0:
        raise ValueError("Ungültige Bildbreite")
    if not isinstance(height, int) or isinstance(height, bool) or height <= 0:
        raise ValueError("Ungültige Bildhöhe")
    if not isinstance(run.get("detections"), list):
        raise TypeError("Detektionsliste fehlt oder hat falschen Typ")
    for detection in run["detections"]:
        bbox = detection.get("bbox_pixels")
        if (not isinstance(bbox, list) or len(bbox) != 4
                or any(type(value) not in (int, float) or not math.isfinite(value)
                       for value in bbox)):
            raise ValueError("Ungültige Detektor-Bounding-Box")
        x0, y0, x1, y1 = bbox
        if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height):
            raise ValueError("Detektorbox außerhalb der Bildgrenzen")
        confidence = detection.get("confidence")
        if (type(confidence) not in (int, float) or not math.isfinite(confidence)
                or not 0 <= confidence <= 1):
            raise ValueError("Ungültige Detektorkonfidenz")
        if (not isinstance(detection.get("class_name"), str)
                or not detection["class_name"]):
            raise ValueError("Detektorklasse fehlt")
        if detection.get("review_status") != "proposed":
            raise ValueError("Detektion darf nicht bereits freigegeben sein")


def detect_conflicts(detections: list[dict], *, class_iou: float = 0.75,
                     overlap_fraction: float = 0.8) -> list[dict]:
    """Pure detector-geometry hints; preserve all source detections unchanged."""
    if not 0 < class_iou <= 1 or not 0 < overlap_fraction <= 1:
        raise ValueError("Ungültige geometrische Schwellen")
    findings: list[dict] = []
    for i, first in enumerate(detections):
        for j in range(i + 1, len(detections)):
            second = detections[j]
            a, b = first["bbox_pixels"], second["bbox_pixels"]
            classes = frozenset((first["class_name"], second["class_name"]))
            iou = box_iou(a, b)
            code = CLASS_CONFLICTS.get(classes)
            if code and iou >= class_iou:
                findings.append({
                    "code": code,
                    "detector_indices": [i, j],
                    "iou": round(iou, 5),
                    "status": "REVIEW_REQUIRED",
                    "approved": False,
                })
            if "abandon" in classes and classes & CONTENT_CLASSES and iou >= class_iou:
                findings.append({
                    "code": "ABANDON_CONTENT_CONFLICT",
                    "detector_indices": [i, j],
                    "iou": round(iou, 5),
                    "status": "REVIEW_REQUIRED",
                    "approved": False,
                })
            if first["class_name"] == second["class_name"] == "table":
                smaller = min(box_area(a), box_area(b))
                fraction = intersection_area(a, b) / smaller
                if fraction >= overlap_fraction:
                    findings.append({
                        "code": "OVERLAPPING_TABLE_REGIONS",
                        "detector_indices": [i, j],
                        "smaller_region_overlap": round(fraction, 5),
                        "iou": round(iou, 5),
                        "status": "REVIEW_REQUIRED",
                        "approved": False,
                    })
    return findings


def review_manifest(manifest: dict, *, source_sha256: str | None = None) -> dict:
    """Review the exact, completed YOLO manifest, without altering its data."""
    if (manifest.get("mode") != "read_only_pdf_layout_proposals"
            or manifest.get("completed") is not True
            or manifest.get("approved") is not False):
        raise ValueError("Vollständiges, nicht freigegebenes YOLO-Manifest erforderlich")
    runs = manifest.get("runs")
    if not isinstance(runs, list) or not runs:
        raise ValueError("Keine YOLO-Ergebnisse im Manifest")
    results = []
    seen = set()
    for run in runs:
        _validate_run(run)
        if run.get("case_id") in seen or not run.get("case_id"):
            raise ValueError("Fallidentität fehlt oder doppelt")
        seen.add(run["case_id"])
        findings = detect_conflicts(run["detections"])
        results.append({
            "case_id": run["case_id"],
            "source_image": run.get("source_image"),
            "image_sha256": run.get("image_sha256"),
            "image_size_pixels": [run["image_width"], run["image_height"]],
            "detection_count": len(run["detections"]),
            "review_findings": findings,
            "status": "REVIEW_REQUIRED" if findings else "NO_CONFLICT_DETECTED",
        })
    return {
        "schema_version": "v2-pdf-layout-conflicts-0.1",
        "manifest_sha256": source_sha256,
        "model_weights_sha256": manifest.get("weights_sha256"),
        "coordinate_space": "source_image_pixels",
        "approved": False,
        "completed": True,
        "runs": results,
        "limitations": [
            "Keine automatische Klassenwahl, Unterdrückung oder Inhaltsfreigabe.",
            "Überschneidungen sind Review-Hinweise; IoU beweist keine Semantik.",
            "Pixelkoordinaten noch nicht in PDF-Punkte umgerechnet.",
            "Mehrteilige Tabellen und Zellqualität sind hier nicht bewertet.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.resolve() == args.manifest.resolve():
        parser.error("Ausgabe darf Manifest nicht überschreiben")
    if args.out.exists():
        parser.error("Ausgabedatei existiert bereits; kein Überschreiben")
    raw = args.manifest.read_bytes()
    result = review_manifest(json.loads(raw), source_sha256=hashlib.sha256(raw).hexdigest())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    for item in result["runs"]:
        codes = [finding["code"] for finding in item["review_findings"]]
        print(f"{item['case_id']}: {codes or 'keine geometrischen Konflikte'}")
    print(f"Review-Bericht lokal: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
