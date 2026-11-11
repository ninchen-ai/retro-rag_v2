"""Fehlerfalltests für einen kontrollierten Einzeldatei-WebDAV-Apply."""

from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError

import pytest

from retro_rag.importer import staging, webdav
from retro_rag.importer.webdav import RemoteFile, WebDAV

ROOT = "http://127.0.0.1:8080/remote.php/dav/files/nina/Retro-Computing/"


def remote(*, size=4, etag='"etag-1"'):
    return RemoteFile(
        source_key="777",
        instance_id="test-nc",
        uri=ROOT + "Hardware/test.md",
        name="test.md",
        etag=etag,
        byte_size=size,
        content_type="text/markdown",
    )


class FakeResponse:
    def __init__(self, data, *, headers=None, fail_after=None):
        self.data = BytesIO(data)
        self.headers = headers or {}
        self.fail_after = fail_after
        self.read_count = 0

    def read(self, count):
        self.read_count += 1
        if self.fail_after is not None and self.read_count > self.fail_after:
            raise ConnectionResetError("connection reset while downloading")
        return self.data.read(count)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeOpener:
    def __init__(self, response):
        self.response = response
        self.request = None

    def open(self, request, timeout):
        self.request = request
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def client_with_response(monkeypatch, response):
    opener = FakeOpener(response)
    monkeypatch.setattr(webdav, "_no_redirect_opener", lambda: opener)
    return WebDAV(ROOT, "nina", "secret", instance_id="test-nc"), opener


def test_get_uses_conditional_if_match(monkeypatch):
    client, opener = client_with_response(
        monkeypatch, FakeResponse(b"test", headers={"ETag": '"etag-1"', "Content-Length": "4"})
    )
    assert client.download(remote()) == b"test"
    assert opener.request.get_header("If-match") == '"etag-1"'


def test_get_rejects_etag_change(monkeypatch):
    client, _ = client_with_response(
        monkeypatch, FakeResponse(b"test", headers={"ETag": '"changed"'})
    )
    with pytest.raises(RuntimeError, match="ETag"):
        client.download(remote())


def test_get_rejects_http_precondition_failure(monkeypatch):
    error = HTTPError(ROOT + "Hardware/test.md", 412, "precondition failed", {}, None)
    client, _ = client_with_response(monkeypatch, error)
    with pytest.raises(HTTPError) as exc:
        client.download(remote())
    assert exc.value.code == 412


def test_get_rejects_short_response(monkeypatch):
    client, _ = client_with_response(
        monkeypatch, FakeResponse(b"tes", headers={"Content-Length": "4"})
    )
    with pytest.raises(RuntimeError, match="Unvollständiger"):
        client.download(remote())


def test_get_rejects_connection_reset_without_returning_partial_data(monkeypatch):
    client, _ = client_with_response(
        monkeypatch, FakeResponse(b"x" * (70 * 1024), fail_after=1)
    )
    with pytest.raises(ConnectionResetError):
        client.download(remote(size=None))


def test_get_rejects_stream_exceeding_limit(monkeypatch):
    client, _ = client_with_response(monkeypatch, FakeResponse(b"12345"))
    with pytest.raises(ValueError, match="Größenlimit"):
        client.download(remote(size=None), max_bytes=4)


def test_get_rejects_reported_size_change(monkeypatch):
    client, _ = client_with_response(monkeypatch, FakeResponse(b"changed"))
    with pytest.raises(RuntimeError, match="Dateigröße"):
        client.download(remote(size=4))


def test_get_rejects_another_instance(monkeypatch):
    client, _ = client_with_response(monkeypatch, FakeResponse(b"test"))
    other = RemoteFile(**{**remote().__dict__, "instance_id": "another"})
    with pytest.raises(ValueError, match="Instanzkennung"):
        client.download(other)


def test_archive_uses_atomic_publish(tmp_path, monkeypatch):
    """Während temp-Schreibphase existiert noch kein endgültiges Archiv."""
    real_link = staging.os.link
    observed = []

    def inspect_then_link(source, destination):
        assert Path(source).exists()
        assert not Path(destination).exists()
        observed.append(True)
        return real_link(source, destination)

    monkeypatch.setattr(staging.os, "link", inspect_then_link)
    uri = staging.archive_original(tmp_path, b"test", "test.md")
    assert observed == [True]
    assert Path(uri.removeprefix("file://")).read_bytes() == b"test"
    assert not list(tmp_path.rglob(".pending-*"))


def test_archive_failure_never_publishes_partial_target(tmp_path, monkeypatch):
    def crash_before_publish(*args, **kwargs):
        raise OSError("simulated failure before publish")

    monkeypatch.setattr(staging.os, "link", crash_before_publish)
    with pytest.raises(OSError, match="simulated"):
        staging.archive_original(tmp_path, b"test", "test.md")
    assert not list(tmp_path.rglob("*.md"))
    assert not list(tmp_path.rglob(".pending-*"))


def test_archive_replay_after_publish_is_idempotent(tmp_path):
    first = staging.archive_original(tmp_path, b"test", "test.md")
    second = staging.archive_original(tmp_path, b"test", "test.md")
    assert first == second
    assert len(list(tmp_path.rglob("*.md"))) == 1


def test_archive_detects_corrupt_preexisting_target(tmp_path):
    value = staging.digest(b"test")
    target = tmp_path / value[:2] / (value + ".md")
    target.parent.mkdir(parents=True)
    target.write_bytes(b"broken")
    with pytest.raises(RuntimeError, match="Hash"):
        staging.archive_original(tmp_path, b"test", "test.md")
