"""Schreibfreier Nextcloud-PDF-Katalog mit repräsentativer Qualitätsstichprobe."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import getpass
import json
import os
from pathlib import Path

from retro_rag.importer.webdav import RemoteFile, WebDAV

MAX_PDF_BYTES = 50 * 1024 * 1024

KEYWORDS = {
    "datasheets": ("datasheet", "data-sheet", "data sheet", "chipset", "processor", "cpu"),
    "standards": ("agp", "specification", "standard", "design guide", "usb", "ehci", "xhci"),
    "manuals": ("manual", "user guide", "mainboard", "motherboard", "bios", "asus", "msi"),
}


def category(file: RemoteFile) -> str:
    """Vorrang für Datenblätter; keine Teiltreffer wie 'ata' in 'datasheet'."""
    from urllib.parse import unquote, urlsplit

    path = unquote(urlsplit(file.uri).path).casefold()
    filename = file.name.casefold()
    # Datenblattnamen haben Vorrang vor Begriffen im übergeordneten Verzeichnis.
    if any(word in filename for word in ("datasheet", "data-sheet", "data sheet")):
        return "datasheets"
    for group, terms in KEYWORDS.items():
        if any(term in path for term in terms):
            return group
    return "other"


def size_class(size: int | None) -> str:
    if size is None:
        return "unknown"
    if size < 500_000:
        return "small"
    if size < 5_000_000:
        return "medium"
    return "large"


def select_candidates(files: list[RemoteFile], count: int) -> list[RemoteFile]:
    """Round-robin über Kategorie und Dateigrößenklassen; deterministische Stichprobe."""
    if count < 0:
        raise ValueError("Stichprobengröße darf nicht negativ sein")
    buckets: dict[tuple[str, str], list[RemoteFile]] = defaultdict(list)
    for file in files:
        if file.byte_size is not None and file.byte_size > MAX_PDF_BYTES:
            continue
        if file.byte_size is None:
            continue  # Keine unbeschränkten Downloads ohne verifizierte Größenangabe.
        buckets[(category(file), size_class(file.byte_size))].append(file)
    for group in buckets.values():
        group.sort(key=lambda f: (f.source_key, f.uri))
    keys = sorted(buckets)
    result: list[RemoteFile] = []
    while len(result) < count and any(buckets.values()):
        for key in keys:
            if buckets[key] and len(result) < count:
                result.append(buckets[key].pop(0))
    return result


def inspect_pdf(data: bytes, max_pages: int = 12) -> dict:
    """Einige über die PDF verteilte Seiten messen; keine OCR, keine Indexierung."""
    import pymupdf

    if not data.startswith(b"%PDF-"):
        raise ValueError("Keine PDF-Signatur")
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        if doc.needs_pass:
            return {"status": "encrypted", "page_count": len(doc)}
        total = len(doc)
        positions = (
            sorted({round(i * (total - 1) / (min(max_pages, total) - 1))
                    for i in range(min(max_pages, total))})
            if total > 1 else ([0] if total == 1 else [])
        )
        chars: list[int] = []
        image_counts: list[int] = []
        large_font_spans = 0
        for index in positions:
            page = doc[index]
            text = page.get_text("text", sort=True)
            chars.append(len(text.strip()))
            image_counts.append(len(page.get_images(full=True)))
            details = page.get_text("dict")
            font_sizes = [
                span["size"]
                for block in details.get("blocks", [])
                if "lines" in block
                for line in block["lines"]
                for span in line["spans"]
                if span.get("text", "").strip()
            ]
            if font_sizes:
                baseline = sorted(font_sizes)[len(font_sizes) // 2]
                large_font_spans += sum(size > baseline * 1.25 for size in font_sizes)
        return {
            "status": "ok",
            "page_count": total,
            "bookmarks": len(doc.get_toc()),
            "sampled_pages": [p + 1 for p in positions],
            "sampled_characters": chars,
            "sampled_images": image_counts,
            "sampled_low_text_pages": sum(c < 40 for c in chars),
            "sampled_heading_size_candidates": large_font_spans,
            "note": "Stichprobenwerte, keine vollständige OCR-/Layoutbewertung",
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Nextcloud-PDF-Katalog und schreibfreie Stichprobe")
    parser.add_argument("--url", default=os.getenv("RETRO_V2_NEXTCLOUD_URL"))
    parser.add_argument("--user", default=os.getenv("RETRO_V2_NEXTCLOUD_USER"))
    parser.add_argument("--instance-id", default=os.getenv("RETRO_V2_NEXTCLOUD_INSTANCE_ID"))
    parser.add_argument("--sample", type=int, default=30, help="Anzahl zu analysierender PDFs")
    parser.add_argument("--analyze-all", action="store_true", help="Alle geeigneten PDFs analysieren")
    parser.add_argument("--max-directories", type=int, default=1000)
    parser.add_argument("--report", type=Path, default=Path("/tmp/retro-v2-pdf-survey.json"))
    args = parser.parse_args()
    if not args.url or not args.user or not args.instance_id:
        parser.error("URL, Benutzer und stabile Nextcloud-Instanzkennung erforderlich")
    if args.sample < 0:
        parser.error("--sample darf nicht negativ sein")

    password = os.getenv("RETRO_V2_NEXTCLOUD_APP_PASSWORD")
    if not password:
        password = getpass.getpass("Nextcloud-App-Passwort: ")
    dav = WebDAV(args.url, args.user, password, instance_id=args.instance_id)
    files = [f for f in dav.list_files(max_directories=args.max_directories)
             if f.name.casefold().endswith(".pdf")]
    selected = select_candidates(files, len(files) if args.analyze_all else args.sample)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "read_only_no_db_writes",
        "pdf_count": len(files),
        "category_counts": dict(Counter(category(f) for f in files)),
        "size_class_counts": dict(Counter(size_class(f.byte_size) for f in files)),
        "files": [
            {
                "source_key": f.source_key,
                "uri": f.uri,
                "name": f.name,
                "etag": f.etag,
                "size": f.byte_size,
                "category_guess": category(f),
                "selected": f in selected,
            }
            for f in files
        ],
        "analysis": [],
    }
    for index, file in enumerate(selected, start=1):
        entry = {"source_key": file.source_key, "name": file.name}
        try:
            # Nur bei vorher bekannter, begrenzter Größe herunterladen.
            data = dav.download(file, max_bytes=MAX_PDF_BYTES)
            entry.update(inspect_pdf(data))
        except Exception as exc:
            entry.update(status="error", error=f"{type(exc).__name__}: {exc}")
        report["analysis"].append(entry)
        print(f"[{index}/{len(selected)}] {file.name}: {entry['status']}", flush=True)
    # Bericht lokal, nie in Git einchecken (private Nextcloud-Pfade).
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"PDFs entdeckt: {len(files)}, analysiert: {len(selected)}")
    print(f"Bericht: {args.report} (enthält interne Dateipfade)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
