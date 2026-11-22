"""Job -> PDF -> Chunks -> Embeddings -> Aktivierung: nur Rollback auf V2-Test.

Ausführung ausschließlich nach expliziter DSN-Aktivierung als dedizierter
Migrator. Kein Commit, keine neuen DBs/Container, kein echter Import-Apply.
"""
import hashlib
import os
from uuid import uuid4

import psycopg
import pymupdf
import pytest

from retro_rag.importer.activation import activate_version
from retro_rag.importer.job_pipeline import _persist_contract_rows, prepare_job


def test_synthetic_pdf_pipeline_rolls_back_everything(tmp_path):
    dsn = os.environ.get("RETRO_V2_JOB_ROLLBACK_DSN")
    if not dsn:
        pytest.skip("RETRO_V2_JOB_ROLLBACK_DSN nicht gesetzt")

    # Nur synthetische PDF-Bytes in einer privaten Pytest-Tempdatei.
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_text((48, 72), "ASUS CUBX AGP 4X")
        data = pdf.tobytes()
    sha = hashlib.sha256(data).hexdigest()
    archive_root = tmp_path / "originals"
    original = archive_root / sha[:2] / (sha + ".pdf")
    original.parent.mkdir(parents=True)
    original.write_bytes(data)

    conn = psycopg.connect(dsn, autocommit=False)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database(), session_user")
            assert cur.fetchone() == ("retro_rag_v2_test", "rag_v2_migrator_login")
            cur.execute("SELECT max(version) FROM rag_v2.schema_migration")
            assert cur.fetchone() == (6,)
            cur.execute("SELECT writes_enabled FROM rag_v2.write_gate WHERE id=true")
            assert cur.fetchone() == (False,)
            cur.execute("SET LOCAL ROLE rag_v2_migrator")
            # Für diese EINE Transaktion wird das Gate sichtbar; kein Commit.
            cur.execute(
                """UPDATE rag_v2.write_gate SET writes_enabled=true,
                   reason='Job-Adapter: nur Rollback-Integrationstest' WHERE id=true"""
            )
            cur.execute(
                "INSERT INTO rag_v2.document(title) VALUES (%s) RETURNING id",
                ("rollback-pdf-" + str(uuid4()),),
            )
            document_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO rag_v2.document_version
                   (document_id,version_no,content_hash,source_filename,
                    archive_uri,mime_type,byte_size)
                   VALUES (%s,1,%s,'synthetic.pdf',%s,'application/pdf',%s)
                   RETURNING id""",
                (document_id, sha, original.as_uri(), len(data)),
            )
            version_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO rag_v2.processing_job
                   (document_version_id,job_type) VALUES (%s,'document_import')
                   RETURNING id""",
                (version_id,),
            )
            job_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO rag_v2.processing_step
                   (processing_job_id,step_name,status,input_hash,completed_at)
                   VALUES (%s,'source_archived','completed',%s,now())
                   RETURNING id""",
                (job_id, sha),
            )
            archive_step_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO rag_v2.processing_artifact
                   (processing_step_id,artifact_kind,artifact_uri,content_hash)
                   VALUES (%s,'original',%s,%s)""",
                (archive_step_id, original.as_uri(), sha),
            )

        prepared = prepare_job(conn, job_id, archive_root)
        assert prepared.contract.chunks
        assert not prepared.contract.warnings
        assert not prepared.contract.indexing_allowed
        assert not prepared.contract.fact_proposals

        count = _persist_contract_rows(conn, prepared)
        assert count == len(prepared.contract.chunks)
        with conn.cursor() as cur:
            cur.execute(
                """SELECT sequence_no,content_hash,page_from,page_to,section_path
                   FROM rag_v2.chunk
                   WHERE document_version_id=%s ORDER BY sequence_no""",
                (version_id,),
            )
            chunks = cur.fetchall()
            assert len(chunks) == count
            assert [row[0] for row in chunks] == list(range(count))
            assert all(row[2] == row[3] == 1 for row in chunks)
            cur.execute(
                """SELECT step_name,status FROM rag_v2.processing_step
                   WHERE processing_job_id=%s ORDER BY step_name""",
                (job_id,),
            )
            assert cur.fetchall() == [
                ("source_archived", "completed"),
                ("text_extracted", "completed"),
            ]
            cur.execute(
                """SELECT artifact_kind FROM rag_v2.processing_artifact a
                   JOIN rag_v2.processing_step s ON s.id=a.processing_step_id
                   WHERE s.processing_job_id=%s ORDER BY artifact_kind""",
                (job_id,),
            )
            assert [row[0] for row in cur.fetchall()] == ["chunk_set", "original"]
            cur.execute(
                "SELECT processing_state FROM rag_v2.document_version WHERE id=%s",
                (version_id,),
            )
            assert cur.fetchone() == ("processing",)
            cur.execute(
                "SELECT status,attempts FROM rag_v2.processing_job WHERE id=%s",
                (job_id,),
            )
            assert cur.fetchone() == ("running", 1)

        with pytest.raises(ValueError, match="nicht mehr bearbeitbar"):
            _persist_contract_rows(conn, prepared)

        # Ausschließlich synthetisches Embedding für den technischen Gate-Test;
        # keine echte Embedding-Pipeline wird hier behauptet.
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO rag_v2.embedding_model(model_name,dimensions)
                   VALUES (%s,3) RETURNING id""",
                ("job-rollback-" + str(uuid4()),),
            )
            model_id = cur.fetchone()[0]
            cur.execute(
                "SELECT id FROM rag_v2.chunk WHERE document_version_id=%s",
                (version_id,),
            )
            chunk_ids = [r[0] for r in cur.fetchall()]
            for chunk_id in chunk_ids:
                cur.execute(
                    """INSERT INTO rag_v2.chunk_embedding
                       (chunk_id,embedding_model_id,dimensions,embedding)
                       VALUES (%s,%s,3,'[0.1,0.2,0.3]'::public.vector)""",
                    (chunk_id, model_id),
                )
            cur.execute(
                """UPDATE rag_v2.processing_job
                   SET status='completed',completed_at=now() WHERE id=%s""",
                (job_id,),
            )
            cur.execute(
                """UPDATE rag_v2.document_version
                   SET processing_state='indexed' WHERE id=%s""",
                (version_id,),
            )
        result = activate_version(conn, version_id)
        assert result.changed
        assert result.version_id == version_id
        with conn.cursor() as cur:
            cur.execute("SELECT state FROM rag_v2.document_version WHERE id=%s", (version_id,))
            assert cur.fetchone() == ("active",)
    finally:
        # Dieser Test darf NIE committen (auch bei fehlgeschlagener Assertion).
        conn.rollback()
        conn.close()

    # Unabhängige erneute Anmeldung nach Rollback: kein Gate-Apply, keine
    # Datensätze dieses Testdokuments, keine aktive Version.
    with psycopg.connect(dsn, autocommit=False) as check:
        with check.cursor() as cur:
            cur.execute("SELECT writes_enabled FROM rag_v2.write_gate WHERE id=true")
            assert cur.fetchone() == (False,)
            cur.execute("SELECT COUNT(*) FROM rag_v2.document WHERE id=%s", (document_id,))
            assert cur.fetchone() == (0,)
            cur.execute("SELECT COUNT(*) FROM rag_v2.document_version WHERE id=%s", (version_id,))
            assert cur.fetchone() == (0,)
            cur.execute("SELECT COUNT(*) FROM rag_v2.processing_job WHERE id=%s", (job_id,))
            assert cur.fetchone() == (0,)
        check.rollback()
