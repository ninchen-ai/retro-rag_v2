"""Schreibfreie Auswahl- und Analysefunktionen für Nextcloud-PDFs."""

from retro_rag.importer.webdav import RemoteFile
from retro_rag.importer.pdf_survey import category, select_candidates, size_class, inspect_pdf


def file(key, name, size=1000):
    return RemoteFile(
        source_key=key,
        uri=f"https://cloud.example.test/remote.php/dav/files/user/{name}",
        name=name,
        etag=None,
        byte_size=size,
        content_type="application/pdf",
    )


def test_balanced_candidates_are_deterministic():
    files = [
        file("1", "agp30.pdf"),
        file("2", "asus-cubx-manual.pdf"),
        file("3", "chipset-datasheet.pdf"),
        file("4", "misc.pdf"),
        file("5", "agp20.pdf"),
    ]
    result = select_candidates(files, 4)
    assert len(result) == 4
    assert len({category(f) for f in result}) == 4
    assert select_candidates(files, 4) == result


def test_unknown_and_oversized_are_not_downloaded():
    files = [file("1", "small.pdf"), file("2", "unknown.pdf", None),
             file("3", "huge.pdf", 60 * 1024 * 1024)]
    assert select_candidates(files, 99) == files[:1]
    assert size_class(None) == "unknown"


def test_rejects_negative_count():
    import pytest
    with pytest.raises(ValueError):
        select_candidates([], -1)


def test_pdf_inspection_with_bookmarks():
    import pymupdf

    doc = pymupdf.open()
    doc.new_page().insert_text((50, 70), "ASUS BIOS")
    doc.new_page()
    doc.set_toc([[1, "BIOS", 1]])
    data = doc.tobytes()
    doc.close()
    result = inspect_pdf(data)
    assert result["status"] == "ok"
    assert result["page_count"] == 2
    assert result["bookmarks"] == 1
    assert result["sampled_pages"] == [1, 2]
    assert result["sampled_low_text_pages"] == 1
