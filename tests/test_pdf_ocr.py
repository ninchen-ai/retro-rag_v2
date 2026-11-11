"""Tests für die optionale Seiten-OCR ohne Tesseract-Laufzeitpflicht."""
import pytest

pymupdf = pytest.importorskip("pymupdf")

from retro_rag.importer.pdf import read_pdf
from retro_rag.importer.pdf_ocr import extract_page_text, is_ocr_candidate


def _page_with_image(doc):
    page = doc.new_page(width=200, height=200)
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 10, 10), 0)
    pix.clear_with(255)
    page.insert_image(page.rect, pixmap=pix)
    return page


def test_no_ocr_by_default(monkeypatch):
    with pymupdf.open() as doc:
        page = _page_with_image(doc)
        assert is_ocr_candidate(page, "") is True
        def never(**kwargs):
            raise AssertionError("OCR darf nicht laufen")
        monkeypatch.setattr(page, "get_textpage_ocr", never)
        assert extract_page_text(page).status == "empty"


def test_auto_ocr_scan_and_status(monkeypatch):
    with pymupdf.open() as doc:
        page = _page_with_image(doc)
        def fake_ocr(**kwargs):
            return page.get_textpage()
        monkeypatch.setattr(page, "get_textpage_ocr", fake_ocr)
        assert extract_page_text(page, mode="auto").status == "ocr_failed"


def test_auto_preserves_native_text(monkeypatch):
    with pymupdf.open() as doc:
        page = doc.new_page()
        page.insert_text((40, 70), "A" * 80)
        def never(**kwargs):
            raise AssertionError("OCR darf nicht laufen")
        monkeypatch.setattr(page, "get_textpage_ocr", never)
        result = extract_page_text(page, mode="auto")
        assert result.status == "native"
        assert "AAAA" in result.text


def test_ocr_failure_preserves_original(monkeypatch):
    with pymupdf.open() as doc:
        page = _page_with_image(doc)
        def fail(**kwargs):
            raise RuntimeError("Tesseract fehlt")
        monkeypatch.setattr(page, "get_textpage_ocr", fail)
        result = extract_page_text(page, mode="auto")
        assert result.status == "ocr_failed"
        assert "Tesseract fehlt" in result.warning


def test_force_single_page(monkeypatch):
    with pymupdf.open() as doc:
        page = doc.new_page()
        page.insert_text((40, 70), "Existing")
        def fail(**kwargs):
            raise RuntimeError("test")
        monkeypatch.setattr(page, "get_textpage_ocr", fail)
        result = extract_page_text(page, mode="auto", force=True)
        assert result.status == "ocr_failed"
        assert "Existing" in result.text


def test_read_pdf_keeps_gate_closed_and_tracks_ocr(tmp_path, monkeypatch):
    path = tmp_path / "scan.pdf"
    with pymupdf.open() as doc:
        _page_with_image(doc)
        doc.save(path)
    def fail(self, **kwargs):
        raise RuntimeError("OCR missing")
    monkeypatch.setattr(pymupdf.Page, "get_textpage_ocr", fail)
    result = read_pdf(path, "nc:scan", ocr_mode="auto")
    assert result.indexing_allowed is False
    assert result.document.metadata["ocr_failed_pages"] == [1]
    assert any("OCR fehlgeschlagen" in warning for warning in result.warnings)


@pytest.mark.parametrize("value", [0, 99, 301])
def test_invalid_ocr_dpi(value):
    with pymupdf.open() as doc:
        page = doc.new_page()
        with pytest.raises(ValueError, match="DPI"):
            extract_page_text(page, dpi=value)
