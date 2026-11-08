"""DB-gestütztes, wiederholbares Staging für die V2-Testdatenbank."""

from dataclasses import dataclass
from pathlib import Path
import hashlib
import os

import psycopg

from retro_rag.importer.webdav import RemoteFile


@dataclass(frozen=True)
class PlannedChange:
    action: str
    source_key: str
    title: str
    content_hash: str


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def plan_file(conn: psycopg.Connection, file: RemoteFile, data: bytes) -> PlannedChange:
    """Plant ausschließlich lesend; identische Versionen werden übersprungen."""
    hash_value = digest(data)
    with conn.cursor() as cur:
        cur.execute(
            """SELECT s.document_id, s.last_seen_content_hash
               FROM rag_v2.document_source s
               WHERE s.source_system = 'nextcloud' AND s.source_key = %s""",
            (file.source_key,),
        )
        source = cur.fetchone()
        if source is None:
            return PlannedChange("new", file.source_key, file.name, hash_value)
        cur.execute(
            """SELECT 1 FROM rag_v2.document_version
               WHERE document_id = %s AND content_hash = %s LIMIT 1""",
            (source[0], hash_value),
        )
        if cur.fetchone() is not None:
            return PlannedChange("unchanged", file.source_key, file.name, hash_value)
        return PlannedChange("changed", file.source_key, file.name, hash_value)


def archive_original(archive_root: Path, data: bytes, filename: str) -> str:
    """Inhaltsadressiertes Originalarchiv; vorhandene Kopien auf Hash prüfen."""
    value = digest(data)
    ext = Path(filename).suffix.lower()
    if ext not in (".md", ".pdf"):
        raise ValueError("Nicht unterstütztes Dateiformat")
    folder = archive_root / value[:2]
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = folder / (value + ext)
    if path.exists():
        if digest(path.read_bytes()) != value:
            raise RuntimeError("Vorhandenes Archivartefakt stimmt nicht mit Hash überein")
    else:
        # Exklusives Schreiben verhindert Überschreiben unveränderter Rohdaten.
        try:
            with path.open("xb") as out:
                os.chmod(path, 0o600)
                out.write(data)
                out.flush()
                os.fsync(out.fileno())
        except FileExistsError:
            if digest(path.read_bytes()) != value:
                raise RuntimeError("Parallel angelegte Archivkopie hat anderen Hash")
    return path.resolve().as_uri()


def stage_file(
    conn: psycopg.Connection,
    file: RemoteFile,
    data: bytes,
    archive_root: Path,
) -> PlannedChange:
    """Erfordert expliziten Apply-Aufruf und eine offene DB-Schreibfreigabe."""
    file_hash = digest(data)
    with conn.transaction():
        with conn.cursor() as cur:
            # SECURITY DEFINER prüft und hält den FOR SHARE-Row-Lock.
            # Importer benötigt nur EXECUTE, niemals UPDATE auf write_gate.
            cur.execute("SELECT rag_v2.assert_import_write_gate()")
            # Eine bereits geschlossene Schreibsperre darf kein Archiv erzeugen.
            # Bei einem späteren SQL-Fehler bleibt höchstens eine verwaiste Archivdatei.
            archive_uri = archive_original(archive_root, data, file.name)
            cur.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                ("nextcloud:" + file.source_key,),
            )
            cur.execute(
                """SELECT id, document_id FROM rag_v2.document_source
                   WHERE source_system='nextcloud' AND source_key=%s FOR UPDATE""",
                (file.source_key,),
            )
            row = cur.fetchone()
            if row is None:
                cur.execute(
                    """INSERT INTO rag_v2.document (title, document_type)
                       VALUES (%s, %s) RETURNING id""",
                    (file.name, "markdown" if file.name.lower().endswith(".md") else "pdf"),
                )
                document_id = cur.fetchone()[0]
                cur.execute(
                    """INSERT INTO rag_v2.document_source
                       (document_id,source_system,source_key,source_uri,last_seen_content_hash)
                       VALUES (%s,'nextcloud',%s,%s,%s)""",
                    (document_id, file.source_key, file.uri, file_hash),
                )
                action = "new"
            else:
                document_id = row[1]
                cur.execute(
                    """UPDATE rag_v2.document_source SET source_uri=%s,
                       last_seen_content_hash=%s, last_seen_at=now(), is_available=true
                       WHERE id=%s""",
                    (file.uri, file_hash, row[0]),
                )
                cur.execute(
                    """SELECT id FROM rag_v2.document_version
                       WHERE document_id=%s AND content_hash=%s LIMIT 1""",
                    (document_id, file_hash),
                )
                if cur.fetchone():
                    return PlannedChange("unchanged", file.source_key, file.name, file_hash)
                action = "changed"
            cur.execute(
                """SELECT COALESCE(MAX(version_no),0)+1
                   FROM rag_v2.document_version WHERE document_id=%s""",
                (document_id,),
            )
            version_no = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO rag_v2.document_version
                   (document_id,version_no,content_hash,source_filename,
                    archive_uri,mime_type,byte_size)
                   VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                (document_id, version_no, file_hash, file.name, archive_uri,
                 file.content_type, len(data)),
            )
            version_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO rag_v2.processing_job (document_version_id,job_type)
                   VALUES (%s,'document_import') RETURNING id""",
                (version_id,),
            )
            job_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO rag_v2.processing_step
                   (processing_job_id,step_name,input_hash)
                   VALUES (%s,'source_archived',%s) RETURNING id""",
                (job_id, file_hash),
            )
            step_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO rag_v2.processing_artifact
                   (processing_step_id,artifact_kind,artifact_uri,content_hash)
                   VALUES (%s,'original',%s,%s)""",
                (step_id, archive_uri, file_hash),
            )
            cur.execute(
                """UPDATE rag_v2.processing_step SET status='completed',
                   completed_at=now() WHERE id=%s""",
                (step_id,),
            )
    return PlannedChange(action, file.source_key, file.name, file_hash)
