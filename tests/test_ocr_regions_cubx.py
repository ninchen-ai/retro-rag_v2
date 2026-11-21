"""Regression tests for a non-persistent PDF region OCR experiment."""

import hashlib

import pytest

pymupdf = pytest.importorskip("pymupdf")

from experiments.ocr_regions_cubx import HEADLINE_LINES, Region, run_region_experiment


def sample_pdf():
    with pymupdf.open() as document:
        page = document.new_page()
        page.insert_text((50, 80), "AGP-V6800 Series")
        return document.tobytes()


def test_same_regions_two_dpi_two_psm_without_approval(tmp_path):
    data = sample_pdf()
    ocr_calls = []

    def mock_ocr(png, *, language, psm):
        assert png.startswith(b"\x89PNG")
        ocr_calls.append((language, psm))
        return "AGP-V6800 Series\n"

    target = tmp_path / "ocr-test"
    report = run_region_experiment(
        data,
        expected_sha256=hashlib.sha256(data).hexdigest(),
        output_dir=target, page_number=1, ocr=mock_ocr,
    )
    assert len(report["runs"]) == 12
    assert len(ocr_calls) == 12
    assert {item["dpi"] for item in report["runs"]} == {200, 300}
    assert {item["psm"] for item in report["runs"]} == {6, 11}
    assert report["quality_approved"] is False
    assert report["indexing_allowed"] is False
    assert report["reference_status"] == "unreviewed"
    assert all(row["status"] == "not_evaluated" for row in report["runs"])
    assert (target / "report.json").exists()
    assert len(list(target.glob("*.png"))) == 6
    assert len(list(target.glob("*.txt"))) == 12
    assert not (target / "reference.txt").exists()
    assert not (target / "review.json").exists()


def test_rejects_changed_pdf_hash_before_writes(tmp_path):
    target = tmp_path / "result"
    with pytest.raises(ValueError, match="SHA-256"):
        run_region_experiment(
            sample_pdf(), expected_sha256="0" * 64,
            output_dir=target, page_number=1,
        )
    assert not target.exists()


def test_existing_output_preserved(tmp_path):
    data = sample_pdf()
    target = tmp_path / "result"
    target.mkdir()
    (target / "keep.txt").write_text("original", encoding="utf-8")
    with pytest.raises(FileExistsError, match="existiert"):
        run_region_experiment(
            data, expected_sha256=hashlib.sha256(data).hexdigest(),
            output_dir=target, page_number=1,
        )
    assert (target / "keep.txt").read_text(encoding="utf-8") == "original"


def test_invalid_region_does_not_produce_result(tmp_path):
    data = sample_pdf()
    target = tmp_path / "result"
    with pytest.raises(ValueError, match="Regionskoordinaten"):
        run_region_experiment(
            data, expected_sha256=hashlib.sha256(data).hexdigest(),
            output_dir=target, page_number=1,
            regions=(Region("invalid", 0.4, 0.0, 0.1, 0.2),),
            ocr=lambda *a, **kw: "never",
        )
    assert not target.exists()


def test_ocr_failure_cleans_temporary_artifacts(tmp_path):
    data = sample_pdf()
    target = tmp_path / "result"

    def failed_ocr(*args, **kwargs):
        raise RuntimeError("simulated Tesseract failure")

    with pytest.raises(RuntimeError, match="Tesseract"):
        run_region_experiment(
            data, expected_sha256=hashlib.sha256(data).hexdigest(),
            output_dir=target, page_number=1, ocr=failed_ocr,
        )
    assert not target.exists()
    assert not list(tmp_path.glob(".ocr-regions-*"))


def test_page_boundaries_checked(tmp_path):
    data = sample_pdf()
    target = tmp_path / "result"
    with pytest.raises(ValueError, match="Seite"):
        run_region_experiment(
            data, expected_sha256=hashlib.sha256(data).hexdigest(),
            output_dir=target, page_number=111,
        )
    assert not target.exists()


def test_headline_lines_psm7_dpi_variants(tmp_path):
    data = sample_pdf()
    received = []

    def mock_ocr(png, *, language, psm):
        assert png.startswith(b"\x89PNG")
        received.append((language, psm))
        return "AGP-V6800 Series\n"

    target = tmp_path / "headline-lines"
    report = run_region_experiment(
        data, expected_sha256=hashlib.sha256(data).hexdigest(),
        output_dir=target, page_number=1, regions=HEADLINE_LINES,
        dpi_options=(200, 300), psm_options=(7,), ocr=mock_ocr,
    )
    assert len(report["runs"]) == 6
    assert {row["region"] for row in report["runs"]} == {
        "title_line", "slogan_line1", "slogan_line2"
    }
    assert all(row["psm"] == 7 for row in report["runs"])
    assert {row["dpi"] for row in report["runs"]} == {200, 300}
    assert received == [("eng+deu", 7)] * 6
    assert len(list(target.glob("*.png"))) == 6
    assert len(list(target.glob("*.txt"))) == 6
    assert report["indexing_allowed"] is False
    assert report["quality_approved"] is False
    assert all(row["status"] == "not_evaluated" for row in report["runs"])


def test_psm7_rejected_outside_supported_set(tmp_path):
    data = sample_pdf()
    target = tmp_path / "invalid-psm"
    with pytest.raises(ValueError, match="PSM"):
        run_region_experiment(
            data, expected_sha256=hashlib.sha256(data).hexdigest(),
            output_dir=target, page_number=1,
            regions=HEADLINE_LINES, psm_options=(13,),
        )
    assert not target.exists()
