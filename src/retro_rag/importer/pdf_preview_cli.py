"""Read-only preview of exactly one WebDAV PDF through the PDF/OCR adapter.

No database connection, archiving, job updates or indexing is performed.
The downloaded original exists only in a short-lived private temporary directory.
"""

import argparse
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

from retro_rag.importer.pdf import DEFAULT_MAX_BYTES, read_pdf
from retro_rag.importer.webdav import WebDAV


def preview_pdf(
    client: WebDAV,
    source_key: str,
    expected_sha256: str,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
    max_pages: int = 1000,
    ocr_mode: str = "off",
    ocr_pages: set[int] | None = None,
    ocr_language: str = "eng+deu",
    ocr_dpi: int = 200,
) -> dict:
    """Fetch one identified source, verify bytes and generate a non-publishable contract."""
    if not source_key.strip():
        raise ValueError("Eine eindeutige Nextcloud-fileid ist erforderlich")
    if not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256):
        raise ValueError("Ein geprüfter SHA-256-Hexwert ist erforderlich")
    if max_bytes < 1 or max_bytes > DEFAULT_MAX_BYTES:
        raise ValueError("PDF-Größenlimit muss zwischen 1 und 50 MiB liegen")
    if max_pages < 1:
        raise ValueError("Seitenlimit muss positiv sein")
    if ocr_mode not in ("off", "auto"):
        raise ValueError("Ungültiger OCR-Modus")
    if ocr_pages and (ocr_mode != "auto" or min(ocr_pages) < 1):
        raise ValueError("OCR-Seiten benötigen auto-Modus und positive Seitennummern")

    matches = [f for f in client.list_files() if f.source_key == source_key]
    if len(matches) != 1:
        raise RuntimeError("Nextcloud-fileid fehlt oder ist nicht eindeutig")
    remote = matches[0]
    if not remote.name.lower().endswith(".pdf"):
        raise ValueError("Dieser Vorschaupfad akzeptiert ausschließlich PDFs")

    data = client.download(remote, max_bytes=max_bytes)
    sha = hashlib.sha256(data).hexdigest()
    if sha != expected_sha256.lower():
        raise RuntimeError("SHA-256 weicht von der geprüften Quelle ab: keine Extraktion")
    if not data.startswith(b"%PDF-"):
        raise ValueError("Ungültige PDF-Signatur")

    with tempfile.TemporaryDirectory(prefix="retro-v2-pdf-preview-") as folder:
        # Private temporary original, removed automatically even on parser/OCR failure.
        path = Path(folder) / "source.pdf"
        path.write_bytes(data)
        os.chmod(path, 0o600)
        contract = read_pdf(
            path,
            f"nextcloud:{remote.instance_id}:{remote.source_key}",
            max_bytes=max_bytes,
            max_pages=max_pages,
            ocr_mode=ocr_mode,
            ocr_pages=ocr_pages,
            ocr_language=ocr_language,
            ocr_dpi=ocr_dpi,
        )
    if contract.source.content_hash != sha:
        raise RuntimeError("PDF-Vertrag meldet abweichenden Original-Hash")
    if contract.indexing_allowed or contract.fact_proposals:
        raise RuntimeError("Vorschauvertrag darf weder indexierbar sein noch Fakten freigeben")
    return {
        "mode": "read_only_pdf_preview",
        "source_key": remote.source_key,
        "source_instance": remote.instance_id,
        "filename": remote.name,
        "sha256": sha,
        "page_count": contract.document.metadata["page_count"],
        "chunk_count": len(contract.chunks),
        "ocr_pages": contract.document.metadata["ocr_pages"],
        "ocr_failed_pages": contract.document.metadata["ocr_failed_pages"],
        "warnings": contract.warnings,
        "indexing_allowed": False,
        "fact_proposal_count": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Nur lesende Einzel-PDF/WebDAV/OCR-Vorschau")
    parser.add_argument("--source-key", required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    parser.add_argument("--max-pages", type=int, default=1000)
    parser.add_argument("--ocr-mode", choices=["off", "auto"], default="off")
    parser.add_argument("--ocr-page", type=int, action="append", default=[])
    parser.add_argument("--ocr-language", default="eng+deu")
    parser.add_argument("--ocr-dpi", type=int, default=200)
    args = parser.parse_args()

    required = (
        "RETRO_V2_WEBDAV_URL",
        "RETRO_V2_WEBDAV_USER",
        "RETRO_V2_WEBDAV_APP_PASSWORD",
        "RETRO_V2_NEXTCLOUD_INSTANCE_ID",
    )
    if any(not os.environ.get(name) for name in required):
        parser.error("WebDAV-URL, Benutzer, App-Passwort und Instanzkennung fehlen")
    # Deliberately does not read RETRO_V2_DATABASE_DSN or connect to PostgreSQL.
    client = WebDAV(
        os.environ["RETRO_V2_WEBDAV_URL"],
        os.environ["RETRO_V2_WEBDAV_USER"],
        os.environ["RETRO_V2_WEBDAV_APP_PASSWORD"],
        instance_id=os.environ["RETRO_V2_NEXTCLOUD_INSTANCE_ID"],
    )
    report = preview_pdf(
        client, args.source_key, args.expected_sha256,
        max_bytes=args.max_bytes, max_pages=args.max_pages,
        ocr_mode=args.ocr_mode, ocr_pages=set(args.ocr_page),
        ocr_language=args.ocr_language, ocr_dpi=args.ocr_dpi,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
