from pathlib import Path

import pytest

from retro_rag.importer import staging


def test_atomic_archive_success(tmp_path):
    data = b"%PDF-1.4\nTestdocument\n"

    uri = staging.archive_original(tmp_path, data, "test.pdf")
    path = Path(uri.removeprefix("file://"))

    assert path.read_bytes() == data
    assert path.name == staging.digest(data) + ".pdf"
    assert staging.archive_original(tmp_path, data, "test.pdf") == uri
    assert len(list(tmp_path.rglob("*.pdf"))) == 1
    assert not list(tmp_path.rglob("*.tmp"))


def test_atomic_archive_write_failure(monkeypatch, tmp_path):
    data = b"%PDF-1.4\nInterrupted\n"

    def fail_fsync(fd):
        raise OSError("Simulierter Schreibfehler")

    monkeypatch.setattr(staging.os, "fsync", fail_fsync)

    with pytest.raises(OSError, match="Schreibfehler"):
        staging.archive_original(tmp_path, data, "test.pdf")

    assert not list(tmp_path.rglob("*.pdf"))
    assert not list(tmp_path.rglob("*.tmp"))


def test_atomic_archive_detects_corruption(tmp_path):
    data = b"%PDF-1.4\nOriginal\n"
    uri = staging.archive_original(tmp_path, data, "test.pdf")
    path = Path(uri.removeprefix("file://"))

    path.write_bytes(b"corrupted")

    with pytest.raises(RuntimeError, match="beschädigt"):
        staging.archive_original(tmp_path, data, "test.pdf")

    assert path.read_bytes() == b"corrupted"
