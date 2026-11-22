"""Schreibfreie Regressionstests für den neuen Job-Adapter."""

import hashlib
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pymupdf
import pytest
from psycopg.pq import TransactionStatus

from retro_rag.importer.contract import Chunk, Document, ImportContract, Source
from retro_rag.importer.job_pipeline import (
    PreparedJob,
    persist_contract,
    prepare_job,
    resolve_archived_original,
)


class FakeCursor:
    def __init__(self, db):
        self.db = db
        self.query = ""

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, _params=None):
        self.query = query

    def fetchone(self):
        if "current_database()" in self.query:
            return ("retro_rag_v2_test",)
        if "JOIN rag_v2.document_version" in self.query:
            return self.db.record
        if "step_name='source_archived'" in self.query:
            return (1,)
        raise AssertionError("Unerwartete SQL-Abfrage")


class FakeConnection:
    def __init__(self, record):
        self.record = record
        self.info = SimpleNamespace(transaction_status=TransactionStatus.IDLE)

    def cursor(self):
        return FakeCursor(self)


def make_original(tmp_path: Path, *, text: str = "AGP V6800 Series"):
    folder = tmp_path / "originals"
    folder.mkdir()
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_text((30, 70), text)
        raw = pdf.tobytes()
    sha = hashlib.sha256(raw).hexdigest()
    path = folder / sha[:2] / (sha + ".pdf")
    path.parent.mkdir()
    path.write_bytes(raw)
    return folder, path, sha


def make_job(tmp_path):
    folder, path, sha = make_original(tmp_path)
    version = uuid4()
    job_id = uuid4()
    row = ("pending", version, sha, "manual.pdf", path.as_uri(), "discovered")
    return FakeConnection(row), job_id, version, folder, path, sha


def test_archive_path_must_stay_under_root(tmp_path):
    root = tmp_path / "originals"
    root.mkdir()
    good = root / "page.pdf"
    good.write_bytes(b"content")
    assert resolve_archived_original(good.as_uri(), root) == good


def test_archive_escape_is_rejected(tmp_path):
    root = tmp_path / "originals"
    root.mkdir()
    other = tmp_path / "other.pdf"
    other.write_bytes(b"content")
    with pytest.raises(ValueError, match="unter dem Archiv"):
        resolve_archived_original(other.as_uri(), root)


def test_archive_symlink_escape_is_rejected(tmp_path):
    root = tmp_path / "originals"
    root.mkdir()
    other = tmp_path / "other.pdf"
    other.write_bytes(b"content")
    shortcut = root / "shortcut.pdf"
    shortcut.symlink_to(other)
    with pytest.raises(ValueError, match="unter dem Archiv"):
        resolve_archived_original(shortcut.as_uri(), root)


@pytest.mark.parametrize("uri", [
    "https://example.org/example.pdf",
    "file://example.org/test.pdf",
    "file:///tmp/f.pdf?download=1",
])
def test_archive_uri_rejects_external_sources(tmp_path, uri):
    with pytest.raises(ValueError):
        resolve_archived_original(uri, tmp_path)


def test_prepare_job_from_sha_verified_pdf(tmp_path):
    conn, job_id, version, root, path, sha = make_job(tmp_path)
    result = prepare_job(conn, job_id, root)
    assert result.job_id == job_id
    assert result.version_id == version
    assert result.original_path == path
    assert result.contract.source.content_hash == sha
    assert result.contract.source.source_id == "document_version:" + str(version)
    assert result.contract.chunks
    assert result.contract.indexing_allowed is False


def test_prepare_job_refuses_corrupt_archive(tmp_path):
    conn, job_id, _version, root, path, _sha = make_job(tmp_path)
    path.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="SHA-256"):
        prepare_job(conn, job_id, root)


def test_prepare_job_refuses_finished_job(tmp_path):
    conn, job_id, version, root, path, sha = make_job(tmp_path)
    conn.record = ("completed", version, sha, "manual.pdf", path.as_uri(), "indexed")
    with pytest.raises(ValueError, match="Ausgangszustand"):
        prepare_job(conn, job_id, root)


def test_persist_contract_refuses_missing_transaction(tmp_path):
    conn, job_id, version, root, path, sha = make_job(tmp_path)
    chunk_text = "ASUS AGP 4X"
    contract = ImportContract(
        source=Source(
            source_id="document_version:" + str(version),
            location=str(path),
            content_hash=sha,
            kind="pdf",
        ),
        document=Document(title="Test", document_type="manual"),
        chunks=[
            Chunk(
                ordinal=0,
                text=chunk_text,
                chunk_hash=hashlib.sha256(chunk_text.encode("utf-8")).hexdigest(),
            ),
        ],
    )
    prepared = PreparedJob(job_id, version, path, contract)
    with pytest.raises(RuntimeError, match="Transaktion"):
        persist_contract(conn, prepared)
