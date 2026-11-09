"""C1: echte SQL-Transaktionstests, ausschließlich rollback-only in V2-Test.

Nur mit RETRO_V2_C1_TEST_DSN; niemals gegen Produktion ausführen.
"""
import hashlib
import os
from uuid import uuid4

import psycopg
import pytest

from retro_rag.importer.activation import activate_version


@pytest.fixture
def db():
    dsn = os.environ.get("RETRO_V2_C1_TEST_DSN")
    if not dsn:
        pytest.skip("RETRO_V2_C1_TEST_DSN nicht gesetzt")
    conn = psycopg.connect(dsn, autocommit=False)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database(), session_user")
            if cur.fetchone() != ("retro_rag_v2_test", "rag_v2_migrator_login"):
                raise RuntimeError("C1-Tests erfordern dedizierten Migrator auf V2-Test")
            cur.execute("SELECT max(version) FROM rag_v2.schema_migration")
            if cur.fetchone()[0] != 5:
                raise RuntimeError("C1-Tests erwarten genau Migrationsstand 0005")
            cur.execute("SELECT writes_enabled FROM rag_v2.write_gate WHERE id=true")
            if cur.fetchone()[0] is not False:
                raise RuntimeError("C1-Tests starten nur bei geschlossenem Gate")
            cur.execute("SET LOCAL ROLE rag_v2_migrator")
            cur.execute("UPDATE rag_v2.write_gate SET writes_enabled=true WHERE id=true")
        yield conn
    finally:
        conn.rollback()
        conn.close()


def make_document(conn):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO rag_v2.document(title) VALUES (%s) RETURNING id",
            ("C1-" + str(uuid4()),),
        )
        return cur.fetchone()[0]


def add_version(conn, document_id, number, *, ready=True, active=False):
    """Erzeugt ausschließlich rollbackfähige, synthetische Daten."""
    value = hashlib.sha256(f"{document_id}-{number}".encode()).hexdigest()
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO rag_v2.document_version
               (document_id,version_no,content_hash,archive_uri,processing_state,state)
               VALUES (%s,%s,%s,%s,%s,%s) RETURNING id""",
            (document_id, number, value, "file:///synthetic/" + value,
             "indexed" if ready else "processing", "active" if active else None),
        )
        version = cur.fetchone()[0]
        if not ready:
            return version
        cur.execute(
            """INSERT INTO rag_v2.processing_job
               (document_version_id,job_type,status,completed_at)
               VALUES (%s,'document_import','completed',now()) RETURNING id""",
            (version,),
        )
        job = cur.fetchone()[0]
        cur.execute(
            """INSERT INTO rag_v2.processing_step
               (processing_job_id,step_name,status,completed_at)
               VALUES (%s,'source_archived','completed',now())""",
            (job,),
        )
        cur.execute(
            """INSERT INTO rag_v2.chunk(document_version_id,sequence_no,content,content_hash)
               VALUES (%s,0,'Testinhalt',%s) RETURNING id""",
            (version, hashlib.sha256(b"Testinhalt").hexdigest()),
        )
        chunk = cur.fetchone()[0]
        cur.execute(
            """INSERT INTO rag_v2.embedding_model(model_name,dimensions)
               VALUES (%s,3) RETURNING id""",
            ("c1-test-" + str(uuid4()),),
        )
        model = cur.fetchone()[0]
        cur.execute(
            """INSERT INTO rag_v2.chunk_embedding
               (chunk_id,embedding_model_id,dimensions,embedding)
               VALUES (%s,%s,3,'[0.1,0.2,0.3]'::public.vector)""",
            (chunk, model),
        )
        return version


def state(conn, version_id):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT state, archive_after FROM rag_v2.document_version WHERE id=%s",
            (version_id,),
        )
        return cur.fetchone()


def test_activates_and_supersedes_atomically(db):
    document = make_document(db)
    old = add_version(db, document, 1, active=True)
    new = add_version(db, document, 2)
    result = activate_version(db, new, superseded_days=30)
    assert (result.changed, result.previous_version_id) == (True, old)
    assert state(db, old)[0] == "superseded"
    assert state(db, old)[1] is not None
    assert state(db, new)[0] == "active"
    assert activate_version(db, new).changed is False


def test_unfinished_version_keeps_previous_active(db):
    document = make_document(db)
    old = add_version(db, document, 1, active=True)
    unfinished = add_version(db, document, 2, ready=False)
    with pytest.raises(ValueError, match="nicht vollständig"):
        activate_version(db, unfinished)
    assert state(db, old)[0] == "active"
    assert state(db, unfinished)[0] is None


def test_missing_embedding_keeps_previous_active(db):
    document = make_document(db)
    old = add_version(db, document, 1, active=True)
    new = add_version(db, document, 2)
    with db.cursor() as cur:
        cur.execute(
            """DELETE FROM rag_v2.chunk_embedding
               WHERE chunk_id IN (
                   SELECT id FROM rag_v2.chunk WHERE document_version_id=%s
               )""",
            (new,),
        )
    with pytest.raises(ValueError, match="kein Embedding"):
        activate_version(db, new)
    assert state(db, old)[0] == "active"


def test_cannot_activate_older_version(db):
    document = make_document(db)
    newer = add_version(db, document, 2, active=True)
    older = add_version(db, document, 1)
    with pytest.raises(ValueError, match="Ältere Version"):
        activate_version(db, older)
    assert state(db, newer)[0] == "active"


def test_savepoint_rollback_restores_both_states(db):
    document = make_document(db)
    old = add_version(db, document, 1, active=True)
    new = add_version(db, document, 2)
    with pytest.raises(RuntimeError, match="simulierter Abbruch"):
        with db.transaction():
            activate_version(db, new)
            raise RuntimeError("simulierter Abbruch")
    assert state(db, old)[0] == "active"
    assert state(db, new)[0] is None


def test_identity_review_blocks_activation(db):
    document = make_document(db)
    new = add_version(db, document, 1)
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO rag_v2.review_batch(document_version_id) VALUES (%s) RETURNING id",
            (new,),
        )
        batch = cur.fetchone()[0]
        cur.execute(
            """INSERT INTO rag_v2.review_item(review_batch_id,item_kind,proposal)
               VALUES (%s,'document_identity','{}'::jsonb)""",
            (batch,),
        )
    with pytest.raises(ValueError, match="Dokumentidentität"):
        activate_version(db, new)
    assert state(db, new)[0] is None
