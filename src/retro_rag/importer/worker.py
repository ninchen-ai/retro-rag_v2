"""Restartable, fail-closed extraction worker for already staged V2 documents.

One invocation processes at most one job. A systemd timer can invoke it again.
No WebDAV discovery, new source approval, embedding or version activation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import uuid
from pathlib import Path
from urllib.parse import unquote, urlparse

import psycopg

from retro_rag.importer.markdown import read_markdown
from retro_rag.importer.pdf import read_pdf

LEASE_MINUTES = 60


def verified_original(uri: str, root: Path, expected_hash: str) -> Path:
    """Verify the archived original before reuse; reject arbitrary paths/links."""
    parsed = urlparse(uri)
    if parsed.scheme != "file" or parsed.netloc not in ("", "localhost"):
        raise ValueError("Originalarchiv benötigt eine lokale file:-URI")
    path = Path(unquote(parsed.path))
    if path.is_symlink() or not path.is_file():
        raise ValueError("Originaldatei fehlt oder ist ein Symlink")
    resolved = path.resolve(strict=True)
    root_resolved = root.resolve(strict=True)
    if not resolved.is_relative_to(root_resolved):
        raise ValueError("Original liegt außerhalb des freigegebenen Archivs")
    if path.suffix.lower() not in (".pdf", ".md"):
        raise ValueError("Originalformat nicht unterstützt")
    if not (root_resolved / expected_hash[:2]).is_dir():
        raise ValueError("Archiv-Unterverzeichnis fehlt")
    if resolved.parent != root_resolved / expected_hash[:2]:
        raise ValueError("Unzulässiges Archiv-Unterverzeichnis")
    h = hashlib.sha256()
    with resolved.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    if h.hexdigest() != expected_hash:
        raise ValueError("Archivinhalt weicht vom dokumentierten SHA-256 ab")
    return resolved


def require_test_gate(cur) -> None:
    cur.execute("SELECT current_database()")
    if cur.fetchone()[0] != "retro_rag_v2_test":
        raise RuntimeError("Worker ausschließlich auf retro_rag_v2_test erlaubt")
    cur.execute("SELECT rag_v2.assert_import_write_gate()")


def claim_job(conn: psycopg.Connection, owner: str):
    """Claim eligible work in a short transaction, including crashed leases."""
    with conn.transaction(), conn.cursor() as cur:
        require_test_gate(cur)
        cur.execute(
            """SELECT j.id, j.document_version_id, v.content_hash, v.archive_uri,
                      v.source_filename, j.attempts, j.max_attempts
                 FROM rag_v2.processing_job j
                 JOIN rag_v2.document_version v ON v.id=j.document_version_id
                 WHERE j.job_type='document_import'
                   AND j.status IN ('pending','failed','running')
                   AND (j.status<>'running' OR j.lease_until < now())
                   AND j.attempts < j.max_attempts
                   AND v.state IS NULL
                   AND v.processing_state IN ('discovered','processing')
                   AND NOT EXISTS (
                       SELECT 1 FROM rag_v2.review_batch b
                       JOIN rag_v2.review_item i ON i.review_batch_id=b.id
                       WHERE b.document_version_id=v.id
                         AND i.item_kind='document_identity'
                         AND i.status IN ('proposed','deferred')
                   )
                 ORDER BY j.created_at, j.id
                 FOR UPDATE OF j SKIP LOCKED LIMIT 1"""
        )
        row = cur.fetchone()
        if row is None:
            return None
        job_id, version_id, expected_hash, archive_uri, filename, _, _ = row
        cur.execute(
            """UPDATE rag_v2.processing_job
               SET status='running', attempts=attempts+1, lease_owner=%s,
                   lease_until=now() + (%s * interval '1 minute'),
                   last_error=NULL, updated_at=now()
               WHERE id=%s""",
            (owner, LEASE_MINUTES, job_id),
        )
        return job_id, version_id, expected_hash, archive_uri, filename


def finish_job(conn, job, owner: str, contract) -> None:
    job_id, version_id, expected_hash, _, _ = job
    if contract.source.content_hash != expected_hash:
        raise ValueError("Extraktionsvertrag weicht vom Originalhash ab")
    if contract.indexing_allowed or contract.fact_proposals:
        raise ValueError("Automatische Index-/Faktenfreigabe ist verboten")
    if not contract.chunks or (contract.source.kind == "pdf" and contract.warnings):
        raise ValueError("Extraktion erfordert Prüfung: " + "; ".join(contract.warnings or [
            "Keine Text-Chunks vorhanden"
        ]))
    with conn.transaction(), conn.cursor() as cur:
        require_test_gate(cur)
        cur.execute(
            """SELECT 1 FROM rag_v2.processing_job
               WHERE id=%s AND status='running' AND lease_owner=%s
                 AND lease_until > now() FOR UPDATE""", (job_id, owner),
        )
        if cur.fetchone() is None:
            raise RuntimeError("Lease verloren, kein Commit")
        cur.execute(
            """SELECT 1 FROM rag_v2.document_version
               WHERE id=%s AND content_hash=%s AND state IS NULL FOR UPDATE""",
            (version_id, expected_hash),
        )
        if cur.fetchone() is None:
            raise RuntimeError("Dokumentversion verändert")
        cur.execute(
            """SELECT status FROM rag_v2.processing_step
               WHERE processing_job_id=%s AND step_name='content_extracted'
               FOR UPDATE""", (job_id,),
        )
        existing = cur.fetchone()
        if existing and existing[0] == 'completed':
            # Completed steps and their chunks are never overwritten.
            cur.execute(
                """UPDATE rag_v2.processing_job SET status='completed',
                   lease_owner=NULL, lease_until=NULL, updated_at=now(),
                   completed_at=now() WHERE id=%s""", (job_id,),
            )
            return
        if existing is not None:
            raise RuntimeError("Unvollständiger Extraktionsschritt: manuelle Klärung")
        cur.execute(
            """SELECT 1 FROM rag_v2.chunk WHERE document_version_id=%s LIMIT 1""",
            (version_id,),
        )
        if cur.fetchone():
            raise RuntimeError("Bereits vorhandene Chunks: manuelle Klärung statt Überschreiben")
        cur.execute(
            """INSERT INTO rag_v2.processing_step
               (processing_job_id,step_name,status,input_hash,attempts)
               VALUES (%s,'content_extracted','running',%s,1) RETURNING id""",
            (job_id, expected_hash),
        )
        step_id = cur.fetchone()[0]
        for chunk in contract.chunks:
            cur.execute(
                """INSERT INTO rag_v2.chunk
                   (document_version_id,sequence_no,content,content_hash,
                    page_from,page_to,section_path,source_locator)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb)""",
                (version_id, chunk.ordinal, chunk.text, chunk.chunk_hash,
                 chunk.page, chunk.page, chunk.heading_path,
                 json.dumps({"page": chunk.page, "origin": "import_worker"})),
            )
        # Durable artifact points at the transactionally persisted chunks.
        summary = {
            "contract_version": contract.contract_version,
            "chunks": len(contract.chunks),
            "metadata": contract.document.metadata,
            "indexing_allowed": False,
            "warnings": contract.warnings,
        }
        summary_hash = hashlib.sha256(json.dumps(summary, sort_keys=True, default=str).encode()).hexdigest()
        cur.execute(
            """INSERT INTO rag_v2.processing_artifact
               (processing_step_id,artifact_kind,artifact_uri,content_hash)
               VALUES (%s,'extraction_summary',%s,%s)""",
            (step_id, "db:rag_v2.chunk?version=" + str(version_id), summary_hash),
        )
        cur.execute(
            """UPDATE rag_v2.processing_step SET status='completed',
               completed_at=now() WHERE id=%s""", (step_id,),
        )
        # No embeddings yet. Do not mark as indexed or activate a version.
        cur.execute(
            """UPDATE rag_v2.document_version SET processing_state='processing'
               WHERE id=%s AND state IS NULL""", (version_id,),
        )
        cur.execute(
            """UPDATE rag_v2.processing_job
               SET status='completed', lease_owner=NULL, lease_until=NULL,
                   updated_at=now(), completed_at=now()
               WHERE id=%s""", (job_id,),
        )


def fail_job(conn, job_id, owner: str, error: Exception) -> None:
    """Keep other documents running; never print secrets or source content."""
    message = f"{type(error).__name__}: {str(error)[:300]}"
    with conn.transaction(), conn.cursor() as cur:
        require_test_gate(cur)
        cur.execute(
            """UPDATE rag_v2.processing_job SET status='failed', last_error=%s,
               lease_owner=NULL, lease_until=NULL, updated_at=now()
               WHERE id=%s AND status='running' AND lease_owner=%s
                 AND lease_until > now()""",
            (message, job_id, owner),
        )


def process_one(conn, root: Path, owner: str, *, ocr_mode: str = "off") -> bool:
    job = claim_job(conn, owner)
    if job is None:
        return False
    job_id, version_id, expected_hash, uri, filename = job
    try:
        if not uri or not filename:
            raise ValueError("Archiv-URI oder Dateiname fehlt")
        path = verified_original(uri, root, expected_hash)
        if path.suffix.lower() != Path(filename).suffix.lower():
            raise ValueError("Archivformat und Quelldateiname unterscheiden sich")
        source_id = f"version:{version_id}"
        if path.suffix.lower() == ".pdf":
            contract = read_pdf(path, source_id, ocr_mode=ocr_mode)
        else:
            contract = read_markdown(path, source_id)
        finish_job(conn, job, owner, contract)
        return True
    except Exception as exc:
        fail_job(conn, job_id, owner, exc)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="V2-Importworker (ein Job pro Aufruf)")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--archive-root", type=Path, required=True)
    parser.add_argument("--ocr-mode", choices=("off", "auto"), default="off")
    args = parser.parse_args()
    if not args.apply:
        print("Dry-run: Kein Job übernommen, keine Änderungen. --apply erforderlich.")
        return
    dsn = os.getenv("RETRO_V2_DATABASE_DSN")
    if not dsn:
        parser.error("RETRO_V2_DATABASE_DSN fehlt")
    owner = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex}"
    with psycopg.connect(dsn, autocommit=True) as conn:
        processed = process_one(conn, args.archive_root, owner, ocr_mode=args.ocr_mode)
    print("Extraktionsjob verarbeitet (nicht indexiert)." if processed else "Kein Job verfügbar.")


if __name__ == "__main__":
    main()
