"""Tests für den schreibfreien seitenweisen PDF-Qualitätsbericht."""

import hashlib
import json
import sys

import pymupdf
import pytest

from retro_rag.importer import pdf_quality
from retro_rag.importer.pdf_quality import _write_report, analyze_pdf


def test_full_document_metrics_and_no_text_leakage():
    doc = pymupdf.open()
    doc.new_page().insert_text((50, 70), "ASUS BIOS")
    doc.new_page()
    doc.new_page().insert_text((50, 70), "Bus clock setting " * 6)
    doc.set_toc([[1, "BIOS", 1], [2, "Advanced", 3]])
    data = doc.tobytes()
    doc.close()
    result = analyze_pdf(data, detect_tables=False)
    assert result["status"] == "ok"
    assert result["page_count"] == 3
    assert result["pages_analyzed"] == 3
    assert result["bookmarks"] == 2
    assert result["empty_pages"] == 1
    assert result["low_text_pages"] == 2
    assert result["pages"][0]["characters"] == 9
    assert result["pages"][1]["empty_text"] is True
    assert result["pages"][0]["table_candidates"] is None
    assert result["sha256"] == hashlib.sha256(data).hexdigest()
    assert "ASUS BIOS" not in json.dumps(result)


def test_large_image_without_text_is_ocr_candidate():
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=400)
    image = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 20, 20), 0)
    image.clear_with(180)
    page.insert_image(page.rect, pixmap=image)
    data = doc.tobytes()
    doc.close()
    result = analyze_pdf(data, detect_tables=False)
    assert result["ocr_candidate_pages"] == 1
    assert result["pages"][0]["image_count"] >= 1
    assert result["pages"][0]["image_coverage_upper_bound"] >= 0.95


def test_two_column_layout_flagged_heuristically():
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    for x in (45, 345):
        page.insert_textbox(
            pymupdf.Rect(x, 75, x + 200, 290),
            "Memory controller and PCI bridge interface. " * 8,
            fontsize=10,
        )
    data = doc.tobytes()
    doc.close()
    result = analyze_pdf(data, detect_tables=False)
    assert result["pages"][0]["possible_multicolumn"] is True


def test_limits_and_signature():
    doc = pymupdf.open()
    doc.new_page()
    doc.new_page()
    data = doc.tobytes()
    doc.close()
    with pytest.raises(ValueError, match="Seitenlimit"):
        analyze_pdf(data, max_pages=1)
    with pytest.raises(ValueError, match="Signatur"):
        analyze_pdf(b"not a pdf")
    with pytest.raises(ValueError, match="positiv"):
        analyze_pdf(data, max_pages=0)


def test_table_detection_on_line_grid():
    doc = pymupdf.open()
    page = doc.new_page()
    for x in (50, 170, 290):
        page.draw_line((x, 100), (x, 210))
    for y in (100, 155, 210):
        page.draw_line((50, y), (290, y))
    for x, y, value in (
        (60, 115, "CPU"), (180, 115, "Clock"),
        (60, 170, "386DX"), (180, 170, "40 MHz"),
    ):
        page.insert_text((x, y), value)
    data = doc.tobytes()
    doc.close()
    result = analyze_pdf(data)
    assert result["status"] == "ok"
    assert result["table_candidates"] >= 1


def test_report_is_written_as_valid_json(tmp_path):
    target = tmp_path / "result.json"
    _write_report(target, {"completed": False, "results": []})
    _write_report(target, {"completed": True, "results": [{"source_key": "123"}]})
    assert json.loads(target.read_text(encoding="utf-8"))["completed"] is True
    assert list(tmp_path.iterdir()) == [target]


def test_cli_processes_all_files_and_reports_duplicate_hashes(tmp_path, monkeypatch):
    doc = pymupdf.open()
    doc.new_page().insert_text((50, 70), "Intel AGP specification")
    content = doc.tobytes()
    doc.close()

    class FakeFile:
        def __init__(self, key):
            self.source_key = key
            self.name = f"manual-{key}.pdf"
            self.byte_size = len(content)

    class FakeWebDAV:
        def __init__(self, *args, **kwargs):
            pass

        def list_files(self, max_directories=1000):
            return [FakeFile("172"), FakeFile("173")]

        def download(self, file, max_bytes=0):
            assert max_bytes >= len(content)
            return content

    monkeypatch.setattr(pdf_quality, "WebDAV", FakeWebDAV)
    monkeypatch.setenv("RETRO_V2_NEXTCLOUD_URL", "https://cloud.example.test/dav")
    monkeypatch.setenv("RETRO_V2_NEXTCLOUD_USER", "test")
    monkeypatch.setenv("RETRO_V2_NEXTCLOUD_INSTANCE_ID", "test-instance")
    monkeypatch.setenv("RETRO_V2_NEXTCLOUD_APP_PASSWORD", "dummy")
    report_path = tmp_path / "quality.json"
    monkeypatch.setattr(sys, "argv", [
        "pdf_quality", "--report", str(report_path), "--no-tables",
    ])
    assert pdf_quality.main() == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["completed"] is True
    assert report["selected_pdf_count"] == 2
    assert report["duplicate_sha256_groups"] == [["172", "173"]]
    assert all(item["status"] == "ok" for item in report["results"])


def test_cli_failed_file_is_visible_in_report(tmp_path, monkeypatch):
    class MissingSize:
        source_key = "1"
        name = "unknown.pdf"
        byte_size = None

    class FakeWebDAV:
        def __init__(self, *args, **kwargs):
            pass

        def list_files(self, max_directories=1000):
            return [MissingSize()]

        def download(self, file, max_bytes=0):
            raise AssertionError("Download darf bei unbekannter Größe nicht starten")

    monkeypatch.setattr(pdf_quality, "WebDAV", FakeWebDAV)
    monkeypatch.setenv("RETRO_V2_NEXTCLOUD_URL", "https://cloud.example.test/dav")
    monkeypatch.setenv("RETRO_V2_NEXTCLOUD_USER", "test")
    monkeypatch.setenv("RETRO_V2_NEXTCLOUD_INSTANCE_ID", "test-instance")
    monkeypatch.setenv("RETRO_V2_NEXTCLOUD_APP_PASSWORD", "dummy")
    report_path = tmp_path / "quality.json"
    monkeypatch.setattr(sys, "argv", [
        "pdf_quality", "--report", str(report_path),
    ])
    assert pdf_quality.main() == 1
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["completed"] is True
    assert report["results"][0]["status"] == "error"
