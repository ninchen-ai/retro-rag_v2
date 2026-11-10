"""Schreibfreier PDF-Adapter für den V2-Importvertrag (ohne OCR)."""

from __future__ import annotations

import hashlib
from pathlib import Path

from retro_rag.importer.contract import Chunk, Document, ImportContract, Source

DEFAULT_MAX_BYTES = 50 * 1024 * 1024
DEFAULT_MAX_PAGES = 500


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
) -> ImportContract:
    """PDF nur lesen und Vorschlagsdaten erzeugen; keine Indexierung oder DB-Schreibzugriffe."""
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
    with pymupdf.open(stream=raw, filetype="pdf") as pdf:
        if pdf.needs_pass:
            raise ValueError("Passwortgeschützte PDFs benötigen einen gesonderten Review")
        if len(pdf) > max_pages:
            raise ValueError("PDF überschreitet die Seitenbegrenzung")
        metadata = pdf.metadata or {}
        page_count = len(pdf)
        bookmarks = outline_by_page(pdf.get_toc(), page_count)
        heading_path: list[str] = []
        for page_number, page in enumerate(pdf, start=1):
            if page_number in bookmarks:
                heading_path = bookmarks[page_number]
            text = page.get_text("text", sort=True)
            parts = split_page(text, max_chars)
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
                "ocr_performed": False,
                "chunker_version": "pdf-outline-v1",
                "outline_headings_are_hints": True,
            },
        ),
        chunks=chunks,
        warnings=warnings,
        indexing_allowed=False,
    )
