"""Regressionstests für den lokalen PDF-Goldstandard-Vorbereitungsschritt."""

import hashlib
import json
import sys

import pymupdf
import pytest

from retro_rag.importer import pdf_goldstandard as gs


def _pdf():
    doc = pymupdf.open()
    doc.new_page().insert_text((40, 80), "ASUS CUBX reference text")
    doc.new_page()
    result = doc.tobytes()
    doc.close()
    return result


def _report(data):
    digest = hashlib.sha256(data).hexdigest()
    return {
        "completed": True,
        "mode": "read_only_no_db_writes_full_page_quality",
        "results": [{
            "name": "cubx-103.pdf",
            "source_key": "172",
            "sha256": digest,
            "status": "ok",
            "page_count": 2,
            "pages": [
                {"page": 1, "characters": 24},
                {"page": 2, "characters": 0, "ocr_candidate": False},
            ],
        }],
    }


def test_case_selection_rejects_incomplete_report():
    with pytest.raises(ValueError, match="Vollständig"):
        gs.choose_cases({"completed": False})


def test_unreviewed_template_must_not_infer_ground_truth():
    case = {
        "sha256": "a" * 64, "page": 1, "focus": "ocr",
    }
    result = gs.evaluation_template(case)
    assert result["review_status"] == "unreviewed"
    assert all(value is None for value in result["labels"].values())
    assert all(value == [] for value in result["reference"].values())


def test_pdf_page_export_is_visual_and_does_not_write_pdf(tmp_path):
    data = _pdf()
    case = {
        "sha256": hashlib.sha256(data).hexdigest(),
        "page": 1, "focus": "headings",
        "metrics": {"page": 1, "characters": 24},
    }
    target = tmp_path / "gold-page"
    gs.export_page(data, case, target, dpi=90)
    assert (target / "page.png").read_bytes().startswith(b"\x89PNG")
    assert "CUBX" in (target / "extracted.txt").read_text()
    review = json.loads((target / "review.json").read_text())
    assert review["labels"]["ocr_needed"] is None
    assert review["pdf_page_1_based"] == 1
    assert not list(target.glob("*.pdf"))
    with pytest.raises(FileExistsError):
        gs.export_page(data, case, target, dpi=90)


def test_ambiguous_pdf_name_is_rejected(monkeypatch):
    monkeypatch.setattr(gs, "CASES", (("3C905CX.pdf", 1, "ocr"),))
    report = {
        "completed": True,
        "mode": "read_only_no_db_writes_full_page_quality",
        "results": [
            {"name": "3C905CX.pdf", "source_key": "1", "sha256": "a" * 64,
             "status": "ok", "page_count": 1, "pages": [{"page": 1}]},
            {"name": "3C905CX.pdf", "source_key": "2", "sha256": "b" * 64,
             "status": "ok", "page_count": 1, "pages": [{"page": 1}]},
        ],
    }
    with pytest.raises(ValueError, match="Mehrdeutige"):
        gs.choose_cases(report)


def test_choose_unique_sha_for_duplicate_source(monkeypatch):
    monkeypatch.setattr(gs, "CASES", (("3C905CX.pdf", 1, "ocr"),))
    item = {
        "name": "3C905CX.pdf", "sha256": "a" * 64,
        "status": "ok", "page_count": 1, "pages": [{"page": 1}],
    }
    report = {
        "completed": True,
        "mode": "read_only_no_db_writes_full_page_quality",
        "results": [{**item, "source_key": "475"}, {**item, "source_key": "246"}],
    }
    result = gs.choose_cases(report)
    assert len(result) == 1
    assert result[0]["source_key"] == "246"


def test_end_to_end_cli_uses_hash_check_and_local_output(tmp_path, monkeypatch):
    data = _pdf()
    monkeypatch.setattr(gs, "CASES", (("cubx-103.pdf", 1, "headings"),))
    quality_file = tmp_path / "quality.json"
    quality_file.write_text(json.dumps(_report(data)))
    class FakeFile:
        source_key = "172"
        name = "cubx-103.pdf"
        byte_size = len(data)

    class FakeWebDAV:
        def __init__(self, *args, **kwargs):
            pass

        def list_files(self):
            return [FakeFile()]

        def download(self, file, max_bytes):
            return data

    monkeypatch.setattr(gs, "WebDAV", FakeWebDAV)
    monkeypatch.setenv("RETRO_V2_NEXTCLOUD_URL", "https://example.invalid/dav")
    monkeypatch.setenv("RETRO_V2_NEXTCLOUD_USER", "test")
    monkeypatch.setenv("RETRO_V2_NEXTCLOUD_INSTANCE_ID", "instance")
    monkeypatch.setenv("RETRO_V2_NEXTCLOUD_APP_PASSWORD", "dummy")
    destination = tmp_path / "goldstandard"
    monkeypatch.setattr(sys, "argv", [
        "pdf_goldstandard", "--quality-report", str(quality_file),
        "--output", str(destination), "--dpi", "90",
    ])
    assert gs.main() == 0
    assert len(list(destination.glob("*/page.png"))) == 1
    assert len(list(destination.glob("*/review.json"))) == 1
    assert (destination / "README.txt").exists()
    with pytest.raises(SystemExit):
        gs.main()


def test_changed_pdf_refused_before_export(tmp_path, monkeypatch):
    original = _pdf()
    changed = original + b"\n"
    monkeypatch.setattr(gs, "CASES", (("cubx-103.pdf", 1, "headings"),))
    quality_file = tmp_path / "quality.json"
    quality_file.write_text(json.dumps(_report(original)))
    class FakeFile:
        source_key = "172"
        name = "cubx-103.pdf"
        byte_size = len(changed)

    class FakeWebDAV:
        def __init__(self, *args, **kwargs):
            pass

        def list_files(self):
            return [FakeFile()]

        def download(self, file, max_bytes):
            return changed

    monkeypatch.setattr(gs, "WebDAV", FakeWebDAV)
    monkeypatch.setenv("RETRO_V2_NEXTCLOUD_URL", "https://example.invalid/dav")
    monkeypatch.setenv("RETRO_V2_NEXTCLOUD_USER", "test")
    monkeypatch.setenv("RETRO_V2_NEXTCLOUD_INSTANCE_ID", "instance")
    monkeypatch.setenv("RETRO_V2_NEXTCLOUD_APP_PASSWORD", "dummy")
    dest = tmp_path / "out"
    monkeypatch.setattr(sys, "argv", [
        "pdf_goldstandard", "--quality-report", str(quality_file),
        "--output", str(dest),
    ])
    with pytest.raises(ValueError, match="verändert"):
        gs.main()
    assert not list(dest.glob("*/page.png"))
