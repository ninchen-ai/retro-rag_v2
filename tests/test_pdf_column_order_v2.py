"""Unit-Tests der schreibfreien Spaltenlesereihenfolge mit echten PyMuPDF-Zeilen."""
import hashlib
import importlib.util
from pathlib import Path

import pymupdf
import pytest
from PIL import Image

SCRIPT = Path(__file__).resolve().parents[1] / "experiments" / "pdf_column_order_v2.py"
SPEC = importlib.util.spec_from_file_location("pdf_column_order_v2", SCRIPT)
columns = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(columns)


def sample(tmp_path, *, both=True):
    doc = pymupdf.open()
    page = doc.new_page(width=600, height=800)
    page.insert_text((50, 150), "Left first paragraph")
    page.insert_text((350, 155), "Right first paragraph")
    page.insert_text((50, 250), "Left second paragraph")
    page.insert_text((350, 255), "Right second paragraph")
    page.insert_text((240, 45), "Header")
    image = tmp_path / "page.png"
    page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False).save(image)
    data = doc.tobytes()
    doc.close()
    digest = hashlib.sha256(image.read_bytes()).hexdigest()
    detections = [{
        "class_name": "plain text", "confidence": 0.95,
        "bbox_pixels": [80, 240, 500, 600],
    }]
    if both:
        detections.append({
            "class_name": "plain text", "confidence": 0.94,
            "bbox_pixels": [680, 240, 1100, 600],
        })
    run = {
        "image_width": 1200, "image_height": 1600,
        "image_sha256": digest, "detections": detections,
    }
    return data, image, run


def test_pixel_to_pdf_geometry():
    assert columns.pixel_box_to_pdf(
        [200, 400, 600, 800], 600, 800, 1200, 1600
    ) == [100, 200, 300, 400]
    with pytest.raises(ValueError, match="außerhalb"):
        columns.pixel_box_to_pdf([10, 20, 5000, 50], 600, 800, 1200, 1600)


def test_column_proposal_preserves_all_source_lines(tmp_path):
    data, image, run = sample(tmp_path)
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        result = columns.propose_page(
            doc[0], image, run, pdf_sha256=columns.sha256(data), page_number=1
        )
    proposed = result["proposed_text"]
    assert (proposed.index("Left first") < proposed.index("Left second")
            < proposed.index("Right first") < proposed.index("Right second"))
    assert len(result["unassigned_line_ids"]) == 1
    assert "Header" in "".join(row["source_text"] for row in result["source_lines"])
    assert (len(result["ordered_line_ids"]) + len(result["unassigned_line_ids"])
            == result["source_line_count"])
    assert result["approved"] is False and result["status"] == "REVIEW_REQUIRED"


def test_no_two_columns_fails_closed(tmp_path):
    data, image, run = sample(tmp_path, both=False)
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        with pytest.raises(ValueError, match="Zwei getrennte"):
            columns.propose_page(
                doc[0], image, run, pdf_sha256=columns.sha256(data), page_number=1
            )


def test_mismatched_image_sha_fails_closed(tmp_path):
    data, image, run = sample(tmp_path)
    run["image_sha256"] = "a" * 64
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        with pytest.raises(ValueError, match="Bild-SHA"):
            columns.propose_page(
                doc[0], image, run, pdf_sha256=columns.sha256(data), page_number=1
            )


def test_rotation_is_not_silently_transformed(tmp_path):
    data, image, run = sample(tmp_path)
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        doc[0].set_rotation(90)
        with pytest.raises(ValueError, match="Rotation"):
            columns.propose_page(
                doc[0], image, run, pdf_sha256=columns.sha256(data), page_number=1
            )


def test_run_must_be_unique_and_unapproved():
    raw = {"mode": "read_only_pdf_layout_proposals", "completed": True,
           "approved": False, "runs": [
               {"case_id": "x", "status": "ok", "review_status": "proposed"},
               {"case_id": "x", "status": "ok", "review_status": "proposed"},
           ]}
    with pytest.raises(ValueError, match="eindeutiger"):
        columns.resolve_run(raw, "x")
    raw["completed"] = False
    with pytest.raises(ValueError, match="nicht vollständig"):
        columns.resolve_run(raw, "x")
