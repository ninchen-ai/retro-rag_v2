"""Echter Importer-/HBA-/Gate-Negativtest, ausschließlich V2-Test und Rollback.

Ohne RETRO_V2_JOB_TEST_DSN wird dieser Test übersprungen. Er öffnet
niemals das Gate, führt keine Migration aus und schreibt keine DB-Zeilen.
"""

import hashlib
import os
from uuid import uuid4

import psycopg
import pytest

from retro_rag.importer.contract import Chunk, Document, ImportContract, Source
from retro_rag.importer.job_pipeline import PreparedJob, persist_contract


def test_importer_job_persistence_rejected_by_closed_gate(tmp_path):
    dsn = os.environ.get("RETRO_V2_JOB_TEST_DSN")
    if not dsn:
        pytest.skip("RETRO_V2_JOB_TEST_DSN nicht gesetzt")

    # Kein Nextcloud-Zugriff und keine Änderung am Originalarchiv.
    original = tmp_path / "synthetic.md"
    original.write_bytes(b"synthetic test data; no import")
    original_hash = hashlib.sha256(original.read_bytes()).hexdigest()
    chunk_text = "# Synthetischer Test\nNur der Gate-Negativtest."
    contract = ImportContract(
        source=Source(
            source_id="document_version:" + str(version_id := uuid4()),
            location=str(original),
            content_hash=original_hash,
            kind="markdown",
        ),
        document=Document(title="Test", document_type="markdown"),
        chunks=[
            Chunk(
                ordinal=0,
                text=chunk_text,
                chunk_hash=hashlib.sha256(chunk_text.encode("utf-8")).hexdigest(),
            ),
        ],
    )
    prepared = PreparedJob(uuid4(), version_id, original, contract)

    with psycopg.connect(dsn, autocommit=False) as conn:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT current_database(), session_user")
                assert cur.fetchone() == ("retro_rag_v2_test", "rag_v2_importer_login")
                cur.execute("SELECT writes_enabled FROM rag_v2.write_gate WHERE id=true")
                assert cur.fetchone() == (False,)

            with pytest.raises(
                psycopg.errors.InsufficientPrivilege,
                match="V2-Schreibsperre ist geschlossen",
            ):
                persist_contract(conn, prepared)

            conn.rollback()
            with conn.cursor() as cur:
                cur.execute("SELECT writes_enabled FROM rag_v2.write_gate WHERE id=true")
                assert cur.fetchone() == (False,)
        finally:
            # Kein Commit, auch bei fehlschlagenden Assertions.
            conn.rollback()
