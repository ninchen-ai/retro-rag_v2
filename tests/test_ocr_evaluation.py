"""Regressionsprüfungen der schreibfreien OCR-Qualitätsbewertung."""
import json

import pytest

from retro_rag.importer.ocr_evaluation import (
    edit_distance,
    evaluate,
    evaluate_folder,
    normalize,
)


def test_normalization_and_distance():
    assert normalize("A\n  B") == "A B"
    assert edit_distance(list("kitten"), list("sitting")) == 3


def test_perfect_match():
    result = evaluate("AGP-V6800 300MHz 32MB", "AGP-V6800 300MHz 32MB",
                      ["AGP-V6800", "300MHz", "32MB"])
    assert result["cer"] == 0
    assert result["wer"] == 0
    assert result["critical_term_recall"] == 1
    assert result["quality_approved"] is False


def test_wrong_hardware_number_is_detected():
    result = evaluate("440BX 32MB", "440ZX 32MB", ["440BX", "32MB"])
    assert result["cer"] > 0
    assert result["wer"] > 0
    assert result["critical_term_recall"] == 0.5


def test_insertions_can_exceed_one_hundred_percent():
    assert evaluate("a", "aaaaaaaaaa")["cer"] > 1


def test_empty_reference_is_rejected():
    with pytest.raises(ValueError, match="leer"):
        evaluate("   ", "foo")


def test_missing_reference_term_is_rejected():
    with pytest.raises(ValueError, match="nicht im Referenztext"):
        evaluate("440BX", "440BX", ["440ZX"])


def test_unreviewed_does_not_get_a_score(tmp_path):
    (tmp_path / "review.json").write_text(json.dumps({
        "review_status": "unreviewed", "case_id": "test",
        "pdf_sha256": "a" * 64, "pdf_page_1_based": 1,
    }), encoding="utf-8")
    (tmp_path / "reference.txt").write_text("440BX", encoding="utf-8")
    (tmp_path / "ocr.txt").write_text("440BX", encoding="utf-8")
    with pytest.raises(ValueError, match="reviewed"):
        evaluate_folder(tmp_path)


def test_reviewed_case_provenance(tmp_path):
    (tmp_path / "review.json").write_text(json.dumps({
        "review_status": "reviewed", "case_id": "test-p1",
        "pdf_sha256": "a" * 64, "pdf_page_1_based": 1,
        "reference": {"critical_terms": ["440BX"]},
    }), encoding="utf-8")
    (tmp_path / "reference.txt").write_text("440BX", encoding="utf-8")
    (tmp_path / "ocr.txt").write_text("440ZX", encoding="utf-8")
    result = evaluate_folder(tmp_path)
    assert result["status"] == "evaluated_not_approved"
    assert result["pdf_page_1_based"] == 1
    assert result["critical_term_recall"] == 0
