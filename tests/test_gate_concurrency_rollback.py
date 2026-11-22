"""Reale Gate-Sperrkonkurrenz auf V2-Test, ohne Commit und ohne Fixtures.

Dies ist ein Guard-/Serialisierungstest und KEIN Zwei-Aktivierungen-C1-Test.
Nur auf ausdrückliche Aktivierung mit zwei sicheren Rollen-Logins ausführbar.
"""

import os
import time
from concurrent.futures import ThreadPoolExecutor

import psycopg
import pytest


def _assert_import_gate(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT rag_v2.assert_import_write_gate()")


def test_uncommitted_gate_update_blocks_then_rejects_importer():
    migrator_dsn = os.getenv("RETRO_V2_GATE_MIGRATOR_DSN")
    importer_dsn = os.getenv("RETRO_V2_GATE_IMPORTER_DSN")
    migrator_password = os.getenv("RETRO_V2_GATE_MIGRATOR_PASSWORD")
    importer_password = os.getenv("RETRO_V2_GATE_IMPORTER_PASSWORD")
    if not all((migrator_dsn, importer_dsn, migrator_password, importer_password)):
        pytest.skip("V2-Gate-Konkurrenz-DSNs/Passwörter fehlen")

    with (
        psycopg.connect(migrator_dsn, password=migrator_password, autocommit=False) as writer,
        psycopg.connect(importer_dsn, password=importer_password, autocommit=False) as reader,
        psycopg.connect(migrator_dsn, password=migrator_password, autocommit=True) as observer,
    ):
        try:
            with observer.cursor() as cur:
                cur.execute("SELECT current_database(), session_user")
                assert cur.fetchone() == ("retro_rag_v2_test", "rag_v2_migrator_login")
                cur.execute("SELECT max(version) FROM rag_v2.schema_migration")
                assert cur.fetchone() == (6,)
                cur.execute("SELECT writes_enabled FROM rag_v2.write_gate WHERE id=true")
                assert cur.fetchone() == (False,)

            with writer.cursor() as cur:
                cur.execute("SELECT current_database(), session_user, pg_backend_pid()")
                dbname, user, writer_pid = cur.fetchone()
                assert (dbname, user) == ("retro_rag_v2_test", "rag_v2_migrator_login")
                cur.execute("SET LOCAL ROLE rag_v2_migrator")
                # Bleibt ausschließlich in dieser nie committeten Transaktion.
                cur.execute(
                    """UPDATE rag_v2.write_gate
                       SET writes_enabled=true,
                           reason='Rollback-only Gate-Blockierungstest'
                       WHERE id=true"""
                )
                assert cur.rowcount == 1

            with reader.cursor() as cur:
                cur.execute("SELECT current_database(), session_user, pg_backend_pid()")
                dbname, user, reader_pid = cur.fetchone()
                assert (dbname, user) == ("retro_rag_v2_test", "rag_v2_importer_login")
                cur.execute("SET LOCAL lock_timeout = '8s'")
                cur.execute("SET LOCAL statement_timeout = '12s'")

            blocked = False
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(_assert_import_gate, reader)
                deadline = time.monotonic() + 6
                try:
                    while time.monotonic() < deadline:
                        with observer.cursor() as cur:
                            cur.execute("SELECT pg_blocking_pids(%s)", (reader_pid,))
                            blocking = cur.fetchone()[0]
                        if writer_pid in blocking:
                            blocked = True
                            break
                        if future.done():
                            break
                        time.sleep(0.05)
                finally:
                    # Auch bei Fehlern/Timeout: die Freigabe NICHT committen.
                    writer.rollback()

                # Nach der Sperrfreigabe muss der Reader das geschlossene Gate sehen.
                with pytest.raises(
                    psycopg.errors.InsufficientPrivilege,
                    match="V2-Schreibsperre ist geschlossen",
                ) as error:
                    future.result(timeout=5)
                assert error.value.sqlstate == "42501"
            assert blocked, "Keine tatsächliche PostgreSQL-Blockierung nachgewiesen"
        finally:
            writer.rollback()
            reader.rollback()

        with observer.cursor() as cur:
            cur.execute("SELECT writes_enabled, reason FROM rag_v2.write_gate WHERE id=true")
            assert cur.fetchone() == (
                False, "Parallelitätstest erfolgreich; Freigabe ausstehend"
            )
