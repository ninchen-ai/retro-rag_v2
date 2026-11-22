"""Fail-closed regression tests for the restartable import worker.

Database lease/concurrency behavior requires a separate Poseidon integration run.
"""
import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from retro_rag.importer import worker


def archived(tmp_path, content=b"archived markdown"):
    sha = hashlib.sha256(content).hexdigest()
    folder = tmp_path / sha[:2]
    folder.mkdir()
    path = folder / (sha + ".md")
    path.write_bytes(content)
    return path, sha


def test_verified_original_accepts_unchanged_archive(tmp_path):
    path, sha = archived(tmp_path)
    assert worker.verified_original(path.as_uri(), tmp_path, sha) == path


def test_verified_original_rejects_modified_archive(tmp_path):
    path, sha = archived(tmp_path)
    path.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="SHA-256"):
        worker.verified_original(path.as_uri(), tmp_path, sha)


def test_verified_original_rejects_path_outside_archive(tmp_path):
    root = tmp_path / "archive"
    root.mkdir()
    outsider = tmp_path / "secret.md"
    outsider.write_bytes(b"secret")
    sha = hashlib.sha256(b"secret").hexdigest()
    with pytest.raises(ValueError, match="außerhalb"):
        worker.verified_original(outsider.as_uri(), root, sha)


def test_verified_original_rejects_symlink(tmp_path):
    path, sha = archived(tmp_path)
    symlink = path.with_name("linked.md")
    symlink.symlink_to(path)
    with pytest.raises(ValueError, match="Symlink"):
        worker.verified_original(symlink.as_uri(), tmp_path, sha)


def test_verified_original_rejects_non_file_uri(tmp_path):
    with pytest.raises(ValueError, match="file:"):
        worker.verified_original("https://example.com/a.pdf", tmp_path, "a" * 64)


def test_no_work_is_noop(monkeypatch, tmp_path):
    monkeypatch.setattr(worker, "claim_job", lambda *_: None)
    assert worker.process_one(object(), tmp_path, "worker-1") is False


def test_pdf_with_unverified_chunks_fails_before_db_write():
    contract = SimpleNamespace(
        source=SimpleNamespace(content_hash="a" * 64, kind="pdf"),
        document=SimpleNamespace(metadata={}),
        indexing_allowed=False,
        fact_proposals=[],
        chunks=[object()],
        warnings=["Page requires OCR review"],
    )
    job = ("job-1", "version-1", "a" * 64, "file:///unused.pdf", "manual.pdf")
    with pytest.raises(ValueError, match="PDF-Warnungen erfordern vor Persistierung ein Review"):
        worker.finish_job(object(), job, "worker-1", Path("/does-not-exist"), contract)


def test_fact_proposals_fail_before_db_write():
    contract = SimpleNamespace(
        source=SimpleNamespace(content_hash="a" * 64, kind="markdown"),
        document=SimpleNamespace(metadata={}),
        indexing_allowed=False,
        fact_proposals=[{"unreviewed": True}],
        chunks=[object()],
        warnings=[],
    )
    job = ("job-1", "version-1", "a" * 64, "file:///unused.md", "doc.md")
    with pytest.raises(ValueError, match="Verarbeitungsadapter darf keine Freigaben übernehmen"):
        worker.finish_job(object(), job, "worker-1", Path("/does-not-exist"), contract)


def test_worker_failure_is_isolated_and_reported(monkeypatch, tmp_path):
    job = ("job-1", "version-1", "a" * 64, "file:///missing.md", "missing.md")
    events = []
    monkeypatch.setattr(worker, "claim_job", lambda *_: job)
    monkeypatch.setattr(worker, "fail_job",
                        lambda _c, job_id, _o, _exc: events.append(job_id))
    with pytest.raises(ValueError):
        worker.process_one(object(), tmp_path, "worker-1")
    assert events == ["job-1"]


def test_worker_keeps_incomplete_job_until_embeddings():
    source = Path(worker.__file__).read_text()
    assert "_persist_contract_rows(conn, prepared, lease_owner=owner)" in source
    assert "activate_version(" not in source
    assert "processing_state='indexed'" not in source
    assert "SET status='completed'" not in source
    assert "step_name='text_extracted'" in source
    assert "step_name='source_archived'" in source


def test_claim_job_requires_unextracted_document():
    source = Path(worker.__file__).read_text()
    assert "FOR UPDATE OF j SKIP LOCKED LIMIT 1" in source
    assert "s.step_name='text_extracted'" in source
    assert "j.lease_until < now()" in source
    assert "j.attempts < j.max_attempts" in source
