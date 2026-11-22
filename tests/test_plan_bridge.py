"""Pipe-Grenztests ohne Netzwerk oder Datenbank."""

import hashlib
import io
import json
import struct
from types import SimpleNamespace

import pytest

from retro_rag.importer import plan_bridge
from retro_rag.importer.staging import PlannedChange
from retro_rag.importer.webdav import RemoteFile


def fixture():
    data = b"---\ntitle: Test\n---\n# Content\n"
    sha = hashlib.sha256(data).hexdigest()
    file = RemoteFile(
        source_key="480",
        instance_id="poseidon-nextcloud",
        uri="http://127.0.0.1:8080/remote.php/dav/files/nina/test.md",
        name="test.md", etag='"etag"', byte_size=len(data),
        content_type="text/markdown",
    )
    return file, data, sha


class FakeDAV:
    def __init__(self, remote, data):
        self.remote = remote
        self.data = data

    def list_files(self):
        return [self.remote]

    def download(self, file, max_bytes):
        assert file == self.remote
        assert max_bytes == plan_bridge.MAX_BYTES
        return self.data


def encode(monkeypatch, remote, data, sha):
    stream = io.BytesIO()
    monkeypatch.setattr(plan_bridge.sys, "stdout", SimpleNamespace(buffer=stream))
    plan_bridge.fetch_to_pipe(FakeDAV(remote, data), remote.source_key, sha)
    return stream.getvalue()


def test_roundtrip_pipe(monkeypatch):
    remote, data, sha = fixture()
    blob = encode(monkeypatch, remote, data, sha)
    result, output = plan_bridge.read_pipe(io.BytesIO(blob), sha)
    assert result == remote
    assert output == data


def test_fetch_rejects_wrong_hash_before_output(monkeypatch):
    remote, data, _sha = fixture()
    stream = io.BytesIO()
    monkeypatch.setattr(plan_bridge.sys, "stdout", SimpleNamespace(buffer=stream))
    with pytest.raises(ValueError, match="SHA-256"):
        plan_bridge.fetch_to_pipe(FakeDAV(remote, data), remote.source_key, "0" * 64)
    assert stream.getvalue() == b""


def test_fetch_rejects_missing_fileid(monkeypatch):
    remote, data, sha = fixture()
    stream = io.BytesIO()
    monkeypatch.setattr(plan_bridge.sys, "stdout", SimpleNamespace(buffer=stream))
    with pytest.raises(ValueError, match="nicht eindeutig"):
        plan_bridge.fetch_to_pipe(FakeDAV(remote, data), "999", sha)
    assert stream.getvalue() == b""


@pytest.mark.parametrize("tail", [b"extra", b"\x00"])
def test_pipe_rejects_trailing_bytes(monkeypatch, tail):
    remote, data, sha = fixture()
    payload = encode(monkeypatch, remote, data, sha)
    with pytest.raises(ValueError, match="Pipe-Daten"):
        plan_bridge.read_pipe(io.BytesIO(payload + tail), sha)


def test_pipe_rejects_truncation(monkeypatch):
    remote, data, sha = fixture()
    payload = encode(monkeypatch, remote, data, sha)
    with pytest.raises(ValueError, match="Pipe-Daten"):
        plan_bridge.read_pipe(io.BytesIO(payload[:-2]), sha)


def test_pipe_rejects_corrupt_content(monkeypatch):
    remote, data, sha = fixture()
    payload = encode(monkeypatch, remote, data, sha)
    with pytest.raises(ValueError, match="SHA-256"):
        plan_bridge.read_pipe(io.BytesIO(payload[:-1] + b"!"), sha)


def test_pipe_rejects_oversized_header():
    with pytest.raises(ValueError, match="Metadatenlänge"):
        plan_bridge.read_pipe(
            io.BytesIO(struct.pack("!I", plan_bridge.MAX_HEADER + 1)),
            "0" * 64,
        )


def test_pipe_rejects_oversized_payload():
    meta = {"byte_size": plan_bridge.MAX_BYTES + 1}
    header = json.dumps(meta).encode()
    data = struct.pack("!I", len(header)) + header
    with pytest.raises(ValueError):
        plan_bridge.read_pipe(io.BytesIO(data), "0" * 64)


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, _params=None):
        self.conn.queries.append(sql)

    def fetchone(self):
        query = self.conn.queries[-1]
        if "current_database()" in query:
            return ("retro_rag_v2_test", "rag_v2_importer_login")
        if "writes_enabled" in query:
            return (False,)
        raise AssertionError(query)


class FakeDB:
    def __init__(self):
        self.queries = []
        self.rollbacks = 0

    def cursor(self):
        return FakeCursor(self)

    def rollback(self):
        self.rollbacks += 1


def test_plan_is_read_only(monkeypatch):
    remote, data, sha = fixture()
    payload = encode(monkeypatch, remote, data, sha)
    db = FakeDB()

    def fake_plan(_conn, file, content):
        assert file == remote
        assert content == data
        return PlannedChange("new", file.source_key, file.name, sha)

    monkeypatch.setattr(plan_bridge, "plan_file", fake_plan)
    result = plan_bridge.plan_from_pipe(db, io.BytesIO(payload), sha)
    assert result.action == "new"
    assert db.queries[0] == "BEGIN READ ONLY"
    assert db.rollbacks == 1


def test_plan_rejects_bad_session(monkeypatch):
    remote, data, sha = fixture()
    payload = encode(monkeypatch, remote, data, sha)
    db = FakeDB()
    original = db.cursor

    def wrong_cursor():
        cur = original()
        cur.fetchone = lambda: ("retro_rag_v2_test", "postgres")
        return cur

    db.cursor = wrong_cursor
    with pytest.raises(RuntimeError, match="Importer"):
        plan_bridge.plan_from_pipe(db, io.BytesIO(payload), sha)
