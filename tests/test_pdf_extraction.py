"""Regressionstests für die aus V1 abgeleitete schreibfreie PDF-Extraktion."""

import pytest

pymupdf = pytest.importorskip("pymupdf")

from retro_rag.importer.pdf import outline_by_page, read_pdf, split_page


def test_split_page_keeps_limits_and_content():
    text = "Alpha Beta\n\nGamma Delta\n\nEpsilon"
    parts = split_page(text, max_chars=12)
    assert parts
    assert all(0 < len(part) <= 12 for part in parts)
    assert "".join(parts) == text


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


def test_outline_hierarchy_and_provenance(tmp_path):
    path = tmp_path / "chapters.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_text((40, 70), "BIOS summary")
    doc.new_page().insert_text((40, 70), "Advanced settings")
    doc.set_toc([[1, "BIOS", 1], [2, "Advanced", 2]])
    doc.save(path)
    doc.close()

    result = read_pdf(path, "nc:test:chapters", max_chars=7)
    assert {tuple(c.heading_path) for c in result.chunks if c.page == 1} == {("BIOS",)}
    assert {tuple(c.heading_path) for c in result.chunks if c.page == 2} == {
        ("BIOS", "Advanced")
    }
    with pymupdf.open(path) as doc:
        for n in (1, 2):
            original = doc[n - 1].get_text("text", sort=True)
            assert "".join(c.text for c in result.chunks if c.page == n) == original
    assert result.document.metadata["outline_headings_are_hints"] is True


def test_outline_invalid_entries_and_no_guessing():
    assert outline_by_page([[1, "Valid", 1], [2, "Out", 10], [0, "Bad", 1]], 2) == {
        1: ["Valid"]
    }
    assert outline_by_page([], 2) == {}


def test_split_preserves_whitespace_at_boundaries():
    text = ("alpha beta\n\n" * 23) + "final\n"
    assert "".join(split_page(text, max_chars=37)) == text
    assert all(len(p) <= 37 for p in split_page(text, max_chars=37))
