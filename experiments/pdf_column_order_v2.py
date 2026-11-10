"""Review-only two-column reading order from YOLO regions and PyMuPDF lines.

Original text and source line identity are preserved; no DB or PDF writes.
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import math
import os
from pathlib import Path

import pymupdf

from retro_rag.importer.webdav import WebDAV

MAX_BYTES = 50 * 1024 * 1024
MAX_PAGES = 1000


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pixel_box_to_pdf(box: list[float], width: float, height: float,
                     image_width: int, image_height: int) -> list[float]:
    """V1 geometry formula; only for an unrotated, uncropped page."""
    if (len(box) != 4 or min(width, height, image_width, image_height) <= 0
            or any(type(v) not in (float, int) or not math.isfinite(v) for v in box)):
        raise ValueError("Ungültige Geometriedaten")
    x0, y0, x1, y1 = box
    if not (0 <= x0 < x1 <= image_width and 0 <= y0 < y1 <= image_height):
        raise ValueError("Region außerhalb des Bildes")
    return [x0 * width / image_width, y0 * height / image_height,
            x1 * width / image_width, y1 * height / image_height]


def overlap_fraction(a: list[float], b: list[float]) -> float:
    x = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    y = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    area = (a[2] - a[0]) * (a[3] - a[1])
    return x * y / area if area > 0 else 0.0


def columns_from_regions(regions: list[dict], width: float) -> list[dict]:
    """Collect text boxes by the two physical sides, not inference list order."""
    candidates = [r for r in regions
                  if r["class_name"] == "plain text" and r["confidence"] >= 0.5
                  and r["bbox_pdf_points"][3] - r["bbox_pdf_points"][1] >= 35
                  and r["bbox_pdf_points"][2] - r["bbox_pdf_points"][0] >= 40]
    mid = width / 2
    groups = [
        [r for r in candidates if r["bbox_pdf_points"][2] <= mid + 3],
        [r for r in candidates if r["bbox_pdf_points"][0] >= mid - 3],
    ]
    if not all(groups):
        raise ValueError("Zwei getrennte Textspalten nicht sicher erkannt")
    result = []
    for name, group in zip(("left", "right"), groups, strict=True):
        boxes = [r["bbox_pdf_points"] for r in group]
        result.append({
            "name": name,
            "bbox_pdf_points": [min(b[0] for b in boxes), min(b[1] for b in boxes),
                                max(b[2] for b in boxes), max(b[3] for b in boxes)],
            "source_detection_indices": [r["index"] for r in group],
        })
    if result[0]["bbox_pdf_points"][2] >= result[1]["bbox_pdf_points"][0]:
        raise ValueError("Spaltenrahmen überschneiden sich")
    return result


def propose_page(page: pymupdf.Page, image: Path, run: dict, *,
                 pdf_sha256: str, page_number: int) -> dict:
    """Keep every PyMuPDF text line; ambiguous lines remain explicitly unassigned."""
    if page.rotation or page.cropbox != page.mediabox:
        raise ValueError("Rotation oder Cropbox erfordert spezielle Transformation")
    image_data = image.read_bytes()
    if sha256(image_data) != run["image_sha256"]:
        raise ValueError("Bild-SHA-256 stimmt nicht mit YOLO überein")
    pixmap = pymupdf.Pixmap(str(image))
    width, height = pixmap.width, pixmap.height
    if (width, height) != (run["image_width"], run["image_height"]):
        raise ValueError("Bilddimensionen stimmen nicht überein")
    rect = page.rect
    regions = [
        {"index": i, "class_name": d["class_name"], "confidence": d["confidence"],
         "bbox_pdf_points": pixel_box_to_pdf(d["bbox_pixels"], rect.width, rect.height,
                                             width, height)}
        for i, d in enumerate(run["detections"])
    ]
    cols = columns_from_regions(regions, rect.width)
    lines = []
    # PyMuPDF can mix two physical columns into ONE text block: operate on lines.
    for bi, block in enumerate(page.get_text("dict", sort=False)["blocks"]):
        if block.get("type") != 0:
            continue
        for li, line in enumerate(block.get("lines", [])):
            txt = "".join(span.get("text", "") for span in line.get("spans", []))
            if not txt.strip():
                continue
            bbox = [float(v) for v in line["bbox"]]
            scores = [(col["name"], overlap_fraction(bbox, col["bbox_pdf_points"]))
                      for col in cols]
            scores.sort(key=lambda value: value[1], reverse=True)
            best, other = scores
            column = best[0] if best[1] >= 0.65 and other[1] <= 0.15 else None
            lines.append({
                "line_id": f"{bi}:{li}", "source_text": txt, "bbox_pdf_points": bbox,
                "column": column, "status": "proposed" if column else "REVIEW_REQUIRED",
                "coverage": {name: round(value, 4) for name, value in scores},
            })
    def sorted_column(name: str) -> list[dict]:
        return sorted((line for line in lines if line["column"] == name),
                      key=lambda item: (item["bbox_pdf_points"][1],
                                        item["bbox_pdf_points"][0], item["line_id"]))
    ordered = sorted_column("left") + sorted_column("right")
    unassigned = [line for line in lines if line["column"] is None]
    assert len(lines) == len(ordered) + len(unassigned)
    assert {l["line_id"] for l in lines} == {
        l["line_id"] for l in ordered + unassigned
    }
    return {
        "status": "REVIEW_REQUIRED", "approved": False,
        "pdf_sha256": pdf_sha256, "page": page_number,
        "image_sha256": run["image_sha256"],
        "source_extractor": "pymupdf_dict_lines_sort_false",
        "columns": cols, "source_line_count": len(lines),
        "source_lines_sha256": sha256("".join(l["source_text"] for l in lines).encode()),
        "ordered_line_ids": [l["line_id"] for l in ordered],
        "unassigned_line_ids": [l["line_id"] for l in unassigned],
        "proposed_text": "\n".join(l["source_text"] for l in ordered),
        "source_lines": lines,
        "limitations": [
            "All original PyMuPDF lines retained; possible unassigned headers or footers",
            "Reading order and text correctness require manual verification",
            "No automatic approval or suppression of source text",
        ],
    }


def resolve_run(manifest: dict, case_id: str) -> dict:
    if (manifest.get("mode") != "read_only_pdf_layout_proposals"
            or manifest.get("completed") is not True
            or manifest.get("approved") is not False):
        raise ValueError("YOLO-Manifest nicht vollständig oder freigegeben")
    runs = [r for r in manifest.get("runs", []) if r.get("case_id") == case_id]
    if (len(runs) != 1 or runs[0].get("status") != "ok"
            or runs[0].get("review_status") != "proposed"):
        raise ValueError("Kein eindeutiger erfolgreicher YOLO-Fall")
    return runs[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quality-report", type=Path,
                        default=Path("/tmp/retro-v2-pdf-quality.json"))
    parser.add_argument("--goldstandard", type=Path,
                        default=Path("/tmp/retro-v2-pdf-goldstandard"))
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--page", type=int, required=True)
    parser.add_argument("--name", default="usb_20.pdf")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--url", default=os.getenv("RETRO_V2_NEXTCLOUD_URL"))
    parser.add_argument("--user", default=os.getenv("RETRO_V2_NEXTCLOUD_USER"))
    parser.add_argument("--instance-id", default=os.getenv("RETRO_V2_NEXTCLOUD_INSTANCE_ID"))
    args = parser.parse_args()
    if args.out.exists():
        parser.error("Ausgabedatei existiert bereits")
    if not all((args.url, args.user, args.instance_id)):
        parser.error("Nextcloud-Konfiguration fehlt")
    report = json.loads(args.quality_report.read_text(encoding="utf-8"))
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if report.get("completed") is not True:
        parser.error("Qualitätsbericht nicht abgeschlossen")
    matches = [e for e in report["results"] if e.get("name") == args.name
               and e.get("status") == "ok"]
    if len(matches) != 1:
        parser.error("Keine eindeutige Dokumentquelle")
    entry = matches[0]
    if not 1 <= args.page <= entry["page_count"]:
        parser.error("Seite außerhalb PDF")
    digest = entry["sha256"]
    case_id = f"{Path(args.name).stem}-{digest[:12]}-p{args.page:04d}"
    run = resolve_run(manifest, case_id)
    image = args.goldstandard / case_id / "page.png"
    if run.get("source_image") != f"{case_id}/page.png" or not image.is_file():
        parser.error("Originalbild nicht eindeutig zugeordnet")
    password = os.getenv("RETRO_V2_NEXTCLOUD_APP_PASSWORD") or getpass.getpass(
        "Nextcloud-App-Passwort: "
    )
    dav = WebDAV(args.url, args.user, password, instance_id=args.instance_id)
    files = [f for f in dav.list_files() if f.source_key == entry["source_key"]]
    if len(files) != 1 or files[0].byte_size is None or files[0].byte_size > MAX_BYTES:
        parser.error("Nextcloud-Quelldatei fehlt oder überschreitet Limit")
    raw = dav.download(files[0], max_bytes=MAX_BYTES)
    if sha256(raw) != digest:
        parser.error("PDF-Inhalt seit Qualitätsanalyse verändert")
    with pymupdf.open(stream=raw, filetype="pdf") as pdf:
        if pdf.needs_pass or len(pdf) > MAX_PAGES:
            parser.error("PDF geschützt oder zu lang")
        result = propose_page(pdf[args.page - 1], image, run, pdf_sha256=digest,
                              page_number=args.page)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print(f"Seite {args.page}: {len(result['ordered_line_ids'])} Zeilen zugeordnet, "
          f"{len(result['unassigned_line_ids'])} ungeklärt; Review erforderlich")
    print(f"Lokaler Bericht: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
