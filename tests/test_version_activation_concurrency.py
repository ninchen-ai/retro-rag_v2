"""C1-Konkurrenztest mit drei echten PostgreSQL-Verbindungen.

NUR in einer separat gestarteten, nicht vernetzten PostgreSQL-Instanz.
Die Instanz muss cluster_name='retro-rag-v2-c1-isolated' melden.
"""
import os
import time
from concurrent.futures import ThreadPoolExecutor

import psycopg
import pytest

from retro_rag.importer.activation import activate_version


def _insert_version(conn, document_id, version_no, active=False):
    """Vollständig synthetische Version mit minimalem gültigen Index."""
    import hashlib
    from uuid import uuid4

    content_hash = hashlib.sha256(f"{document_id}:{version_no}".encode()).hexdigest()
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO rag_v2.document_version
               (document_id,version_no,content_hash,processing_state,state,archive_uri)
               VALUES (%s,%s,%s,'indexed',%s,%s) RETURNING id""",
            (document_id, version_no, content_hash,
             "active" if active else None, "file:///c1-isolated/" + content_hash),
        )
        version_id = cur.fetchone()[0]
        cur.execute(
            """INSERT INTO rag_v2.processing_job
               (document_version_id,job_type,status,completed_at)
               VALUES (%s,'document_import','completed',now()) RETURNING id""",
            (version_id,),
        )
        job_id = cur.fetchone()[0]
        cur.execute(
            """INSERT INTO rag_v2.processing_step
               (processing_job_id,step_name,status,completed_at)
               VALUES (%s,'source_archived','completed',now())""",
            (job_id,),
        )
        cur.execute(
            """INSERT INTO rag_v2.chunk
               (document_version_id,sequence_no,content,content_hash)
               VALUES (%s,0,'Synthetischer C1-Text',%s) RETURNING id""",
            (version_id, hashlib.sha256(b"Synthetischer C1-Text").hexdigest()),
        )
        chunk_id = cur.fetchone()[0]
        cur.execute(
            """INSERT INTO rag_v2.embedding_model(model_name,dimensions)
               VALUES (%s,3) RETURNING id""",
            ("isolated-c1-" + str(uuid4()),),
        )
        model_id = cur.fetchone()[0]
        cur.execute(
            """INSERT INTO rag_v2.chunk_embedding
               (chunk_id,embedding_model_id,dimensions,embedding)
               VALUES (%s,%s,3,'[0.1,0.2,0.3]'::public.vector)""",
            (chunk_id, model_id),
        )
    return version_id


def _second_activate(conn, version_id):
    result = activate_version(conn, version_id)
    conn.commit()
    return result


def test_two_concurrent_activations_are_serialized():
    dsn = os.environ.get("RETRO_V2_C1_ISOLATED_DSN")
    if not dsn:
        pytest.skip("RETRO_V2_C1_ISOLATED_DSN fehlt")

    # Der Cluster-Name ist ein zwingendes zusätzliches Schutzmerkmal:
    # die vorhandene V2-Testdatenbank ist KEIN zulässiges Testziel.
    with psycopg.connect(dsn, autocommit=True) as check:
        with check.cursor() as cur:
            cur.execute("SELECT current_database(), current_setting('cluster_name'), session_user")
            dbname, cluster_name, username = cur.fetchone()
            if (dbname, cluster_name, username) != (
                "retro_rag_v2_test", "retro-rag-v2-c1-isolated", "postgres"
            ):
                raise RuntimeError("C1-Konkurrenztest nur im isolierten Testcluster als postgres")
            cur.execute("SELECT MAX(version) FROM rag_v2.schema_migration")
            if cur.fetchone()[0] != 5:
                raise RuntimeError("Isolierter Cluster benötigt vollständiges Schema bis 0005")
            cur.execute("SELECT writes_enabled FROM rag_v2.write_gate WHERE id=true")
            if cur.fetchone()[0] is not False:
                raise RuntimeError("Isolierter Cluster muss mit geschlossenem Gate starten")
            # Ausschließlich der isolierte Cluster erhält eine committed Freigabe.
            cur.execute(
                """UPDATE rag_v2.write_gate SET writes_enabled=true,
                   reason='Nur C1-Test in isoliertem Docker-Cluster' WHERE id=true"""
            )

    with psycopg.connect(dsn, autocommit=False) as setup:
        with setup.cursor() as cur:
            cur.execute(
                "INSERT INTO rag_v2.document(title) VALUES ('C1-Konkurrenztest') RETURNING id"
            )
            document_id = cur.fetchone()[0]
        old = _insert_version(setup, document_id, 1, active=True)
        middle = _insert_version(setup, document_id, 2)
        newest = _insert_version(setup, document_id, 3)
        setup.commit()

    with (
        psycopg.connect(dsn, autocommit=False) as first,
        psycopg.connect(dsn, autocommit=False) as second,
        psycopg.connect(dsn, autocommit=True) as observer,
    ):
        with second.cursor() as cur:
            cur.execute("SELECT pg_backend_pid()")
            second_pid = cur.fetchone()[0]
        second.commit()

        with first.cursor() as cur:
            cur.execute("SET lock_timeout='5s'")
        # Die äußere Transaktion hält die Dokument-Zeilensperre absichtlich.
        first_result = activate_version(first, middle)
        assert first_result.changed and first_result.previous_version_id == old
        blocked = False
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(_second_activate, second, newest)
                limit = time.monotonic() + 4
                while time.monotonic() < limit:
                    with observer.cursor() as cur:
                        cur.execute("SELECT pg_blocking_pids(%s)", (second_pid,))
                        blocking_pids = cur.fetchone()[0]
                    if blocking_pids:
                        blocked = True
                        break
                    if future.done():
                        break
                    time.sleep(0.05)
                # Erst nach positiver Blockiererbeobachtung die Sperre lösen.
                if not blocked:
                    first.rollback()
                    future.result(timeout=6)
                    pytest.fail("Keine tatsächlich blockierte zweite Aktivierung nachgewiesen")
                first.commit()
                second_result = future.result(timeout=6)
                assert second_result.changed
                assert second_result.previous_version_id == middle
        finally:
            first.rollback()

        with observer.cursor() as cur:
            cur.execute(
                """SELECT version_no,state
                   FROM rag_v2.document_version
                   WHERE document_id=%s ORDER BY version_no""",
                (document_id,),
            )
            assert cur.fetchall() == [
                (1, "superseded"), (2, "superseded"), (3, "active")
            ]
            cur.execute(
                """SELECT COUNT(*) FROM rag_v2.document_version
                   WHERE document_id=%s AND state='active'""",
                (document_id,),
            )
            assert cur.fetchone()[0] == 1
    assert blocked
