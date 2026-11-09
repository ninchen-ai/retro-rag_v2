"""Rollback-only integration tests against Poseidon's V2 test database.

Requires RETRO_V2_IDENTITY_TEST_DSN for the dedicated V2 migrator LOGIN.
Never commits an open write gate. No Nextcloud, archive, or V1 writes.
"""

import json
import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

from retro_rag.importer import staging
from retro_rag.importer.webdav import RemoteFile


@pytest.fixture
def db(monkeypatch):
    dsn = os.environ.get("RETRO_V2_IDENTITY_TEST_DSN")
    if not dsn:
        pytest.skip("RETRO_V2_IDENTITY_TEST_DSN nicht gesetzt")
    # No archive files in these tests; only the DB write path is tested.
    monkeypatch.setattr(
        staging,
        "archive_original",
        lambda archive_root, data, filename: "file:///nonexistent/test-only/" + staging.digest(data),
    )
    conn = psycopg.connect(dsn, autocommit=False)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database(), session_user")
            dbname, username = cur.fetchone()
            if dbname != "retro_rag_v2_test" or username != "rag_v2_migrator_login":
                raise RuntimeError("Nur dedizierter Migrator-Login auf retro_rag_v2_test erlaubt")
            cur.execute("SELECT max(version) FROM rag_v2.schema_migration")
            if cur.fetchone()[0] != 5:
                raise RuntimeError("Migration 0005 als letzter Migrationsstand erforderlich")
            cur.execute("SELECT writes_enabled FROM rag_v2.write_gate WHERE id=true")
            if cur.fetchone()[0] is not False:
                raise RuntimeError("Test nur bei bereits geschlossenem Write-Gate")
            # SET LOCAL, true and all inserts remain invisible to other sessions;
            # the fixture NEVER commits this outer transaction.
            cur.execute("SET LOCAL ROLE rag_v2_migrator")
            cur.execute(
                """UPDATE rag_v2.write_gate
                   SET writes_enabled=true, reason='Identity integration test: rollback only'
                   WHERE id=true"""
            )
        yield conn
    finally:
        conn.rollback()
        conn.close()


def source(instance: str, key: str) -> RemoteFile:
    return RemoteFile(
        source_key=key,
        uri=f"https://nc.example/remote.php/dav/files/test/{instance}/{key}.md",
        name=f"{key}.md",
        etag=None,
        byte_size=None,
        content_type="text/markdown",
        instance_id=instance,
    )


def stage(conn, remote, data):
    return staging.stage_file(conn, remote, data, Path("/nonexistent/test-only"))


def scalar(conn, sql, params=()):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()[0]


def test_same_fileid_in_two_instances_is_distinct(db):
    key = str(uuid4())
    first = source("identity-test-a", key)
    second = source("identity-test-b", key)
    assert stage(db, first, b"file A") .action == "new"
    assert stage(db, second, b"file B").action == "new"
    with db.cursor() as cur:
        cur.execute(
            """SELECT source_instance, document_id
               FROM rag_v2.document_source
               WHERE source_system='nextcloud' AND source_key=%s
               ORDER BY source_instance""",
            (key,),
        )
        rows = cur.fetchall()
    assert [r[0] for r in rows] == ["identity-test-a", "identity-test-b"]
    assert rows[0][1] != rows[1][1]


def test_same_hash_other_source_creates_identity_review(db):
    key1, key2 = str(uuid4()), str(uuid4())
    data = b"identical-test-content-" + uuid4().bytes
    assert stage(db, source("identity-test-a", key1), data).action == "new"
    result = stage(db, source("identity-test-b", key2), data)
    assert result.action == "review"
    with db.cursor() as cur:
        cur.execute(
            """SELECT i.item_kind, i.status, i.proposal, b.document_version_id
               FROM rag_v2.review_item i
               JOIN rag_v2.review_batch b ON b.id=i.review_batch_id
               JOIN rag_v2.document_source s ON s.document_id =
                    (SELECT v.document_id FROM rag_v2.document_version v
                     WHERE v.id=b.document_version_id)
               WHERE s.source_instance=%s AND s.source_key=%s""",
            ("identity-test-b", key2),
        )
        rows = cur.fetchall()
    assert len(rows) == 1
    kind, status, proposal, version = rows[0]
    assert (kind, status) == ("document_identity", "proposed")
    assert proposal["reason"] == "same_hash_different_source"
    assert proposal["content_hash"] == staging.digest(data)
    assert len(proposal["candidate_document_ids"]) == 1
    assert str(version)


def test_reviewed_document_has_no_processing_job(db):
    data = b"review-no-job-" + uuid4().bytes
    key1, key2 = str(uuid4()), str(uuid4())
    stage(db, source("identity-test-a", key1), data)
    stage(db, source("identity-test-b", key2), data)
    with db.cursor() as cur:
        cur.execute(
            """SELECT COUNT(j.id)
               FROM rag_v2.document_source s
               JOIN rag_v2.document_version v ON v.document_id=s.document_id
               LEFT JOIN rag_v2.processing_job j ON j.document_version_id=v.id
               WHERE s.source_instance=%s AND s.source_key=%s""",
            ("identity-test-b", key2),
        )
        assert cur.fetchone()[0] == 0


def test_reimport_is_idempotent_even_for_review(db):
    data = b"replay-" + uuid4().bytes
    key1, key2 = str(uuid4()), str(uuid4())
    first = source("identity-test-a", key1)
    second = source("identity-test-b", key2)
    assert stage(db, first, data).action == "new"
    assert stage(db, second, data).action == "review"
    before = [
        scalar(db, "SELECT COUNT(*) FROM rag_v2.document"),
        scalar(db, "SELECT COUNT(*) FROM rag_v2.document_source"),
        scalar(db, "SELECT COUNT(*) FROM rag_v2.document_version"),
        scalar(db, "SELECT COUNT(*) FROM rag_v2.review_item"),
        scalar(db, "SELECT COUNT(*) FROM rag_v2.processing_job"),
    ]
    assert stage(db, second, data).action == "unchanged"
    assert stage(db, first, data).action == "unchanged"
    after = [
        scalar(db, "SELECT COUNT(*) FROM rag_v2.document"),
        scalar(db, "SELECT COUNT(*) FROM rag_v2.document_source"),
        scalar(db, "SELECT COUNT(*) FROM rag_v2.document_version"),
        scalar(db, "SELECT COUNT(*) FROM rag_v2.review_item"),
        scalar(db, "SELECT COUNT(*) FROM rag_v2.processing_job"),
    ]
    assert after == before
