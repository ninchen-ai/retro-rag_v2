"""Migration 0006: konkurrierende PostgreSQL-Sitzungen auf retro_rag_v2_test.

NUR nach dauerhaft angewendeter Migration 0006. Echte SCRAM-Logins; die
Passwoerter werden per getpass abgefragt und weder geloggt noch gespeichert.

Alle Testobjekte haben UUIDs; Topic-Fixtures werden nach den Tests geloescht.
Das Write-Gate wird lediglich uncommitted geoeffnet und wieder ROLLBACKt.
Eine Unterbrechung des Prozesses kann Topic-Fixtures zuruecklassen.
"""
from __future__ import annotations

import getpass
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import psycopg

DB = "retro_rag_v2_test"
HOST = "127.0.0.1"
MIGRATOR = "rag_v2_migrator_login"
IMPORTER = "rag_v2_importer_login"


def connect(role: str, password: str) -> psycopg.Connection:
    conn = psycopg.connect(
        host=HOST,
        port=5432,
        dbname=DB,
        user=role,
        password=password,
        connect_timeout=5,
        application_name="retro-rag-v2-0006-concurrency",
    )
    if role == MIGRATOR:
        conn.execute("SET ROLE rag_v2_migrator")
    conn.execute("SET lock_timeout = '12s'")
    conn.execute("SET statement_timeout = '20s'")
    conn.commit()
    return conn


def one(conn: psycopg.Connection, query: str, params=None):
    return conn.execute(query, params).fetchone()[0]


def backend(conn: psycopg.Connection) -> int:
    pid = one(conn, "SELECT pg_backend_pid()")
    conn.commit()
    return pid


def require_blocked(
    observer: psycopg.Connection, blocked_pid: int, blocker_pid: int, future
):
    """Detect actual database blocking, not simply concurrent Python threads."""
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        pids = one(observer, "SELECT pg_blocking_pids(%s)", (blocked_pid,))
        observer.commit()
        if blocker_pid in pids:
            return
        if future.done():
            break
        time.sleep(0.05)
    raise AssertionError(
        f"Kein beobachteter PostgreSQL-Blocker: blocker={blocker_pid}, "
        f"blocked={blocked_pid}"
    )


def expect_error(future, state: str, snippet: str):
    try:
        future.result(timeout=15)
    except psycopg.Error as exc:
        if exc.sqlstate != state or snippet not in str(exc):
            raise AssertionError(
                f"Falscher Fehler: SQLSTATE={exc.sqlstate}, erwartet {state}; {exc}"
            ) from exc
    else:
        raise AssertionError(f"Erwartete PostgreSQL-Ablehnung {state} blieb aus")


def update_topic(conn: psycopg.Connection, topic_id, parent_id):
    conn.execute(
        "UPDATE rag_v2.knowledge_topic SET parent_id=%s WHERE id=%s",
        (parent_id, topic_id),
    )
    conn.commit()


def propose(conn: psycopg.Connection, tag: str):
    conn.execute(
        """INSERT INTO rag_v2.knowledge_proposal
             (proposal_kind, origin_kind, payload, provenance, agent_run_key)
           VALUES ('fact', 'agent', %s::jsonb, %s::jsonb, %s)""",
        ('{"statement":"0006-only-test"}',
         '{"model":"parallel-test"}', tag),
    )
    conn.commit()


def main():
    print("0006: Parallelitaet auf bestehender Testdatenbank; keine neue Instanz")
    mpw = getpass.getpass(f"Passwort {MIGRATOR}: ")
    ipw = getpass.getpass(f"Passwort {IMPORTER}: ")

    connections: list[psycopg.Connection] = []
    a, b = uuid4(), uuid4()
    token = str(uuid4())
    inserted_topics = False
    original_topics = None
    original_proposals = None

    try:
        first = connect(MIGRATOR, mpw)
        connections.append(first)
        second = connect(MIGRATOR, mpw)
        connections.append(second)
        observer = connect(MIGRATOR, mpw)
        connections.append(observer)
        importer_1 = connect(IMPORTER, ipw)
        connections.append(importer_1)
        importer_2 = connect(IMPORTER, ipw)
        connections.append(importer_2)

        # Fail closed before any DML.
        dbname = one(observer, "SELECT current_database()")
        observer.commit()
        if dbname != DB:
            raise RuntimeError(f"Falsche Datenbank {dbname}")
        version = one(observer, "SELECT max(version) FROM rag_v2.schema_migration")
        observer.commit()
        gate = one(observer, "SELECT writes_enabled FROM rag_v2.write_gate WHERE id=true")
        observer.commit()
        if version != 6 or gate is not False:
            raise RuntimeError(f"Abbruch: migration={version}, write_gate={gate}")
        if one(observer, "SELECT to_regclass('rag_v2.knowledge_proposal') IS NOT NULL") is not True:
            raise RuntimeError("0006 Vorschlagstabelle fehlt")
        observer.commit()
        original_topics = one(observer, "SELECT count(*) FROM rag_v2.knowledge_topic")
        original_proposals = one(observer, "SELECT count(*) FROM rag_v2.knowledge_proposal")
        observer.commit()

        # Cross-session visibility requires committed topic fixtures.
        first.execute(
            "INSERT INTO rag_v2.knowledge_topic(id, name) VALUES "
            "(%s,%s),(%s,%s)",
            (a, "0006-parallel-" + token + "-a",
             b, "0006-parallel-" + token + "-b"),
        )
        first.commit()
        inserted_topics = True
        print(f"Test-Fixures: topic_id_a={a}, topic_id_b={b}")

        # 1: Concurrent opposite parent assignments must not form a cycle.
        first_pid, second_pid = backend(first), backend(second)
        first.execute(
            "UPDATE rag_v2.knowledge_topic SET parent_id=%s WHERE id=%s",
            (b, a),
        )
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(update_topic, second, b, a)
                require_blocked(observer, second_pid, first_pid, future)
                first.commit()
                expect_error(future, "P0001", "zyklische Themenhierarchie")
        finally:
            first.rollback()
            second.rollback()

        row = observer.execute(
            "SELECT (SELECT parent_id FROM rag_v2.knowledge_topic WHERE id=%s), "
            "(SELECT parent_id FROM rag_v2.knowledge_topic WHERE id=%s)",
            (a, b),
        ).fetchone()
        observer.commit()
        if row != (b, None):
            raise AssertionError(f"Themenstand nach Konkurrenz unerwartet: {row}")
        print("PASS 0006: Topic-Zyklus verhindert; Blockierung beobachtet")

        # 2: Gate updater transaction locks the row but rolls back. Importer
        # must block, then reject; no committed gate opening is performed.
        first_pid, importer_pid = backend(first), backend(importer_1)
        first.execute(
            "UPDATE rag_v2.write_gate SET writes_enabled=true, "
            "reason='0006-concurrency-uncommitted-only' WHERE id=true"
        )
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(propose, importer_1, token + "-blocked")
                require_blocked(observer, importer_pid, first_pid, future)
                first.rollback()
                expect_error(future, "42501", "Schreibsperre ist geschlossen")
        finally:
            first.rollback()
            importer_1.rollback()

        # 3: Two simultaneous importer attempts must both fail while closed.
        with ThreadPoolExecutor(max_workers=2) as pool:
            fa = pool.submit(propose, importer_1, token + "-a")
            fb = pool.submit(propose, importer_2, token + "-b")
            expect_error(fa, "42501", "Schreibsperre ist geschlossen")
            expect_error(fb, "42501", "Schreibsperre ist geschlossen")
        importer_1.rollback()
        importer_2.rollback()

        gate = one(observer, "SELECT writes_enabled FROM rag_v2.write_gate WHERE id=true")
        observer.commit()
        proposals = one(observer, "SELECT count(*) FROM rag_v2.knowledge_proposal")
        observer.commit()
        if gate is not False or proposals != original_proposals:
            raise AssertionError(
                f"Gate/Vorschlaege veraendert: gate={gate}, proposals={proposals}"
            )
        print("PASS 0006: Gate-Serialisierung und parallele Import-Ablehnung")

    finally:
        # Rollback every connection before fixture cleanup; uncommitted
        # transactions, including the temporary gate update, are discarded.
        for conn in connections:
            try:
                conn.rollback()
            except psycopg.Error:
                pass

        if inserted_topics:
            try:
                cleanup = connections[0]
                cleanup.execute(
                    "UPDATE rag_v2.knowledge_topic SET parent_id=NULL "
                    "WHERE id IN (%s,%s)", (a, b)
                )
                cleanup.execute(
                    "DELETE FROM rag_v2.knowledge_topic WHERE id IN (%s,%s)",
                    (a, b),
                )
                cleanup.commit()
                check_topics = one(
                    cleanup, "SELECT count(*) FROM rag_v2.knowledge_topic"
                )
                check_gate = one(
                    cleanup, "SELECT writes_enabled FROM rag_v2.write_gate WHERE id=true"
                )
                cleanup.commit()
                if check_topics != original_topics or check_gate is not False:
                    raise RuntimeError(
                        f"Cleanup unverifiziert: topics={check_topics}, gate={check_gate}"
                    )
                print("PASS 0006: Test-Fixures bereinigt, Write-Gate geschlossen")
            except Exception:
                print(f"ACHTUNG: Cleanup pruefen! Topic-IDs: {a}, {b}")
                raise
        for conn in connections:
            conn.close()

    print("PASS 0006: Mehrverbindungstests abgeschlossen")


if __name__ == "__main__":
    main()
