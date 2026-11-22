"""Real CUBX PDF/OCR -> chunks -> Ollama embeddings -> activation, rollback-only.

Opt-in PR13 integration check, *not* a production ingestion worker.
Only the known SHA-256 pinned WebDAV fileid 172 is accepted, and only the
separate PR13 PostgreSQL cluster may be modified (never committed).
The technical activation is simulated after manual job completion: the PDF
contract deliberately has indexing_allowed=False.
"""

import hashlib
import json
import math
import os
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

import psycopg
import pytest

from retro_rag.importer.activation import activate_version
from retro_rag.importer.job_pipeline import _persist_contract_rows, prepare_job
from retro_rag.importer.staging import stage_file
from retro_rag.importer.webdav import RemoteFile

EXPECTED_SHA = "f10dc04911aa75241adcb29731af62fc4ce4c5e5a21b0a69ff621778c784f82b"
EXPECTED_PATH = Path("/data/retro-rag/v2/e2e-isolated/cubx-103.pdf")
EXPECTED_BYTES = 4914302
EMBED_URL = "http://127.0.0.1:11434/api/embed"
EMBED_MODEL = "nomic-embed-text"
EMBED_DIMENSIONS = 768


def _embed_batch(texts: list[str]) -> list[list[float]]:
    """Generate actual local Ollama embeddings; fail closed on bad output."""
    assert texts and len(texts) <= 8
    request = Request(
        EMBED_URL,
        data=json.dumps({"model": EMBED_MODEL, "input": texts}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=120) as response:
        embeddings = json.load(response).get("embeddings")
    if not isinstance(embeddings, list) or len(embeddings) != len(texts):
        raise ValueError("Ollama returned an unexpected number of embeddings")
    for vector in embeddings:
        if not isinstance(vector, list) or len(vector) != EMBED_DIMENSIONS:
            raise ValueError("Ollama embedding has the wrong dimensions")
        if any(
            type(value) not in (float, int) or not math.isfinite(value)
            for value in vector
        ):
            raise ValueError("Ollama embedding contains invalid values")
    return embeddings


def test_real_cubx_pdf_ocr_to_embeddings_isolated_rollback(tmp_path):
    dsn = os.environ.get("RETRO_V2_E2E_ISOLATED_DSN")
    uri = os.environ.get("RETRO_V2_E2E_PDF_SOURCE_URI")
    if not (dsn and uri):
        pytest.skip("Requires the PR13 isolated DB and verified WebDAV PDF URI")

    path = EXPECTED_PATH.resolve(strict=True)
    if path != EXPECTED_PATH or not path.is_file():
        raise RuntimeError("Only the verified, isolated CUBX original is allowed")
    data = path.read_bytes()
    if (
        len(data) != EXPECTED_BYTES
        or hashlib.sha256(data).hexdigest() != EXPECTED_SHA
        or not data.startswith(b"%PDF-")
    ):
        raise RuntimeError("CUBX original SHA-256, size, or PDF signature mismatch")

    parts = urlsplit(uri)
    if (
        parts.scheme not in ("http", "https")
        or not parts.hostname
        or parts.username
        or parts.password
        or parts.query
        or parts.fragment
    ):
        raise ValueError("Invalid WebDAV source URI")
    remote = RemoteFile(
        source_key="172",
        instance_id="poseidon-nextcloud",
        uri=uri,
        name="cubx-103.pdf",
        etag=None,
        byte_size=len(data),
        content_type="application/pdf",
    )

    conn = psycopg.connect(dsn, autocommit=False)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT current_database(), current_setting('cluster_name'), session_user"
            )
            if cur.fetchone() != (
                "retro_rag_v2_test",
                "retro-rag-v2-pr13-e2e-isolated",
                "rag_v2_migrator_login",
            ):
                raise RuntimeError("Refusing non-isolated DB or wrong login")
            cur.execute("SELECT max(version) FROM rag_v2.schema_migration")
            if cur.fetchone() != (6,):
                raise RuntimeError("Migration 0006 required")
            cur.execute("SELECT writes_enabled FROM rag_v2.write_gate WHERE id=true")
            if cur.fetchone() != (False,):
                raise RuntimeError("Closed write gate required")
            cur.execute(
                "SELECT (SELECT count(*) FROM rag_v2.document), "
                "(SELECT count(*) FROM rag_v2.document_version), "
                "(SELECT count(*) FROM rag_v2.processing_job)"
            )
            if cur.fetchone() != (0, 0, 0):
                raise RuntimeError("Isolated test DB is not empty")
            cur.execute("SET LOCAL ROLE rag_v2_migrator")
            # Only visible in this one uncommitted transaction.
            cur.execute(
                "UPDATE rag_v2.write_gate SET writes_enabled=true, "
                "reason='PR13 PDF E2E rollback only' WHERE id=true"
            )

        archive = tmp_path / "isolated-originals"
        assert stage_file(conn, remote, data, archive).action == "new"

        with conn.cursor() as cur:
            cur.execute(
                """SELECT v.id, j.id FROM rag_v2.document_source s
                   JOIN rag_v2.document_version v ON v.document_id=s.document_id
                   JOIN rag_v2.processing_job j ON j.document_version_id=v.id
                   WHERE s.source_system='nextcloud'
                     AND s.source_instance=%s AND s.source_key='172'
                     AND v.content_hash=%s""",
                (remote.instance_id, EXPECTED_SHA),
            )
            version_id, job_id = cur.fetchone()

        prepared = prepare_job(
            conn, job_id, archive, ocr_mode="auto", ocr_pages={111}
        )
        contract = prepared.contract
        assert contract.source.kind == "pdf"
        assert contract.document.metadata["page_count"] == 112
        assert contract.document.metadata["ocr_pages"] == [111]
        assert contract.document.metadata["ocr_failed_pages"] == []
        assert contract.warnings == []
        assert contract.indexing_allowed is False
        assert not contract.fact_proposals
        assert len(contract.chunks) == 114
        assert any(chunk.page == 111 for chunk in contract.chunks)

        assert _persist_contract_rows(conn, prepared) == 114
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, content, page_from FROM rag_v2.chunk "
                "WHERE document_version_id=%s ORDER BY sequence_no",
                (version_id,),
            )
            rows = cur.fetchall()
        assert len(rows) == 114
        assert any(row[2] == 111 for row in rows)

        # The current processing adapter has no embedding/finalization worker.
        # This E2E smoke test therefore performs those technical steps explicitly.
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO rag_v2.embedding_model(model_name, dimensions) "
                "VALUES (%s, %s) RETURNING id",
                ("nomic-embed-text-pr13-pdf-e2e", EMBED_DIMENSIONS),
            )
            model_id = cur.fetchone()[0]

        for start in range(0, len(rows), 8):
            batch = rows[start : start + 8]
            vectors = _embed_batch([row[1] for row in batch])
            with conn.cursor() as cur:
                for (chunk_id, _, _), vector in zip(batch, vectors, strict=True):
                    cur.execute(
                        """INSERT INTO rag_v2.chunk_embedding
                           (chunk_id,embedding_model_id,dimensions,embedding)
                           VALUES (%s,%s,%s,%s::public.vector)""",
                        (
                            chunk_id, model_id, EMBED_DIMENSIONS,
                            json.dumps(vector, allow_nan=False),
                        ),
                    )

        # Embeddings alone must NOT silently activate a still-running job.
        with pytest.raises(ValueError, match="nicht vollständig technisch indexiert"):
            activate_version(conn, version_id)

        with conn.cursor() as cur:
            cur.execute(
                "UPDATE rag_v2.processing_job "
                "SET status='completed', completed_at=now() WHERE id=%s",
                (job_id,),
            )
            cur.execute(
                "UPDATE rag_v2.document_version SET processing_state='indexed' "
                "WHERE id=%s",
                (version_id,),
            )
        assert activate_version(conn, version_id).changed
        with conn.cursor() as cur:
            cur.execute(
                "SELECT state FROM rag_v2.document_version WHERE id=%s",
                (version_id,),
            )
            assert cur.fetchone() == ("active",)
            cur.execute(
                "SELECT count(*) FROM rag_v2.chunk_embedding e "
                "JOIN rag_v2.chunk c ON c.id=e.chunk_id "
                "WHERE c.document_version_id=%s",
                (version_id,),
            )
            assert cur.fetchone() == (114,)
    finally:
        conn.rollback()
        conn.close()

    # Independent database connection proves rollback and unchanged gate.
    with psycopg.connect(dsn, autocommit=False) as check:
        with check.cursor() as cur:
            cur.execute("SELECT writes_enabled FROM rag_v2.write_gate WHERE id=true")
            assert cur.fetchone() == (False,)
            cur.execute(
                "SELECT (SELECT count(*) FROM rag_v2.document), "
                "(SELECT count(*) FROM rag_v2.document_source), "
                "(SELECT count(*) FROM rag_v2.document_version), "
                "(SELECT count(*) FROM rag_v2.processing_job), "
                "(SELECT count(*) FROM rag_v2.chunk), "
                "(SELECT count(*) FROM rag_v2.chunk_embedding)"
            )
            assert cur.fetchone() == (0, 0, 0, 0, 0, 0)
        check.rollback()
