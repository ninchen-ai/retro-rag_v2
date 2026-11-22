"""Optionale, schreibfreie Seiten-OCR für den PDF-Import.

Die Entscheidung ist konservativ: automatische OCR nur bei wenig eingebettetem
Text UND hoher Bildabdeckung. Eine explizite Seitenliste erlaubt geprüfte Ausnahmen.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pymupdf

OcrMode = Literal["off", "auto"]
MIN_TEXT_CHARS = 40
MIN_IMAGE_COVERAGE = 0.5


@dataclass(frozen=True)
class PageText:
    text: str
    status: Literal["native", "ocr", "ocr_failed", "empty"]
    warning: str | None = None


def is_ocr_candidate(page: pymupdf.Page, native_text: str) -> bool:
    """Heuristischer Scanverdacht; keine Qualitätsgarantie."""
    if len(native_text.strip()) >= MIN_TEXT_CHARS:
        return False
    area = page.rect.width * page.rect.height
    if area <= 0:
        return False
    image_area = 0.0
    for info in page.get_image_info(hashes=False, xrefs=False):
        if "bbox" not in info:
            continue
        rect = pymupdf.Rect(info["bbox"]) & page.rect
        image_area += max(rect.width, 0) * max(rect.height, 0)
    return min(1.0, image_area / area) >= MIN_IMAGE_COVERAGE


def extract_page_text(
    page: pymupdf.Page,
    *,
    mode: OcrMode = "off",
    force: bool = False,
    language: str = "eng+deu",
    dpi: int = 200,
) -> PageText:
    """Gibt PDF-Text oder OCR-Text zurück, ohne Quelle oder DB zu verändern.

    `force` nur nach Sichtprüfung der einzelnen Seite setzen. Bei OCR-Fehler
    bleibt vorhandener nativer Text erhalten und der Fehler wird ausgewiesen.
    """
    if mode not in ("off", "auto"):
        raise ValueError("OCR-Modus muss 'off' oder 'auto' sein")
    if not 100 <= dpi <= 300:
        raise ValueError("OCR-DPI muss zwischen 100 und 300 liegen")
    if not language or not language.strip():
        raise ValueError("OCR-Sprache darf nicht leer sein")
    native = page.get_text("text", sort=True)
    should_ocr = mode == "auto" and (force or is_ocr_candidate(page, native))
    if not should_ocr:
        return PageText(native, "native" if native.strip() else "empty")
    try:
        textpage = page.get_textpage_ocr(language=language, dpi=dpi, full=True)
        extracted = page.get_text("text", sort=True, textpage=textpage)
    except (RuntimeError, ValueError, OSError) as exc:
        return PageText(native, "ocr_failed", f"OCR fehlgeschlagen ({type(exc).__name__}: {exc})")
    if not extracted.strip():
        return PageText(native, "ocr_failed", "OCR lieferte keinen Text")
    return PageText(extracted, "ocr")
