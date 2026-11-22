"""Real-document PR13 E2E smoke test: only isolated DB, uncommitted transaction.

Explicit opt-in. This test does not fetch WebDAV data; SOURCE_PATH must be a
byte-for-byte, SHA-verified local copy of Nextcloud fileid 480.
"""
import hashlib
import json
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

EXPECTED_SHA = "70e1b0ce4dc3d7cc3497763c4e907f1f3df65843cb3b5cef7c38bf8ee66efab6"


def embed(text):
    url = os.environ["RETRO_V2_E2E_EMBED_URL"]
    parts = urlsplit(url)
    if (parts.scheme, parts.hostname, parts.path) != ("http", "127.0.0.1", "/api/embed"):
        raise RuntimeError("Only local Ollama /api/embed is allowed")
    model = os.getenv("RETRO_V2_E2E_EMBED_MODEL", "nomic-embed-text")
    req = Request(
        url, data=json.dumps({"model": model, "input": text}).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urlopen(req, timeout=90) as response:
        vectors = json.load(response).get("embeddings")
    if not isinstance(vectors, list) or len(vectors) != 1 or not vectors[0]:
        raise RuntimeError("No usable Ollama embedding")
    vector = vectors[0]
    if not all(isinstance(v, (float, int)) and not isinstance(v, bool) for v in vector):
        raise RuntimeError("Invalid embedding values")
    return model, vector


def test_real_md_full_pipeline_isolated_rollback(tmp_path):
    dsn = os.getenv("RETRO_V2_E2E_ISOLATED_DSN")
    path = os.getenv("RETRO_V2_E2E_SOURCE_PATH")
    uri = os.getenv("RETRO_V2_E2E_SOURCE_URI")
    if not all((dsn, path, uri, os.getenv("RETRO_V2_E2E_EMBED_URL"))):
        pytest.skip("Requires isolated DB, SHA-pinned WebDAV bytes/URI, local Ollama")

    source = Path(path).resolve(strict=True)
    if source.name != "test-mainboard.md" or not source.is_file():
        raise RuntimeError("Only verified Nextcloud test-mainboard.md is allowed")
    data = source.read_bytes()
    if hashlib.sha256(data).hexdigest() != EXPECTED_SHA:
        raise RuntimeError("Source SHA-256 mismatch")
    url = urlsplit(uri)
    if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password:
        raise RuntimeError("Invalid WebDAV source URI")
    remote = RemoteFile(
        source_key="480", instance_id="poseidon-nextcloud", uri=uri,
        name=source.name, etag=None, byte_size=len(data), content_type="text/markdown",
    )
    archive = tmp_path / "isolated-originals"

    conn = psycopg.connect(dsn, autocommit=False)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database(), current_setting('cluster_name'), session_user")
            if cur.fetchone() != (
                "retro_rag_v2_test", "retro-rag-v2-pr13-e2e-isolated",
                "rag_v2_migrator_login",
            ):
                raise RuntimeError("Refusing non-isolated database or wrong role")
            cur.execute("SELECT max(version) FROM rag_v2.schema_migration")
            if cur.fetchone() != (6,):
                raise RuntimeError("Migration 0006 required")
            cur.execute("SELECT writes_enabled FROM rag_v2.write_gate WHERE id=true")
            if cur.fetchone() != (False,):
                raise RuntimeError("Closed write gate required")
            cur.execute("SET LOCAL ROLE rag_v2_migrator")
            cur.execute(
                "UPDATE rag_v2.write_gate SET writes_enabled=true, "
                "reason='PR13 isolated E2E rollback only' WHERE id=true"
            )

        assert stage_file(conn, remote, data, archive).action == "new"
        with conn.cursor() as cur:
            cur.execute(
                """SELECT v.id,j.id FROM rag_v2.document_source s
                JOIN rag_v2.document_version v ON v.document_id=s.document_id
                JOIN rag_v2.processing_job j ON j.document_version_id=v.id
                WHERE s.source_system='nextcloud' AND s.source_instance=%s
                AND s.source_key=%s AND v.content_hash=%s""",
                (remote.instance_id, remote.source_key, EXPECTED_SHA),
            )
            version_id, job_id = cur.fetchone()

        prepared = prepare_job(conn, job_id, archive)
        assert prepared.contract.chunks
        # Die Markdown-Vorstufe meldet die noch fehlenden fachlichen Prüfungen.
        # Der E2E-Test validiert nur die technische Pipeline (Rollback),
        # nicht die Freigabe eines Dokuments für den produktiven Index.
        assert prepared.contract.warnings == [
            "Quellenautorisierung, Schema- und Konfliktprüfung sind noch nicht implementiert."
        ]
        assert not prepared.contract.indexing_allowed
        assert not prepared.contract.fact_proposals
        assert _persist_contract_rows(conn, prepared) == len(prepared.contract.chunks)

        with conn.cursor() as cur:
            cur.execute(
                "SELECT id,content FROM rag_v2.chunk "
                "WHERE document_version_id=%s ORDER BY sequence_no",
                (version_id,),
            )
            chunks = cur.fetchall()
        assert chunks
        model, first = embed(chunks[0][1])
        dimensions = len(first)
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO rag_v2.embedding_model(model_name,dimensions) "
                "VALUES (%s,%s) RETURNING id",
                (model + "-pr13-e2e", dimensions),
            )
            model_id = cur.fetchone()[0]
            for index, (chunk_id, text) in enumerate(chunks):
                vector = first if index == 0 else embed(text)[1]
                assert len(vector) == dimensions
                cur.execute(
                    """INSERT INTO rag_v2.chunk_embedding
                    (chunk_id,embedding_model_id,dimensions,embedding)
                    VALUES (%s,%s,%s,%s::public.vector)""",
                    (chunk_id, model_id, dimensions, json.dumps(vector)),
                )
            cur.execute(
                "UPDATE rag_v2.processing_job SET status='completed', "
                "completed_at=now() WHERE id=%s", (job_id,),
            )
            cur.execute(
                "UPDATE rag_v2.document_version SET processing_state='indexed' "
                "WHERE id=%s", (version_id,),
            )
        assert activate_version(conn, version_id).changed
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM rag_v2.chunk_embedding e "
                "JOIN rag_v2.chunk c ON c.id=e.chunk_id "
                "WHERE c.document_version_id=%s", (version_id,),
            )
            assert cur.fetchone() == (len(chunks),)
            cur.execute("SELECT state FROM rag_v2.document_version WHERE id=%s", (version_id,))
            assert cur.fetchone() == ("active",)
    finally:
        conn.rollback()
        conn.close()

    with psycopg.connect(dsn, autocommit=False) as check:
        with check.cursor() as cur:
            cur.execute("SELECT writes_enabled FROM rag_v2.write_gate WHERE id=true")
            assert cur.fetchone() == (False,)
            cur.execute(
                "SELECT count(*) FROM rag_v2.document_source "
                "WHERE source_system='nextcloud' AND source_instance=%s AND source_key=%s",
                (remote.instance_id, remote.source_key),
            )
            assert cur.fetchone() == (0,)
        check.rollback()
