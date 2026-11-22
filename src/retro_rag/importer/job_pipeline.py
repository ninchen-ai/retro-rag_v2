"""Kontrollierte Verbindung eines archivierten Importjobs mit dem Importvertrag.

Kein Poller, kein WebDAV-Aufruf, keine Embeddings und keine Aktivierung.
Die Extraktion ist lesend; persist_contract verlangt eine vorhandene
Transaktion und eine von PostgreSQL bestätigte Import-Schreibfreigabe.
"""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit
from uuid import UUID

import psycopg
from psycopg.pq import TransactionStatus

from retro_rag.importer.contract import ImportContract
from retro_rag.importer.markdown import read_markdown
from retro_rag.importer.pdf import read_pdf


@dataclass(frozen=True)
class PreparedJob:
    job_id: UUID
    version_id: UUID
    original_path: Path
    contract: ImportContract


def resolve_archived_original(archive_uri: str, archive_root: Path) -> Path:
    """Nur echte, unter dem Archiv-Mount liegende file://-Originale öffnen."""
    parts = urlsplit(archive_uri)
    if parts.scheme != "file" or parts.netloc not in ("", "localhost"):
        raise ValueError("Original muss eine lokale file://-Archivkopie sein")
    if parts.query or parts.fragment:
        raise ValueError("Archiv-URI darf keine Query oder Fragmente enthalten")
    root = archive_root.resolve(strict=True)
    path = Path(unquote(parts.path)).resolve(strict=True)
    if not path.is_file() or not path.is_relative_to(root):
        raise ValueError("Original liegt nicht als reguläre Datei unter dem Archiv-Mount")
    return path


def prepare_job(
    conn: psycopg.Connection,
    job_id: UUID,
    archive_root: Path,
    *,
    ocr_mode: str = "off",
    ocr_pages: set[int] | None = None,
) -> PreparedJob:
    """Lädt und extrahiert ein SHA-validiertes Original ausschließlich lesend."""
    with conn.cursor() as cur:
        cur.execute("SELECT current_database()")
        if cur.fetchone()[0] != "retro_rag_v2_test":
            raise RuntimeError("Nur V2-Testdatenbank erlaubt")
        cur.execute(
            """SELECT j.status, v.id, v.content_hash, v.source_filename,
                      v.archive_uri, v.processing_state
               FROM rag_v2.processing_job j
               JOIN rag_v2.document_version v ON v.id=j.document_version_id
               WHERE j.id=%s AND j.job_type='document_import'""",
            (job_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise ValueError("Importjob nicht vorhanden")
        status, version_id, expected_hash, filename, uri, processing_state = row
        if status != "pending" or processing_state != "discovered":
            raise ValueError("Importjob oder Dokumentversion nicht im Ausgangszustand")
        if not filename or not uri:
            raise ValueError("Archiviertes Original oder Quelldateiname fehlt")
        cur.execute(
            """SELECT 1 FROM rag_v2.processing_step
               WHERE processing_job_id=%s AND step_name='source_archived'
                 AND status='completed'""",
            (job_id,),
        )
        if cur.fetchone() is None:
            raise ValueError("Archivierungsschritt fehlt oder ist nicht abgeschlossen")

    path = resolve_archived_original(uri, archive_root)
    if path.name != expected_hash + Path(filename).suffix.lower():
        raise ValueError("Archivdateiname entspricht nicht dem erwarteten Hash")
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
        raise ValueError("Originalarchiv verletzt SHA-256-Integrität")
    suffix = Path(filename).suffix.lower()
    source_id = "document_version:" + str(version_id)
    if suffix == ".pdf":
        contract = read_pdf(
            path, source_id, ocr_mode=ocr_mode, ocr_pages=ocr_pages,
        )
    elif suffix == ".md":
        if ocr_mode != "off" or ocr_pages:
            raise ValueError("Markdown benötigt keine OCR")
        contract = read_markdown(path, source_id)
    else:
        raise ValueError("Nur PDF und Markdown unterstützt")
    if contract.source.content_hash != expected_hash:
        raise ValueError("Extraktionsvertrag weicht vom Originalhash ab")
    return PreparedJob(job_id, version_id, path, contract)


def validate_prepared_content(prepared: PreparedJob) -> None:
    """Pure extraction safeguards, shared by the manual and leased worker paths."""
    contract = prepared.contract
    if contract.indexing_allowed or contract.fact_proposals:
        raise ValueError("Verarbeitungsadapter darf keine Freigaben übernehmen")
    if contract.document.metadata.get("ocr_failed_pages"):
        raise ValueError("OCR-Fehlerseiten müssen vor Persistierung geprüft werden")
    if contract.source.kind == "pdf" and contract.warnings:
        raise ValueError("PDF-Warnungen erfordern vor Persistierung ein Review")
    if not contract.chunks or len(contract.chunks) > 10_000:
        raise ValueError("Leerer oder übergroßer Chunk-Satz nicht zulässig")
    if contract.source.source_id != "document_version:" + str(prepared.version_id):
        raise ValueError("Falsche Quellidentität")
    if hashlib.sha256(prepared.original_path.read_bytes()).hexdigest() != contract.source.content_hash:
        raise ValueError("Original wurde seit der Extraktion verändert")
    if [chunk.ordinal for chunk in contract.chunks] != list(range(len(contract.chunks))):
        raise ValueError("Chunk-Reihenfolge ungültig")
    for chunk in contract.chunks:
        if hashlib.sha256(chunk.text.encode("utf-8")).hexdigest() != chunk.chunk_hash:
            raise ValueError("Chunk-Hash ungültig")


def persist_contract(conn: psycopg.Connection, prepared: PreparedJob) -> int:
    """Schreibt nur Chunks und deren Verarbeitungsschritt, niemals Embeddings.

    Die aufrufende Stelle verwaltet Commit/Rollback. Ein bereits begonnenes
    Transaktionsfenster ist Pflicht; diese Funktion committet nicht.
    """
    if conn.info.transaction_status != TransactionStatus.INTRANS:
        raise RuntimeError("Explizite, offene DB-Transaktion erforderlich")
    validate_prepared_content(prepared)

    with conn.cursor() as cur:
        cur.execute("SELECT current_database(), session_user")
        if cur.fetchone() != ("retro_rag_v2_test", "rag_v2_importer_login"):
            raise RuntimeError("Persistierung nur mit dediziertem Importer-Login auf V2-Test")
        cur.execute("SELECT rag_v2.assert_import_write_gate()")
    return _persist_contract_rows(conn, prepared)


def _persist_contract_rows(
    conn: psycopg.Connection, prepared: PreparedJob, *, lease_owner: str | None = None
) -> int:
    """DB-Kern ohne Commit, nur für explizit rollback-only Migator-Integrationstests.

    Kein eigenständiger Anwendungseinstiegspunkt: die produktive Funktion
    persist_contract() erzwingt Importer-Login und Write-Gate davor.
    """
    validate_prepared_content(prepared)
    contract = prepared.contract
    with conn.cursor() as cur:
        cur.execute(
            """SELECT j.status, j.attempts, j.max_attempts,
                      v.id, v.content_hash, v.processing_state, v.state,
                      j.lease_owner, (j.lease_until > now())
               FROM rag_v2.processing_job j
               JOIN rag_v2.document_version v ON v.id=j.document_version_id
               WHERE j.id=%s AND j.job_type='document_import'
               FOR UPDATE OF j, v""",
            (prepared.job_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise ValueError("Unbekannter Importjob")
        status, attempts, max_attempts, version_id, sha, processing_state, state, owner, valid = row
        expected_status = "pending" if lease_owner is None else "running"
        allowed_states = ("discovered",) if lease_owner is None else ("discovered", "processing")
        if (
            status != expected_status
            or (attempts >= max_attempts if lease_owner is None else attempts > max_attempts)
            or (lease_owner is not None and (owner != lease_owner or not valid))
            or version_id != prepared.version_id
            or sha != contract.source.content_hash
            or processing_state not in allowed_states
            or state is not None
        ):
            raise ValueError("Job/Version inzwischen verändert oder nicht mehr bearbeitbar")
        cur.execute(
            """SELECT step_name, status FROM rag_v2.processing_step
               WHERE processing_job_id=%s FOR UPDATE""",
            (prepared.job_id,),
        )
        steps = cur.fetchall()
        if ("source_archived", "completed") not in steps or any(
            name == "text_extracted" for name, _ in steps
        ):
            raise ValueError("Archivierung nicht abgeschlossen oder Text bereits extrahiert")

        for chunk in contract.chunks:
            locator = {"source_id": contract.source.source_id}
            if chunk.page is not None:
                locator["page"] = chunk.page
            cur.execute(
                """INSERT INTO rag_v2.chunk
                   (document_version_id,sequence_no,content,content_hash,
                    page_from,page_to,section_path,source_locator)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb)""",
                (
                    version_id, chunk.ordinal, chunk.text, chunk.chunk_hash,
                    chunk.page, chunk.page, chunk.heading_path, json.dumps(locator),
                ),
            )
        chunk_set_hash = hashlib.sha256(
            json.dumps(
                [chunk.chunk_hash for chunk in contract.chunks],
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        cur.execute(
            """INSERT INTO rag_v2.processing_step
               (processing_job_id,step_name,status,input_hash,completed_at)
               VALUES (%s,'text_extracted','completed',%s,now())
               RETURNING id""",
            (prepared.job_id, contract.source.content_hash),
        )
        step_id = cur.fetchone()[0]
        cur.execute(
            """INSERT INTO rag_v2.processing_artifact
               (processing_step_id,artifact_kind,artifact_uri,content_hash)
               VALUES (%s,'chunk_set',%s,%s)""",
            (step_id, "db:rag_v2.chunk/" + str(version_id), chunk_set_hash),
        )
        cur.execute(
            """UPDATE rag_v2.document_version
               SET processing_state='processing' WHERE id=%s""",
            (version_id,),
        )
        if lease_owner is None:
            cur.execute(
                """UPDATE rag_v2.processing_job
                   SET status='running', attempts=attempts+1, updated_at=now()
                   WHERE id=%s""",
                (prepared.job_id,),
            )
        else:
            # Extraction is complete, but embeddings and final indexing are not.
            # Release claim without completing the document_import job.
            cur.execute(
                """UPDATE rag_v2.processing_job
                   SET lease_owner=NULL, lease_until=NULL, updated_at=now()
                   WHERE id=%s AND status='running' AND lease_owner=%s""",
                (prepared.job_id, lease_owner),
            )
    # Ausdrücklich NICHT indexed/completed/active: Embeddings und Review fehlen.
    return len(contract.chunks)
