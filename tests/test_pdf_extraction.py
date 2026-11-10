"""Regressionstests für die aus V1 abgeleitete schreibfreie PDF-Extraktion."""

import pytest

pymupdf = pytest.importorskip("pymupdf")

from retro_rag.importer.pdf import read_pdf, split_page


def test_split_page_keeps_limits_and_content():
    text = "Alpha Beta\n\nGamma Delta\n\nEpsilon"
    parts = split_page(text, max_chars=12)
    assert parts
    assert all(0 < len(part) <= 12 for part in parts)
    assert " ".join(" ".join(parts).split()) == " ".join(text.split())


def test_pdf_page_references_and_no_writes(tmp_path):
    pdf_path = tmp_path / "manual.pdf"
    doc = pymupdf.open()
    first = doc.new_page()
    first.insert_text((40, 70), "ASUS CUBX")
    doc.new_page()
    doc.save(pdf_path)
    doc.close()

    result = read_pdf(pdf_path, "nc:example:172")
    assert result.source.kind == "pdf"
    assert result.document.metadata["page_count"] == 2
    assert result.chunks[0].page == 1
    assert "ASUS CUBX" in result.chunks[0].text
    assert result.indexing_allowed is False
    assert result.fact_proposals == []
    assert any("Seite 2" in warning for warning in result.warnings)


def test_pdf_rejects_bad_signature(tmp_path):
    path = tmp_path / "fake.pdf"
    path.write_bytes(b"not a pdf")
    with pytest.raises(ValueError, match="Signatur"):
        read_pdf(path, "test")


def test_pdf_rejects_page_limit(tmp_path):
    path = tmp_path / "long.pdf"
    doc = pymupdf.open()
    doc.new_page()
    doc.new_page()
    doc.save(path)
    doc.close()
    with pytest.raises(ValueError, match="Seitenbegrenzung"):
        read_pdf(path, "test", max_pages=1)


def test_pdf_rejects_size_limit(tmp_path):
    path = tmp_path / "big.pdf"
    path.write_bytes(b"%PDF-" + b"x" * 100)
    with pytest.raises(ValueError, match="Größenbegrenzung"):
        read_pdf(path, "test", max_bytes=10)
