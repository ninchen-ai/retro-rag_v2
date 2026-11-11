"""Review-only index entry proposals from PDF column-order JSON.

Based on V1's conservative geometry/review principles. No network or DB.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import re
from pathlib import Path

CONTINUED = re.compile(r"\s*\(continued\)\s*$", re.IGNORECASE)
REFERENCE = re.compile(r"\b\d+(?:\.\d+)+(?:\s+Table\s+\d+(?:-\d+)?)?\b")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def ordered_columns(page: dict) -> dict[str, list[dict]]:
    if page.get("status") != "REVIEW_REQUIRED" or page.get("approved") is not False:
        raise ValueError("Nur unfreigegebene Spaltenvorschläge zulässig")
    if page.get("source_extractor") != "pymupdf_dict_lines_sort_false":
        raise ValueError("Unbekanntes Extraktionsprofil")
    source = page.get("source_lines")
    order = page.get("ordered_line_ids")
    unassigned = page.get("unassigned_line_ids")
    if not all(isinstance(item, list) for item in (source, order, unassigned)):
        raise ValueError("Quellzeilen/Lesereihenfolge fehlen")
    if page.get("source_line_count") != len(source):
        raise ValueError("Quellzeilenzahl widersprüchlich")
    ids = [line["line_id"] for line in source]
    if any(not isinstance(i, str) for i in ids) or len(ids) != len(set(ids)):
        raise ValueError("Fehlende oder doppelte Zeilen-IDs")
    if digest("".join(line["source_text"] for line in source).encode()) != page.get(
        "source_lines_sha256"
    ):
        raise ValueError("Quelltext-Prüfsumme stimmt nicht")
    if (len(order + unassigned) != len(ids)
            or len(set(order + unassigned)) != len(ids)
            or set(order + unassigned) != set(ids)):
        raise ValueError("Zeileninventar nicht eindeutig")
    by_id = {line["line_id"]: line for line in source}
    if "\n".join(by_id[i]["source_text"] for i in order) != page.get("proposed_text"):
        raise ValueError("Vorgeschlagener Text stimmt nicht zu Zeilen-IDs")
    if [c.get("name") for c in page.get("columns", [])] != ["left", "right"]:
        raise ValueError("Erwartet genau zwei Textspalten")
    result: dict[str, list[dict]] = {"left": [], "right": []}
    seen_right = False
    for line_id in order:
        line = by_id[line_id]
        side = line.get("column")
        if side not in result or (side == "left" and seen_right):
            raise ValueError("Ungültige Links-Rechts-Lesereihenfolge")
        if side == "right":
            seen_right = True
        bbox = line.get("bbox_pdf_points")
        if (not isinstance(bbox, list) or len(bbox) != 4
                or not all(type(x) in (int, float) for x in bbox)
                or not (bbox[0] < bbox[2] and bbox[1] < bbox[3])):
            raise ValueError("Ungültige Zeilenkoordinaten")
        result[side].append(line)
    if not all(result.values()):
        raise ValueError("Eine Textspalte ist leer")
    return result


def plausible_wrap(previous: dict, text: str) -> bool:
    """Deep indentation alone must NOT concatenate unrelated subentries."""
    prior = previous["text_parts"][-1].strip()
    if prior.endswith((",", ";", "-")):
        return True
    return (len(prior.split()) >= 3 and not REFERENCE.search(prior)
            and bool(REFERENCE.search(text)))


def propose_index_pages(pages: list[dict], source_hashes: list[str] | None = None) -> dict:
    if not pages:
        raise ValueError("Mindestens eine Seite erforderlich")
    pdf_hash = pages[0].get("pdf_sha256")
    numbers = [page.get("page") for page in pages]
    if (not isinstance(pdf_hash, str) or len(pdf_hash) != 64
            or any(page.get("pdf_sha256") != pdf_hash for page in pages)
            or any(type(n) is not int or n < 1 for n in numbers)
            or numbers != sorted(set(numbers))):
        raise ValueError("PDF-Identität oder Seitenreihenfolge ungültig")
    entries: list[dict] = []
    findings: list[dict] = []
    count = 0
    roots: dict[str, list[dict]] = {}
    last_main: dict | None = None
    last_entry: dict | None = None
    for page in pages:
        columns = ordered_columns(page)
        count += page["source_line_count"]
        for side in ("left", "right"):
            rows = columns[side]
            base_x = min(row["bbox_pdf_points"][0] for row in rows)
            for row in rows:
                text = row["source_text"].strip()
                indentation = row["bbox_pdf_points"][0] - base_x
                if indentation < -3:
                    kind = "uncertain"
                elif indentation <= 5:
                    kind = "headword"
                elif indentation <= 19:
                    kind = "subentry"
                elif last_entry is not None and plausible_wrap(last_entry, text):
                    kind = "wrap"
                else:
                    kind = "deep_subentry"
                if kind == "wrap":
                    last_entry["source_line_ids"].append(row["line_id"])
                    last_entry["text_parts"].append(row["source_text"])
                    last_entry["reference_candidates"] = sorted(set(
                        last_entry["reference_candidates"] + REFERENCE.findall(text)
                    ))
                    continue
                if kind in ("uncertain", "deep_subentry"):
                    findings.append({
                        "code": ("DEEP_INDENT_REVIEW" if kind == "deep_subentry"
                                 else "UNCLASSIFIED_INDENT"),
                        "page": page["page"], "line_id": row["line_id"],
                        "status": "REVIEW_REQUIRED",
                    })
                is_continued = bool(CONTINUED.search(text))
                canonical = CONTINUED.sub("", text).strip().casefold()
                continuation_of = None
                if kind == "headword":
                    if is_continued:
                        matches = [
                            entry for entry in roots.get(canonical, [])
                            if page["page"] - entry["page"] in (0, 1)
                        ]
                        if len(matches) == 1:
                            continuation_of = matches[0]["entry_id"]
                        else:
                            findings.append({
                                "code": "UNRESOLVED_CONTINUATION",
                                "page": page["page"], "line_id": row["line_id"],
                                "candidate_count": len(matches),
                                "status": "REVIEW_REQUIRED",
                            })
                    last_main = None
                parent_id = (
                    last_main["entry_id"]
                    if kind in ("subentry", "deep_subentry") and last_main else None
                )
                if kind in ("subentry", "deep_subentry") and parent_id is None:
                    findings.append({
                        "code": "ORPHAN_SUBENTRY", "page": page["page"],
                        "line_id": row["line_id"], "status": "REVIEW_REQUIRED",
                    })
                record = {
                    "entry_id": f"p{page['page']}-{row['line_id']}",
                    "page": page["page"], "column": side, "kind": kind,
                    "text_parts": [row["source_text"]],
                    "source_line_ids": [row["line_id"]],
                    "indent_pt": round(indentation, 2),
                    "parent_id": parent_id, "continuation_of": continuation_of,
                    "reference_candidates": REFERENCE.findall(text),
                    "status": "REVIEW_REQUIRED", "approved": False,
                }
                entries.append(record)
                last_entry = record
                if kind == "headword":
                    last_main = record
                    if not is_continued:
                        roots.setdefault(canonical, []).append(record)
    expected = {(page["page"], line_id) for page in pages
                for line_id in page["ordered_line_ids"]}
    actual = [(entry["page"], line_id) for entry in entries
              for line_id in entry["source_line_ids"]]
    if len(actual) != len(expected) or set(actual) != expected:
        raise ValueError("Indexeinträge enthalten fehlende/doppelte Quellzeilen")
    return {
        "schema_version": "pdf-index-proposals-v0.1",
        "pdf_sha256": pdf_hash, "source_json_sha256": source_hashes,
        "pages": numbers, "source_line_count": count,
        "indexed_line_count": len(expected), "entries": entries,
        "review_findings": findings, "status": "REVIEW_REQUIRED",
        "approved": False,
        "limitations": [
            "Indent-based roles are heuristics, not verified semantic entities",
            "Wraps and continuation links require review, including across pages",
            "Source JSON remains immutable; all original text lines are preserved",
            "Reference strings are candidates, not verified targets",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--page-json", type=Path, action="append", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists() or args.out.resolve() in [p.resolve() for p in args.page_json]:
        parser.error("Output exists or equals source: refusing overwrite")
    sources = [p.read_bytes() for p in args.page_json]
    result = propose_index_pages(
        [json.loads(data) for data in sources], [digest(data) for data in sources]
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print("Einträge:", dict(Counter(e["kind"] for e in result["entries"])))
    print("Review-Hinweise:", len(result["review_findings"]))
    print("Lokaler Vorschlagsbericht:", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
