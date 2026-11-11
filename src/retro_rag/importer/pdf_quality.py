"""Schreibfreie Vollanalyse von PDF-Seiten aus Nextcloud.

Metriken sind Indikatoren, keine OCR-, Leseordnungs- oder Tabellenfreigabe.
Die Auswertung schreibt ausschließlich den lokalen JSON-Bericht.
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import tempfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pymupdf

from retro_rag.importer.webdav import WebDAV

MAX_PDF_BYTES = 50 * 1024 * 1024
DEFAULT_MAX_PAGES = 1000
MIN_TEXT_CHARS = 40


def _intersection_area(a: pymupdf.Rect, b: pymupdf.Rect) -> float:
    intersection = a & b
    return max(0.0, intersection.width) * max(0.0, intersection.height)


def _possible_columns(blocks: list[dict], page_rect: pymupdf.Rect) -> bool:
    """Sucht überlappende Textblöcke in zwei Seitenhälften (nur Verdachtsfall)."""
    center = (page_rect.x0 + page_rect.x1) / 2
    left: list[pymupdf.Rect] = []
    right: list[pymupdf.Rect] = []
    for block in blocks:
        if block.get("type") != 0:
            continue
        spans = [span.get("text", "") for line in block.get("lines", [])
                 for span in line.get("spans", [])]
        if sum(len(s.strip()) for s in spans) < 50:
            continue
        box = pymupdf.Rect(block["bbox"])
        if box.height < 25:
            continue
        if box.x1 <= center - 8:
            left.append(box)
        elif box.x0 >= center + 8:
            right.append(box)
    for a in left:
        for b in right:
            overlap = min(a.y1, b.y1) - max(a.y0, b.y0)
            if overlap > 25 and overlap > 0.2 * min(a.height, b.height):
                return True
    return False


def analyze_page(page: pymupdf.Page, *, detect_tables: bool = True) -> dict[str, Any]:
    """Seitenbezogene Kennzahlen ohne Ausgabe des Inhalts oder OCR-Verarbeitung."""
    text = page.get_text("text", sort=True)
    char_count = len(text.strip())
    words = len(page.get_text("words"))
    layout = page.get_text("dict", sort=True)
    blocks = [block for block in layout.get("blocks", []) if block.get("type") == 0]
    font_weights: Counter[float] = Counter()
    spans: list[tuple[str, float]] = []
    for block in blocks:
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                span_text = span.get("text", "").strip()
                if not span_text:
                    continue
                size = float(span.get("size", 0))
                if size > 0:
                    font_weights[round(size, 1)] += len(span_text)
                    spans.append((span_text, size))
    body_size = font_weights.most_common(1)[0][0] if font_weights else None
    heading_count = (sum(
        len(value) >= 3 and len(value) <= 160
        and size >= max(body_size * 1.2, body_size + 1.2)
        for value, size in spans
    ) if body_size is not None else 0)

    page_rect = page.rect
    page_area = page_rect.width * page_rect.height
    images = page.get_image_info(hashes=False, xrefs=False)
    total_image_area = sum(
        _intersection_area(pymupdf.Rect(info["bbox"]), page_rect)
        for info in images if "bbox" in info
    )
    image_coverage = min(1.0, total_image_area / page_area) if page_area > 0 else 0.0
    ocr_candidate = char_count < MIN_TEXT_CHARS and image_coverage >= 0.5
    suspected_columns = _possible_columns(blocks, page_rect)

    tables_count = None
    table_error = None
    if detect_tables:
        try:
            tables_count = len(page.find_tables().tables)
        except (ValueError, RuntimeError, TypeError, OSError) as exc:
            table_error = f"{type(exc).__name__}: {exc}"

    result: dict[str, Any] = {
        "page": page.number + 1,
        "characters": char_count,
        "words": words,
        "text_blocks": len(blocks),
        "empty_text": char_count == 0,
        "low_text": char_count < MIN_TEXT_CHARS,
        "image_count": len(images),
        "image_coverage_upper_bound": round(image_coverage, 4),
        "ocr_candidate": ocr_candidate,
        "dominant_font_size": body_size,
        "heading_size_candidates": heading_count,
        "possible_multicolumn": suspected_columns,
        "table_candidates": tables_count,
    }
    if table_error:
        result["table_detection_error"] = table_error
    return result


def analyze_pdf(data: bytes, *, detect_tables: bool = True,
                max_pages: int = DEFAULT_MAX_PAGES) -> dict[str, Any]:
    """Untersucht alle PDF-Seiten mit harter Seiten- und Dateigrößegrenze."""
    if max_pages <= 0:
        raise ValueError("Seitenlimit muss positiv sein")
    if not data.startswith(b"%PDF-"):
        raise ValueError("Keine gültige PDF-Signatur")
    if len(data) > MAX_PDF_BYTES:
        raise ValueError("PDF überschreitet 50 MiB")
    result: dict[str, Any] = {"sha256": hashlib.sha256(data).hexdigest()}
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        total = len(doc)
        result["page_count"] = total
        if total > max_pages:
            raise ValueError(f"PDF mit {total} Seiten überschreitet Seitenlimit {max_pages}")
        if doc.needs_pass:
            result["status"] = "encrypted"
            return result
        result["bookmarks"] = len(doc.get_toc())
        pages: list[dict[str, Any]] = []
        for page in doc:
            try:
                pages.append(analyze_page(page, detect_tables=detect_tables))
            except (ValueError, RuntimeError, TypeError, OSError) as exc:
                pages.append({
                    "page": page.number + 1,
                    "analysis_error": f"{type(exc).__name__}: {exc}",
                })
    successful = [page for page in pages if "analysis_error" not in page]
    errors = len(pages) - len(successful)
    result.update({
        "status": "partial" if errors or any("table_detection_error" in p for p in pages)
        else "ok",
        "pages_analyzed": len(successful),
        "pages_failed": errors,
        "empty_pages": sum(p["empty_text"] for p in successful),
        "low_text_pages": sum(p["low_text"] for p in successful),
        "ocr_candidate_pages": sum(p["ocr_candidate"] for p in successful),
        "possible_multicolumn_pages": sum(p["possible_multicolumn"] for p in successful),
        "heading_candidates": sum(p["heading_size_candidates"] for p in successful),
        "table_candidates": sum((p["table_candidates"] or 0) for p in successful),
        "table_detection_errors": sum("table_detection_error" in p for p in successful),
        "pages": pages,
    })
    return result


def _write_report(path: Path, report: dict[str, Any]) -> None:
    """JSON atomar ersetzen, damit Abbruch kein unvollständiges JSON hinterlässt."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=".pdf-quality-",
            suffix=".tmp", delete=False,
        ) as handle:
            temp_path = handle.name
            json.dump(report, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temp_path, path)
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Vollständige, schreibfreie PDF-Qualitätsanalyse")
    parser.add_argument("--url", default=os.getenv("RETRO_V2_NEXTCLOUD_URL"))
    parser.add_argument("--user", default=os.getenv("RETRO_V2_NEXTCLOUD_USER"))
    parser.add_argument("--instance-id", default=os.getenv("RETRO_V2_NEXTCLOUD_INSTANCE_ID"))
    parser.add_argument("--report", type=Path,
                        default=Path("/tmp/retro-v2-pdf-quality.json"))
    parser.add_argument("--max-directories", type=int, default=1000)
    parser.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES)
    parser.add_argument("--max-files", type=int, default=0,
                        help="0 = alle PDFs, positiver Wert = Teilmenge für Probelauf")
    parser.add_argument("--no-tables", action="store_true",
                        help="Langsamere geometrische Tabellenerkennung überspringen")
    args = parser.parse_args()
    if not all((args.url, args.user, args.instance_id)):
        parser.error("WebDAV-URL, Benutzer und stabile Instanzkennung erforderlich")
    if args.max_files < 0 or args.max_pages <= 0 or args.max_directories <= 0:
        parser.error("Ungültige Grenzen für Dateien, Seiten oder Verzeichnisse")
    password = os.getenv("RETRO_V2_NEXTCLOUD_APP_PASSWORD") or getpass.getpass(
        "Nextcloud-App-Passwort: "
    )
    dav = WebDAV(args.url, args.user, password, instance_id=args.instance_id)
    files = [file for file in dav.list_files(max_directories=args.max_directories)
             if file.name.casefold().endswith(".pdf")]
    selected = files[:args.max_files] if args.max_files else files
    report: dict[str, Any] = {
        "created_at": datetime.now(UTC).isoformat(),
        "mode": "read_only_no_db_writes_full_page_quality",
        "completed": False,
        "discovered_pdf_count": len(files),
        "selected_pdf_count": len(selected),
        "tables_enabled": not args.no_tables,
        "results": [],
    }
    _write_report(args.report, report)
    for index, file in enumerate(selected, 1):
        entry = {"source_key": file.source_key, "name": file.name,
                 "size": file.byte_size}
        try:
            if file.byte_size is None:
                raise ValueError("Dateigröße fehlt; begrenzter Download nicht möglich")
            entry.update(analyze_pdf(dav.download(file, max_bytes=MAX_PDF_BYTES),
                                     detect_tables=not args.no_tables,
                                     max_pages=args.max_pages))
        except (ValueError, OSError, RuntimeError, TypeError) as exc:
            entry.update(status="error", error=f"{type(exc).__name__}: {exc}")
        report["results"].append(entry)
        _write_report(args.report, report)
        print(f"[{index}/{len(selected)}] {file.name}: {entry['status']}", flush=True)
    by_hash: dict[str, list[str]] = {}
    for entry in report["results"]:
        if "sha256" in entry:
            by_hash.setdefault(entry["sha256"], []).append(entry["source_key"])
    report["duplicate_sha256_groups"] = [ids for ids in by_hash.values()
                                         if len(ids) > 1]
    report["completed"] = True
    _write_report(args.report, report)
    print(f"Ergebnis: {len(selected)} PDFs; Bericht nur lokal: {args.report}")
    return 0 if all(r["status"] == "ok" for r in report["results"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
