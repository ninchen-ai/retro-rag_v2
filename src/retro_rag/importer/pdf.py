"""Schreibfreier PDF-Adapter mit optionaler seitenweiser OCR."""

from __future__ import annotations

import hashlib
from pathlib import Path

from retro_rag.importer.contract import Chunk, Document, ImportContract, Source
from retro_rag.importer.pdf_ocr import extract_page_text

DEFAULT_MAX_BYTES = 50 * 1024 * 1024
DEFAULT_MAX_PAGES = 1000


def split_page(text: str, max_chars: int = 4000) -> list[str]:
    """Text verlustfrei an Absatz-, Zeilen- oder Wortgrenzen teilen."""
    if max_chars <= 0:
        raise ValueError("max_chars muss positiv sein")
    if not text or not text.strip():
        return []
    parts: list[str] = []
    remaining = text
    while len(remaining) > max_chars:
        window = remaining[:max_chars]
        cut = -1
        for delimiter in ("\n\n", "\n", " "):
            pos = window.rfind(delimiter, max_chars // 2)
            if pos >= 0:
                cut = pos + len(delimiter)
                break
        if cut <= 0:
            cut = max_chars
        parts.append(remaining[:cut])
        remaining = remaining[cut:]
    if remaining:
        parts.append(remaining)
    return parts


def outline_by_page(toc: list[list], page_count: int) -> dict[int, list[str]]:
    """Bookmark-Hierarchie als Seitenhinweis; keine verifizierte Abschnittsgrenze."""
    result: dict[int, list[str]] = {}
    stack: list[str] = []
    for entry in toc:
        if len(entry) < 3:
            continue
        level, title, page = entry[:3]
        if not isinstance(level, int) or level < 1 or not isinstance(page, int):
            continue
        if not 1 <= page <= page_count:
            continue
        title = str(title).strip()
        if not title:
            continue
        stack = stack[:max(0, level - 1)]
        stack.append(title)
        result[page] = stack.copy()
    return result


def read_pdf(
    path: Path,
    source_id: str,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
    max_pages: int = DEFAULT_MAX_PAGES,
    max_chars: int = 4000,
    ocr_mode: str = "off",
    ocr_pages: set[int] | None = None,
    ocr_language: str = "eng+deu",
    ocr_dpi: int = 200,
) -> ImportContract:
    """PDF nur lesen und Vorschlagsdaten erzeugen; keine Indexierung oder DB-Schreibzugriffe."""
    if ocr_mode not in ("off", "auto"):
        raise ValueError("ocr_mode muss off oder auto sein")
    if not 100 <= ocr_dpi <= 300:
        raise ValueError("ocr_dpi muss zwischen 100 und 300 liegen")
    if ocr_pages and (ocr_mode != "auto" or min(ocr_pages) < 1):
        raise ValueError("ocr_pages benötigt ocr_mode=auto und positive Seitenzahlen")
    if not source_id.strip():
        raise ValueError("source_id darf nicht leer sein")
    if min(max_bytes, max_pages, max_chars) <= 0:
        raise ValueError("PDF-Grenzwerte müssen positiv sein")
    if path.stat().st_size > max_bytes:
        raise ValueError("PDF überschreitet die Größenbegrenzung")
    raw = path.read_bytes()
    if not raw.startswith(b"%PDF-") or len(raw) > max_bytes:
        raise ValueError("Ungültige PDF-Signatur oder Größenbegrenzung überschritten")

    try:
        import pymupdf
    except ImportError as exc:
        raise RuntimeError("PyMuPDF fehlt: pip install -e '.[pdf]'") from exc

    chunks: list[Chunk] = []
    warnings: list[str] = []
    ocr_done: list[int] = []
    ocr_failed: list[int] = []
    with pymupdf.open(stream=raw, filetype="pdf") as pdf:
        if pdf.needs_pass:
            raise ValueError("Passwortgeschützte PDFs benötigen einen gesonderten Review")
        if len(pdf) > max_pages:
            raise ValueError("PDF überschreitet die Seitenbegrenzung")
        if ocr_pages and max(ocr_pages) > len(pdf):
            raise ValueError('ocr_pages außerhalb des PDFs')
        metadata = pdf.metadata or {}
        page_count = len(pdf)
        bookmarks = outline_by_page(pdf.get_toc(), page_count)
        heading_path: list[str] = []
        for page_number, page in enumerate(pdf, start=1):
            if page_number in bookmarks:
                heading_path = bookmarks[page_number]
            extracted = extract_page_text(
                page, mode=ocr_mode, force=page_number in (ocr_pages or ()),
                language=ocr_language, dpi=ocr_dpi,
            )
            if extracted.status == "ocr":
                ocr_done.append(page_number)
            elif extracted.status == "ocr_failed":
                ocr_failed.append(page_number)
                warnings.append(f"Seite {page_number}: {extracted.warning}")
            parts = split_page(extracted.text, max_chars)
            if not parts:
                warnings.append(f"Seite {page_number}: kein extrahierbarer Text; OCR erforderlich")
            for part in parts:
                chunks.append(
                    Chunk(
                        ordinal=len(chunks),
                        text=part,
                        chunk_hash=hashlib.sha256(part.encode("utf-8")).hexdigest(),
                        page=page_number,
                        heading_path=heading_path.copy(),
                    )
                )

    if not chunks:
        warnings.append("Keine Textinhalte extrahiert; OCR/Review erforderlich")
    return ImportContract(
        source=Source(
            source_id=source_id,
            location=str(path),
            content_hash=hashlib.sha256(raw).hexdigest(),
            kind="pdf",
        ),
        document=Document(
            title=(metadata.get("title") or "").strip() or path.stem,
            document_type="manual",
            metadata={
                "page_count": page_count,
                "pdf_format": metadata.get("format"),
                "producer": metadata.get("producer"),
                "author": metadata.get("author"),
                "extraction_engine": "PyMuPDF",
                "ocr_performed": bool(ocr_done),
                "ocr_mode": ocr_mode,
                "ocr_pages": ocr_done,
                "ocr_failed_pages": ocr_failed,
                "ocr_engine": "Tesseract/PyMuPDF" if ocr_done else None,
                "ocr_language": ocr_language if ocr_done else None,
                "ocr_dpi": ocr_dpi if ocr_done else None,
                "chunker_version": "pdf-outline-v1",
                "outline_headings_are_hints": True,
            },
        ),
        chunks=chunks,
        warnings=warnings,
        indexing_allowed=False,
    )
