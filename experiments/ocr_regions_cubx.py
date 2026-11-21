"""Read-only, non-publishing OCR crop comparison of a SHA-verified PDF page.

Keep region coordinates fixed while comparing 200/300 DPI and Tesseract
PSM 6/11. This is an experiment, not part of the import worker.
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pymupdf

MAX_PDF_BYTES = 50 * 1024 * 1024


@dataclass(frozen=True)
class Region:
    name: str
    left: float
    top: float
    right: float
    bottom: float


# Relative PDF-page coordinates based on CUBX page 111; visually verify crops.
REGIONS = (
    Region("headline", 0.10, 0.02, 0.94, 0.18),
    Region("specifications", 0.06, 0.67, 0.68, 0.94),
    Region("badges", 0.08, 0.19, 0.23, 0.52),
)
DPI_OPTIONS = (200, 300)
PSM_OPTIONS = (6, 11)


def render_region(page: pymupdf.Page, region: Region, dpi: int) -> bytes:
    """Render the actual PDF at DPI, never upscale an old page.png."""
    if not (0 <= region.left < region.right <= 1
            and 0 <= region.top < region.bottom <= 1):
        raise ValueError("Ungültige relative Seitenkoordinaten")
    if not 100 <= dpi <= 300:
        raise ValueError("DPI außerhalb des erlaubten Bereichs")
    rect = page.rect
    clip = pymupdf.Rect(
        rect.x0 + rect.width * region.left,
        rect.y0 + rect.height * region.top,
        rect.x0 + rect.width * region.right,
        rect.y0 + rect.height * region.bottom,
    )
    return page.get_pixmap(dpi=dpi, clip=clip, alpha=False).tobytes("png")


def tesseract_ocr(png: bytes, *, language: str, psm: int) -> str:
    """Call Tesseract via stdin/stdout; no intermediate OCR source files."""
    if psm not in PSM_OPTIONS:
        raise ValueError("Nicht unterstützter PSM-Modus")
    result = subprocess.run(
        ["tesseract", "stdin", "stdout", "-l", language, "--psm", str(psm)],
        input=png, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=True, timeout=120,
    )
    return result.stdout.decode("utf-8", errors="replace")


def run_region_experiment(
    pdf_bytes: bytes,
    *,
    expected_sha256: str,
    output_dir: Path,
    page_number: int = 111,
    language: str = "eng+deu",
    regions: tuple[Region, ...] = REGIONS,
    dpi_options: tuple[int, ...] = DPI_OPTIONS,
    psm_options: tuple[int, ...] = PSM_OPTIONS,
    ocr: Callable[..., str] = tesseract_ocr,
) -> dict:
    """Create only local unreviewed candidates; never overwrite outputs."""
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise ValueError("SHA-256 muss ein 64-stelliger Kleinbuchstaben-Hexwert sein")
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    if digest != expected_sha256:
        raise ValueError("Original-PDF stimmt nicht mit dem erwarteten SHA-256 überein")
    if len(pdf_bytes) > MAX_PDF_BYTES or not pdf_bytes.startswith(b"%PDF-"):
        raise ValueError("Ungültige PDF-Datei oder PDF-Größenlimit überschritten")
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError("Zielverzeichnis existiert bereits: kein Überschreiben")
    if not regions or not dpi_options or not psm_options:
        raise ValueError("Mindestens eine Region, DPI-Stufe und PSM-Variante erforderlich")
    if not language or any(char.isspace() for char in language):
        raise ValueError("Ungültiges OCR-Sprachpaket")
    if any(psm not in PSM_OPTIONS for psm in psm_options):
        raise ValueError("Unbekannter PSM-Modus")
    if any(not 100 <= dpi <= 300 for dpi in dpi_options):
        raise ValueError("Ungültige DPI-Stufe")

    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        if doc.needs_pass or not 1 <= page_number <= len(doc):
            raise ValueError("Geschütztes PDF oder Seite außerhalb des Dokuments")
        page = doc[page_number - 1]
        output_dir.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with tempfile.TemporaryDirectory(prefix=".ocr-regions-", dir=output_dir.parent) as tmp:
            scratch = Path(tmp)
            report = {
                "mode": "read_only_pdf_region_ocr_experiment",
                "pdf_sha256": digest,
                "pdf_page_1_based": page_number,
                "ocr_language": language,
                "reference_status": "unreviewed",
                "quality_approved": False,
                "indexing_allowed": False,
                "regions": [{
                    "name": region.name,
                    "fractions": [region.left, region.top, region.right, region.bottom],
                } for region in regions],
                "runs": [],
            }
            for region in regions:
                if not re.fullmatch(r"[a-z][a-z0-9_-]{0,40}", region.name):
                    raise ValueError("Ungültiger Regionsname")
                if not (0 <= region.left < region.right <= 1
                        and 0 <= region.top < region.bottom <= 1):
                    raise ValueError("Ungültige Regionskoordinaten")
                for dpi in dpi_options:
                    png = render_region(page, region, dpi)
                    image_name = f"{region.name}-{dpi}dpi.png"
                    (scratch / image_name).write_bytes(png)
                    for psm in psm_options:
                        candidate = ocr(png, language=language, psm=psm)
                        candidate_name = f"{region.name}-{dpi}dpi-psm{psm}.txt"
                        (scratch / candidate_name).write_text(candidate, encoding="utf-8")
                        report["runs"].append({
                            "region": region.name, "dpi": dpi, "psm": psm,
                            "image": image_name, "candidate": candidate_name,
                            "characters": len(candidate),
                            "words": len(candidate.split()),
                            "sha256": hashlib.sha256(candidate.encode("utf-8")).hexdigest(),
                            "status": "not_evaluated",
                        })
            (scratch / "report.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
            )
            # Does not generate reference.txt or change review.json.
            scratch.rename(output_dir)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Lokaler Bereichs-OCR-Vergleich ohne DB/Index")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-key", default="172")
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--page", type=int, default=111)
    parser.add_argument("--language", default="eng+deu")
    parser.add_argument(
        "--url",
        default=os.environ.get("RETRO_V2_WEBDAV_URL")
        or os.environ.get("RETRO_V2_NEXTCLOUD_URL"),
    )
    parser.add_argument(
        "--user",
        default=os.environ.get("RETRO_V2_WEBDAV_USER")
        or os.environ.get("RETRO_V2_NEXTCLOUD_USER"),
    )
    parser.add_argument(
        "--instance-id", default=os.environ.get("RETRO_V2_NEXTCLOUD_INSTANCE_ID"),
    )
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        parser.error("Ausgabeverzeichnis existiert bereits: nichts überschreiben")
    if not all((args.url, args.user, args.instance_id)):
        parser.error("WebDAV-URL, Benutzer oder Nextcloud-Instanzkennung fehlt")

    from retro_rag.importer.webdav import WebDAV

    password = getpass.getpass("Nextcloud-App-Passwort: ")
    client = WebDAV(args.url, args.user, password, instance_id=args.instance_id)
    files = [file for file in client.list_files() if file.source_key == args.source_key]
    if len(files) != 1 or not files[0].name.lower().endswith(".pdf"):
        raise SystemExit("Eindeutige PDF-Quellkennung fehlt")
    data = client.download(files[0], max_bytes=MAX_PDF_BYTES)
    os.umask(0o077)
    report = run_region_experiment(
        data, expected_sha256=args.expected_sha256, output_dir=args.output,
        page_number=args.page, language=args.language,
    )
    print(json.dumps({
        "output": str(args.output),
        "pdf_sha256": report["pdf_sha256"],
        "page": report["pdf_page_1_based"],
        "runs": len(report["runs"]),
        "status": "not_evaluated",
        "indexing_allowed": False,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
