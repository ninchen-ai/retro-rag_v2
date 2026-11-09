"""Atomare Veröffentlichung vollständig technisch indexierter Dokumentversionen.

Die eigentliche Extraktion und Embedding-Erzeugung erfolgt in separaten Workern.
Diese Funktion veröffentlicht ausschließlich vollständig vorbereitete Versionen.
"""

from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

import psycopg


@dataclass(frozen=True)
class ActivationResult:
    document_id: UUID
    version_id: UUID
    previous_version_id: UUID | None
    changed: bool


def activate_version(
    conn: psycopg.Connection,
    version_id: UUID,
    *,
    superseded_days: int = 30,
) -> ActivationResult:
    """Aktiviert eine indexierte Version atomar; Änderungen nur bei offenem Gate.

    Der Aufrufer muss eine noch nicht abgeschlossene Verbindung übergeben.
    Alle DB-Änderungen einschließlich des Gate-Locks sind Teil *einer*
    Transaktion. Bei Fehlern bleibt die bisherige aktive Version erhalten.
    """
    if superseded_days < 1:
        raise ValueError("superseded_days muss positiv sein")

    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute("SELECT current_database()")
            if cur.fetchone()[0] != "retro_rag_v2_test":
                raise RuntimeError("C1 ist ausschließlich für retro_rag_v2_test freigegeben")

            cur.execute("SELECT rag_v2.assert_import_write_gate()")
            # Dokumentzeile ist die gemeinsame Serialisierungssperre aller
            # Aktivierungen desselben logischen Dokuments.
            cur.execute(
                "SELECT document_id FROM rag_v2.document_version WHERE id=%s",
                (version_id,),
            )
            row = cur.fetchone()
            if row is None:
                raise ValueError("Unbekannte Dokumentversion")
            document_id = row[0]
            cur.execute(
                "SELECT availability FROM rag_v2.document WHERE id=%s FOR UPDATE",
                (document_id,),
            )
            document = cur.fetchone()
            if document is None or document[0] != "available":
                raise ValueError("Dokument ist nicht verfügbar")

            # Nach der Dokumentsperre erneut prüfen: der Zustand kann sich
            # während des Wartens auf einen anderen Aktivierer geändert haben.
            cur.execute(
                """SELECT version_no, processing_state, state, archive_uri
                   FROM rag_v2.document_version
                   WHERE id=%s AND document_id=%s FOR UPDATE""",
                (version_id, document_id),
            )
            target = cur.fetchone()
            if target is None:
                raise ValueError("Dokumentversion wurde verändert")
            version_no, processing_state, state, archive_uri = target
            if state == "active":
                return ActivationResult(document_id, version_id, None, False)
            if state is not None:
                raise ValueError("Nur noch unveröffentlichte Versionen dürfen aktiviert werden")
            if processing_state != "indexed" or not archive_uri:
                raise ValueError("Version ist nicht vollständig technisch indexiert")

            cur.execute(
                """SELECT id, version_no FROM rag_v2.document_version
                   WHERE document_id=%s AND state='active' FOR UPDATE""",
                (document_id,),
            )
            active = cur.fetchone()
            if active and active[1] >= version_no:
                raise ValueError("Ältere Version darf neuere aktive Version nicht ersetzen")

            cur.execute(
                """SELECT 1 FROM rag_v2.review_batch b
                   JOIN rag_v2.review_item i ON i.review_batch_id=b.id
                   WHERE b.document_version_id=%s
                     AND i.item_kind='document_identity'
                     AND i.status IN ('proposed','deferred')
                   LIMIT 1""",
                (version_id,),
            )
            if cur.fetchone():
                raise ValueError("Dokumentidentität muss vor Aktivierung geklärt werden")

            cur.execute(
                """SELECT id FROM rag_v2.processing_job
                   WHERE document_version_id=%s AND job_type='document_import'
                     AND status='completed'
                   ORDER BY completed_at DESC NULLS LAST LIMIT 1""",
                (version_id,),
            )
            job = cur.fetchone()
            if job is None:
                raise ValueError("Kein abgeschlossener Importjob vorhanden")
            cur.execute(
                """SELECT COUNT(*), COUNT(*) FILTER (WHERE status='completed'),
                          COUNT(*) FILTER (WHERE status NOT IN ('completed','skipped'))
                   FROM rag_v2.processing_step WHERE processing_job_id=%s""",
                (job[0],),
            )
            step_count, completed_count, unfinished_count = cur.fetchone()
            if step_count == 0 or completed_count == 0 or unfinished_count:
                raise ValueError("Importjob besitzt offene oder fehlende Schritte")
            cur.execute(
                """SELECT 1 FROM rag_v2.processing_step
                   WHERE processing_job_id=%s AND step_name='source_archived'
                     AND status='completed'""",
                (job[0],),
            )
            if cur.fetchone() is None:
                raise ValueError("Abgeschlossener Archivierungsschritt fehlt")

            cur.execute(
                "SELECT COUNT(*) FROM rag_v2.chunk WHERE document_version_id=%s",
                (version_id,),
            )
            if cur.fetchone()[0] == 0:
                raise ValueError("Keine Such-Chunks vorhanden")
            cur.execute(
                """SELECT 1 FROM rag_v2.chunk c
                   WHERE c.document_version_id=%s
                   AND NOT EXISTS (
                       SELECT 1 FROM rag_v2.chunk_embedding e WHERE e.chunk_id=c.id
                   ) LIMIT 1""",
                (version_id,),
            )
            if cur.fetchone():
                raise ValueError("Mindestens ein Chunk besitzt kein Embedding")

            previous_id = active[0] if active else None
            if previous_id is not None:
                cur.execute(
                    """UPDATE rag_v2.document_version
                       SET state='superseded', superseded_at=now(),
                           archive_after=now() + (%s * interval '1 day')
                       WHERE id=%s AND state='active'""",
                    (superseded_days, previous_id),
                )
                if cur.rowcount != 1:
                    raise RuntimeError("Aktive Vorgängerversion wurde parallel verändert")
            cur.execute(
                """UPDATE rag_v2.document_version
                   SET state='active', indexed_at=COALESCE(indexed_at, now()),
                       superseded_at=NULL, archive_after=NULL
                   WHERE id=%s AND state IS NULL AND processing_state='indexed'""",
                (version_id,),
            )
            if cur.rowcount != 1:
                raise RuntimeError("Version konnte nicht aktiviert werden")
    return ActivationResult(document_id, version_id, previous_id, True)
