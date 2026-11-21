"""Tests for the single-source read-only WebDAV -> PDF adapter bridge."""

import hashlib
from pathlib import Path

import pytest

from retro_rag.importer.contract import Chunk, Document, ImportContract, Source
from retro_rag.importer.pdf_preview_cli import preview_pdf
from retro_rag.importer.webdav import RemoteFile

PDF_BYTES = b"%PDF-test-payload"
PDF_HASH = hashlib.sha256(PDF_BYTES).hexdigest()


class FakeWebDAV:
    def __init__(self, files=None, data=PDF_BYTES):
        self.files = files if files is not None else [remote()]
        self.data = data
        self.downloads = []

    def list_files(self):
        return self.files

    def download(self, file, max_bytes):
        self.downloads.append((file.source_key, max_bytes))
        return self.data


def remote(key="172", name="cubx.pdf"):
    return RemoteFile(
        source_key=key,
        uri="http://127.0.0.1:8080/remote.php/dav/files/test/" + name,
        name=name,
        etag='"etag"',
        byte_size=len(PDF_BYTES),
        content_type="application/pdf",
        instance_id="poseidon-nextcloud",
    )


def fake_contract(path: Path, source_id: str, **kwargs) -> ImportContract:
    assert path.is_file() and path.read_bytes() == PDF_BYTES
    assert path.stat().st_mode & 0o777 == 0o600
    assert source_id == "nextcloud:poseidon-nextcloud:172"
    return ImportContract(
        source=Source(
            source_id=source_id,
            location=str(path),
            content_hash=PDF_HASH,
            kind="pdf",
        ),
        document=Document(
            title="Test", document_type="manual",
            metadata={"page_count": 1, "ocr_pages": [], "ocr_failed_pages": []},
        ),
        chunks=[Chunk(
            ordinal=0, text="CUBX", chunk_hash=hashlib.sha256(b"CUBX").hexdigest(),
            page=1,
        )],
        indexing_allowed=False,
    )


def test_preview_selected_source_is_not_published(monkeypatch):
    from retro_rag.importer import pdf_preview_cli

    visited = []

    def read(path, source_id, **kwargs):
        visited.append(path)
        return fake_contract(path, source_id, **kwargs)

    monkeypatch.setattr(pdf_preview_cli, "read_pdf", read)
    client = FakeWebDAV(files=[remote(), remote("173", "other.pdf")])
    report = preview_pdf(client, "172", PDF_HASH)
    assert client.downloads == [("172", 50 * 1024 * 1024)]
    assert report["chunk_count"] == 1
    assert report["indexing_allowed"] is False
    assert report["fact_proposal_count"] == 0
    assert visited and not visited[0].exists()


def test_hash_mismatch_blocks_pdf_parser(monkeypatch):
    from retro_rag.importer import pdf_preview_cli

    monkeypatch.setattr(
        pdf_preview_cli, "read_pdf", lambda *a, **k: pytest.fail("Parser trotz Hashfehler")
    )
    with pytest.raises(RuntimeError, match="SHA-256"):
        preview_pdf(FakeWebDAV(), "172", "0" * 64)


def test_missing_or_ambiguous_fileid_blocks_download():
    client = FakeWebDAV(files=[remote(), remote()])
    with pytest.raises(RuntimeError, match="nicht eindeutig"):
        preview_pdf(client, "172", PDF_HASH)
    with pytest.raises(RuntimeError, match="nicht eindeutig"):
        preview_pdf(FakeWebDAV(files=[remote()]), "999", PDF_HASH)
    assert client.downloads == []


def test_only_pdf_and_valid_size_allowed():
    client = FakeWebDAV(files=[remote(name="board.md")])
    with pytest.raises(ValueError, match="PDF"):
        preview_pdf(client, "172", PDF_HASH)
    assert client.downloads == []
    with pytest.raises(ValueError, match="Größenlimit"):
        preview_pdf(FakeWebDAV(), "172", PDF_HASH, max_bytes=50 * 1024 * 1024 + 1)


def test_no_ocr_page_without_auto():
    client = FakeWebDAV()
    with pytest.raises(ValueError, match="OCR-Seiten"):
        preview_pdf(client, "172", PDF_HASH, ocr_pages={1})
    assert client.downloads == []


def test_failed_parser_removes_temp_original(monkeypatch):
    from retro_rag.importer import pdf_preview_cli

    visited = []

    def explode(path, *args, **kwargs):
        visited.append(path)
        assert path.exists()
        raise ValueError("PDF unlesbar")

    monkeypatch.setattr(pdf_preview_cli, "read_pdf", explode)
    with pytest.raises(ValueError, match="unlesbar"):
        preview_pdf(FakeWebDAV(), "172", PDF_HASH)
    assert visited and not visited[0].exists()


def test_non_publishable_contract_enforced(monkeypatch):
    from retro_rag.importer import pdf_preview_cli

    def published(path, source_id, **kwargs):
        contract = fake_contract(path, source_id, **kwargs)
        return contract.model_copy(update={"indexing_allowed": True})

    monkeypatch.setattr(pdf_preview_cli, "read_pdf", published)
    with pytest.raises(RuntimeError, match="nicht indexierbar"):
        preview_pdf(FakeWebDAV(), "172", PDF_HASH)


def test_invalid_signature_rejected_before_parser(monkeypatch):
    from retro_rag.importer import pdf_preview_cli

    monkeypatch.setattr(
        pdf_preview_cli, "read_pdf", lambda *a, **k: pytest.fail("Parser trotz PDF-Signatur")
    )
    client = FakeWebDAV(data=b"not a pdf")
    with pytest.raises(ValueError, match="Signatur"):
        preview_pdf(client, "172", hashlib.sha256(client.data).hexdigest())
