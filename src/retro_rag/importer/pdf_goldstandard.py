"""Lokale Goldstandard-Prüfpakete für auffällige PDF-Seiten erstellen.

Alle Bilder, Texte und Bewertungsdateien bleiben ausschließlich lokal auf Poseidon.
Kein OCR, kein Indexing und keine Datenbankschreiboperationen.
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import pymupdf

from retro_rag.importer.webdav import WebDAV

MAX_BYTES = 50 * 1024 * 1024
MAX_PAGES = 1000

# Aus der geprüften Qualitätsbaseline abgeleitete Seiten. KEINE automatisch
# als wahr übernommenen Labels oder Qualitätsbewertungen.
CASES: tuple[tuple[str, int, str], ...] = (
    ("cubx-103.pdf", 111, "ocr"),
    ("cubx-103.pdf", 112, "empty-vs-vector"),
    ("3C905CX.pdf", 1, "ocr"),
    ("directx-demystified-a-comprehensive-guide-to-game-development-essentials.pdf", 2, "ocr"),
    ("507700.pdf", 24, "ocr"),
    ("usb_20.pdf", 601, "reading-order"),
    ("usb_20.pdf", 606, "reading-order"),
    ("AMD K6-2 data sheet_Feb00.pdf", 326, "reading-order"),
    ("MGA-G200_199811.pdf", 522, "long-text"),
    ("ehci-specification-for-usb.pdf", 43, "tables"),
    ("USB_1.0_Specification.pdf", 152, "tables"),
    ("cubx-103.pdf", 21, "tables-and-headings"),
    ("agp20.pdf", 53, "headings"),
    ("agp30.pdf", 40, "headings"),
)


def choose_cases(report: dict[str, Any], limit: int = 0) -> list[dict[str, Any]]:
    """Testfälle an tatsächliche SHA-256-Versionen binden; gleiche PDFs nur einmal."""
    if not report.get("completed") or report.get("mode") != "read_only_no_db_writes_full_page_quality":
        raise ValueError("Vollständig abgeschlossener PDF-Qualitätsbericht erforderlich")
    if limit < 0:
        raise ValueError("limit muss >= 0 sein")
    by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in report.get("results", []):
        if entry.get("status") != "ok" or not entry.get("sha256"):
            continue
        by_name[entry["name"].casefold()].append(entry)
    result: list[dict[str, Any]] = []
    for filename, page_number, focus in CASES:
        options = by_name.get(filename.casefold(), [])
        if not options:
            raise ValueError(f"Testdokument fehlt oder ist fehlerhaft: {filename}")
        hashes = {e["sha256"] for e in options}
        if len(hashes) != 1:
            raise ValueError(f"Mehrdeutige PDF-Version unter demselben Namen: {filename}")
        entry = sorted(options, key=lambda e: e["source_key"])[0]
        if not 1 <= page_number <= entry["page_count"]:
            raise ValueError(f"Testseite außerhalb PDF: {filename}, Seite {page_number}")
        metric = next((p for p in entry.get("pages", [])
                       if p.get("page") == page_number), None)
        if metric is None or "analysis_error" in metric:
            raise ValueError(f"Kein gültiger Seitenmesswert: {filename}, Seite {page_number}")
        result.append({
            "name": entry["name"], "source_key": entry["source_key"],
            "sha256": entry["sha256"], "page": page_number,
            "focus": focus, "metrics": metric,
        })
    return result[:limit] if limit else result


def safe_stem(name: str) -> str:
    """Keine Verzeichnis-Traversierung durch Dateinamen."""
    result = re.sub(r"[^a-zA-Z0-9_-]+", "-", Path(name).stem).strip("-")
    return result[:52] or "pdf"


def evaluation_template(case: dict[str, Any]) -> dict[str, Any]:
    """Bewertungen bleiben NULL, bis visuell von Menschen geprüft."""
    return {
        "case_id": f"{case['sha256'][:12]}-p{case['page']:04d}",
        "pdf_sha256": case["sha256"],
        "pdf_page_1_based": case["page"],
        "focus": case["focus"],
        "review_status": "unreviewed",
        "labels": {
            "page_kind": None,  # text/blank/scan/vector/mixed/other
            "ocr_needed": None,
            "reading_order_correct": None,
            "heading_boundaries_correct": None,
            "table_structure_correct": None,
        },
        "reference": {
            "expected_headings": [],
            "expected_table_cells": [],
            "expected_reading_order": [],
        },
        "notes": "",
    }


def export_page(data: bytes, case: dict[str, Any], folder: Path, dpi: int) -> None:
    """Schreibt PNG, extrahierten Seitentext und unbearbeitete Bewertungsdatei."""
    folder.mkdir(parents=True, exist_ok=False)
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        page = doc[case["page"] - 1]
        pixmap = page.get_pixmap(dpi=dpi, alpha=False)
        pixmap.save(folder / "page.png")
        text = page.get_text("text", sort=True)
        (folder / "extracted.txt").write_text(text, encoding="utf-8")
    (folder / "review.json").write_text(
        json.dumps(evaluation_template(case), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (folder / "metrics.json").write_text(
        json.dumps(case["metrics"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Lokale PDF-Goldstandard-Prüfpakete")
    parser.add_argument("--quality-report", type=Path,
                        default=Path("/tmp/retro-v2-pdf-quality.json"))
    parser.add_argument("--output", type=Path,
                        default=Path("/tmp/retro-v2-pdf-goldstandard"))
    parser.add_argument("--dpi", type=int, default=140)
    parser.add_argument("--max-cases", type=int, default=0)
    parser.add_argument("--url", default=os.getenv("RETRO_V2_NEXTCLOUD_URL"))
    parser.add_argument("--user", default=os.getenv("RETRO_V2_NEXTCLOUD_USER"))
    parser.add_argument("--instance-id", default=os.getenv("RETRO_V2_NEXTCLOUD_INSTANCE_ID"))
    args = parser.parse_args()
    if args.dpi < 72 or args.dpi > 180 or args.max_cases < 0:
        parser.error("DPI muss zwischen 72 und 180 liegen; max-cases >= 0")
    if not all((args.url, args.user, args.instance_id)):
        parser.error("Nextcloud-WebDAV-Konfiguration fehlt")
    if args.output.exists():
        parser.error("Ausgabeverzeichnis existiert bereits; vorhandene Reviews nicht überschreiben")

    report = json.loads(args.quality_report.read_text(encoding="utf-8"))
    cases = choose_cases(report, args.max_cases)
    password = os.getenv("RETRO_V2_NEXTCLOUD_APP_PASSWORD") or getpass.getpass(
        "Nextcloud-App-Passwort: "
    )
    dav = WebDAV(args.url, args.user, password, instance_id=args.instance_id)
    files_by_key = {f.source_key: f for f in dav.list_files()}
    downloads: dict[str, bytes] = {}
    args.output.mkdir(parents=True, exist_ok=False)
    exported = 0
    try:
        for case in cases:
            file = files_by_key.get(case["source_key"])
            if file is None or file.name != case["name"]:
                raise RuntimeError(f"Nextcloud-Quelle nicht mehr vorhanden: {case['name']}")
            if file.byte_size is None or file.byte_size > MAX_BYTES:
                raise ValueError(f"Unbekannte/zu große Datei: {case['name']}")
            digest = case["sha256"]
            if digest not in downloads:
                data = dav.download(file, max_bytes=MAX_BYTES)
                if hashlib.sha256(data).hexdigest() != digest:
                    raise ValueError(f"PDF-Inhalt hat sich verändert: {case['name']}")
                with pymupdf.open(stream=data, filetype="pdf") as doc:
                    if doc.needs_pass or len(doc) > MAX_PAGES:
                        raise ValueError(f"Geschützte/zu lange PDF: {case['name']}")
                downloads[digest] = data
            folder = args.output / f"{safe_stem(case['name'])}-{digest[:12]}-p{case['page']:04d}"
            export_page(downloads[digest], case, folder, args.dpi)
            exported += 1
            print(f"[{exported}/{len(cases)}] {case['name']} S. {case['page']}", flush=True)
    finally:
        # Keine vollständigen PDFs auf die Platte schreiben; nur Arbeitsartefakte.
        downloads.clear()
    (args.output / "README.txt").write_text(
        "LOKAL VERTRAULICH: Bilder, extrahierte Texte, SHA-256 und Quellbezüge. "
        "Nicht in Git committen. review.json manuell anhand page.png prüfen; "
        "NULL bedeutet ausdrücklich noch nicht bewertet.\n",
        encoding="utf-8",
    )
    print(f"Prüfpakete: {exported}. Lokal: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
