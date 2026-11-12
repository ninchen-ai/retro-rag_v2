"""Deterministische OCR-Evaluation gegen manuell verifizierte Referenztexte.

Nur lokale Dateien; keine Nextcloud-, Datenbank- oder Indexschreibzugriffe.
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from datetime import UTC, datetime
from pathlib import Path


def normalize(text: str) -> str:
    """Unicode vereinheitlichen und Whitespace-Unterschiede ausblenden."""
    return " ".join(unicodedata.normalize("NFC", text).split())


def edit_distance(reference: list[str], candidate: list[str]) -> int:
    """Levenshtein-Distanz; Speicher O(min(n, m)), ohne weitere Dependencies."""
    if len(reference) < len(candidate):
        reference, candidate = candidate, reference
    previous = list(range(len(candidate) + 1))
    for i, item in enumerate(reference, 1):
        current = [i]
        for j, other in enumerate(candidate, 1):
            current.append(min(
                previous[j] + 1,
                current[-1] + 1,
                previous[j - 1] + (item != other),
            ))
        previous = current
    return previous[-1]


def evaluate(reference: str, candidate: str, critical_terms: list[str] | None = None) -> dict:
    """CER/WER mit klar ausgewiesenen Nennern; niemals unbewertet als OK markieren."""
    ref = normalize(reference)
    hyp = normalize(candidate)
    if not ref:
        raise ValueError("Referenztext ist leer: CER/WER nicht definiert")
    ref_words = ref.split()
    hyp_words = hyp.split()
    terms = critical_terms or []
    if any(not isinstance(term, str) or not normalize(term) for term in terms):
        raise ValueError("Kritische Begriffe müssen nichtleere Zeichenketten sein")
    # Ganze Tokenfolgen, damit etwa '440BX' nicht in '440BXL' als Treffer gilt.
    def occurrences(text: str, phrase: str) -> int:
        pattern = r"(?<!\w)" + re.escape(normalize(phrase)) + r"(?!\w)"
        return len(re.findall(pattern, text, flags=re.IGNORECASE))

    details = []
    for term in terms:
        expected = occurrences(ref, term)
        if expected == 0:
            raise ValueError(f"Kritischer Begriff nicht im Referenztext: {term}")
        found = occurrences(hyp, term)
        details.append({
            "term": term, "expected": expected, "found": found,
            "matched": min(expected, found),
        })
    reference_hits = sum(item["expected"] for item in details)
    matched_hits = sum(item["matched"] for item in details)
    char_edits = edit_distance(list(ref), list(hyp))
    word_edits = edit_distance(ref_words, hyp_words)
    return {
        "reference_characters": len(ref),
        "candidate_characters": len(hyp),
        "character_edits": char_edits,
        "cer": round(char_edits / len(ref), 6),
        "reference_words": len(ref_words),
        "candidate_words": len(hyp_words),
        "word_edits": word_edits,
        "wer": round(word_edits / len(ref_words), 6),
        "critical_terms_expected": reference_hits,
        "critical_terms_matched": matched_hits,
        "critical_term_recall": (
            round(matched_hits / reference_hits, 6) if reference_hits else None
        ),
        "critical_terms": details,
        "quality_approved": False,
    }


def evaluate_folder(folder: Path) -> dict:
    """Prüft ein Goldstandard-Prüfpaket mit review.json, reference.txt und ocr.txt."""
    review = json.loads((folder / "review.json").read_text(encoding="utf-8"))
    if review.get("review_status") != "reviewed":
        raise ValueError("review_status muss 'reviewed' sein")
    if not review.get("pdf_sha256") or not review.get("pdf_page_1_based"):
        raise ValueError("PDF-Provenienz fehlt")
    reference = (folder / "reference.txt").read_text(encoding="utf-8")
    candidate = (folder / "ocr.txt").read_text(encoding="utf-8")
    terms = review.get("reference", {}).get("critical_terms", [])
    if not isinstance(terms, list):
        raise ValueError("critical_terms muss eine Liste sein")
    result = evaluate(reference, candidate, terms)
    result.update({
        "case_id": review["case_id"],
        "pdf_sha256": review["pdf_sha256"],
        "pdf_page_1_based": review["pdf_page_1_based"],
        "status": "evaluated_not_approved",
    })
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Lokale, schreibfreie OCR-Qualitätsmessung")
    parser.add_argument("--goldstandard-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if not args.goldstandard_dir.is_dir():
        parser.error("Goldstandard-Verzeichnis fehlt")
    cases = []
    for review_file in sorted(args.goldstandard_dir.glob("*/review.json")):
        folder = review_file.parent
        try:
            cases.append(evaluate_folder(folder))
        except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
            cases.append({
                "case_directory": folder.name,
                "status": "not_evaluated",
                "reason": f"{type(exc).__name__}: {exc}",
            })
    report = {
        "created_at": datetime.now(UTC).isoformat(),
        "mode": "local_ocr_evaluation_no_db_writes",
        "cases_total": len(cases),
        "cases_evaluated": sum(c["status"] == "evaluated_not_approved" for c in cases),
        "cases": cases,
    }
    if not cases:
        parser.error("Keine review.json-Prüfpakete gefunden")
    if args.report.exists():
        parser.error("Bericht existiert bereits; kein Überschreiben")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    print(f"Bewertet: {report['cases_evaluated']}/{report['cases_total']}; {args.report}")
    return 0 if report["cases_evaluated"] == report["cases_total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
