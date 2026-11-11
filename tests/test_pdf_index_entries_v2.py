"""Synthetic regression tests for review-only PDF index entry proposals."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "experiments" / "pdf_index_entries_v2.py"
SPEC = importlib.util.spec_from_file_location("pdf_index_entries_v2", SCRIPT)
index = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(index)


def make_page(number, left, right, *, pdf_hash="a" * 64):
    lines = []
    order = []
    for side, records, x0, block in (
        ("left", left, 72, 0), ("right", right, 324, 1)
    ):
        for i, (text, indent) in enumerate(records):
            line_id = f"{block}:{i}"
            lines.append({
                "line_id": line_id, "source_text": text, "column": side,
                "bbox_pdf_points": [x0 + indent, 75 + 20 * i,
                                    x0 + indent + 110, 87 + 20 * i],
            })
            order.append(line_id)
    return {
        "status": "REVIEW_REQUIRED", "approved": False,
        "page": number, "pdf_sha256": pdf_hash,
        "source_extractor": "pymupdf_dict_lines_sort_false",
        "source_lines": lines, "source_line_count": len(lines),
        "source_lines_sha256": hashlib.sha256(
            "".join(line["source_text"] for line in lines).encode()
        ).hexdigest(),
        "columns": [{"name": "left"}, {"name": "right"}],
        "ordered_line_ids": order, "unassigned_line_ids": [],
        "proposed_text": "\n".join(line["source_text"] for line in lines),
    }


def example_page():
    return make_page(606, [
        ("ClearHubFeature() request", 0),
        ("clock model", 0),
        ("clock encoding scheme in electrical", 11),
        ("specifications overview, 4.2.1", 39),
        ("clock tolerance, 11.7.1.3", 11),
    ], [
        ("clock model (continued)", 0),
        ("receive clock, 11.7.1.2, 11.7.1.3", 11),
        ("sample clock, 5.12.2", 11),
    ])


def test_continuation_across_columns_and_wrap_evidence():
    page = example_page()
    snapshot = copy.deepcopy(page)
    report = index.propose_index_pages([page])
    assert page == snapshot
    assert report["approved"] is False
    assert report["indexed_line_count"] == 8
    assert report["source_line_count"] == 8
    root = next(e for e in report["entries"] if e["text_parts"] == ["clock model"])
    continued = next(e for e in report["entries"]
                     if e["text_parts"] == ["clock model (continued)"])
    assert continued["continuation_of"] == root["entry_id"]
    assert any(e["parent_id"] == continued["entry_id"] for e in report["entries"])
    assert any(e["source_line_ids"] == ["0:2", "0:3"] for e in report["entries"])
    assert all(e["status"] == "REVIEW_REQUIRED" for e in report["entries"])


def test_adjacent_page_continuation_stays_review_required():
    a = make_page(610, [("signal integrity", 0)], [("unrelated", 0)])
    b = make_page(611, [("signal integrity (continued)", 0)],
                  [("component, 7.1.2", 11)])
    out = index.propose_index_pages([a, b])
    entry = next(e for e in out["entries"]
                 if e["text_parts"] == ["signal integrity (continued)"])
    assert entry["continuation_of"] == "p610-0:0"
    assert entry["approved"] is False


def test_nonadjacent_page_cannot_link_continuation():
    a = make_page(610, [("signal integrity", 0)], [("unrelated", 0)])
    b = make_page(613, [("signal integrity (continued)", 0)],
                  [("component, 7.1.2", 11)])
    out = index.propose_index_pages([a, b])
    entry = next(e for e in out["entries"]
                 if e["text_parts"] == ["signal integrity (continued)"])
    assert entry["continuation_of"] is None
    assert any(f["code"] == "UNRESOLVED_CONTINUATION" for f in out["review_findings"])


def test_unknown_continuation_has_review_finding():
    page = make_page(606, [("missing (continued)", 0)], [("other", 0)])
    result = index.propose_index_pages([page])
    assert result["entries"][0]["continuation_of"] is None
    assert result["review_findings"][0]["code"] == "UNRESOLVED_CONTINUATION"


def test_deep_indentation_is_not_blindly_merged():
    page = make_page(601, [("assignment", 0), ("after removal, 4.6.3", 39)],
                     [("other", 0)])
    result = index.propose_index_pages([page])
    assert len(result["entries"]) == 3
    assert result["entries"][1]["kind"] == "deep_subentry"
    assert any(f["code"] == "DEEP_INDENT_REVIEW" for f in result["review_findings"])


def test_modified_source_text_is_rejected():
    page = example_page()
    page["source_lines"][0]["source_text"] += " changed"
    with pytest.raises(ValueError, match="Prüfsumme"):
        index.propose_index_pages([page])


def test_page_order_and_duplicate_pages_rejected():
    a = example_page()
    b = make_page(607, [("next", 0)], [("other", 0)])
    with pytest.raises(ValueError, match="Seitenreihenfolge"):
        index.propose_index_pages([b, a])
    with pytest.raises(ValueError, match="Seitenreihenfolge"):
        index.propose_index_pages([a, a])


def test_different_pdf_or_approved_input_rejected():
    a = example_page()
    b = make_page(607, [("next", 0)], [("other", 0)], pdf_hash="b" * 64)
    with pytest.raises(ValueError, match="PDF-Identität"):
        index.propose_index_pages([a, b])
    a["approved"] = True
    with pytest.raises(ValueError, match="unfreigegebene"):
        index.propose_index_pages([a])


def test_duplicate_source_id_fails_closed():
    page = example_page()
    page["ordered_line_ids"][0] = page["ordered_line_ids"][1]
    with pytest.raises(ValueError, match="eindeutig"):
        index.propose_index_pages([page])


def test_references_are_not_verified_targets():
    out = index.propose_index_pages([example_page()])
    assert out["status"] == "REVIEW_REQUIRED"
    assert any(e["reference_candidates"] for e in out["entries"])
    assert "not verified" in " ".join(out["limitations"])


def test_reference_regex():
    assert index.REFERENCE.findall("controller, 11.24.2, 11.24.2.1") == [
        "11.24.2", "11.24.2.1"
    ]


def test_cli_refuses_overwrite(tmp_path, monkeypatch):
    src = tmp_path / "page.json"
    src.write_text(json.dumps(example_page()), encoding="utf-8")
    dest = tmp_path / "index.json"
    monkeypatch.setattr(sys, "argv", [
        "index-proposals", "--page-json", str(src), "--out", str(dest),
    ])
    assert index.main() == 0
    out = json.loads(dest.read_text(encoding="utf-8"))
    assert out["approved"] is False
    assert out["source_json_sha256"] == [hashlib.sha256(src.read_bytes()).hexdigest()]
    with pytest.raises(SystemExit):
        index.main()
