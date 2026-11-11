"""CLI-Grenztests: kein impliziter Massenimport und kein Apply bei Fehlern."""

import sys

import pytest

from retro_rag.importer import sync_cli
from retro_rag.importer.webdav import RemoteFile


def file(source_key, name):
    return RemoteFile(
        source_key=source_key,
        instance_id="test-nc",
        uri=f"http://127.0.0.1:8080/remote.php/dav/files/u/{name}",
        name=name,
        etag='"test"',
        byte_size=4,
        content_type="text/markdown",
    )


class FakeCursor:
    def __init__(self):
        self.answer = None

    def execute(self, statement, params=None):
        if "current_database()" in statement:
            self.answer = ("retro_rag_v2_test", "rag_v2.document_source")
        elif "schema_migration" in statement:
            self.answer = (True,)
        else:
            raise AssertionError(f"Unbekanntes SQL: {statement}")

    def fetchone(self):
        return self.answer

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeConnection:
    def __init__(self):
        self.rollbacks = 0

    def cursor(self):
        return FakeCursor()

    def rollback(self):
        self.rollbacks += 1

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeWebDAV:
    def __init__(self, *args, **kwargs):
        self.download_calls = []

    def list_files(self):
        return [file("777", "selected.md"), file("888", "other.md")]

    def download(self, candidate, max_bytes):
        self.download_calls.append(candidate.source_key)
        return b"test"


def setup(monkeypatch, args):
    monkeypatch.setattr(sys, "argv", ["sync_cli", *args])
    for key, value in {
        "RETRO_V2_WEBDAV_URL": "http://127.0.0.1:8080/remote.php/dav/files/u/",
        "RETRO_V2_WEBDAV_USER": "u",
        "RETRO_V2_WEBDAV_APP_PASSWORD": "secret",
        "RETRO_V2_NEXTCLOUD_INSTANCE_ID": "test-nc",
        "RETRO_V2_DATABASE_DSN": "host=127.0.0.1 dbname=retro_rag_v2_test",
    }.items():
        monkeypatch.setenv(key, value)
    dav = FakeWebDAV()
    monkeypatch.setattr(sync_cli, "WebDAV", lambda *a, **k: dav)
    monkeypatch.setattr(sync_cli.psycopg, "connect", lambda *a, **k: FakeConnection())
    return dav


@pytest.mark.parametrize("args", [
    ["--apply", "--archive-root", "/tmp/retro-test"],
    ["--apply", "--source-key", "777", "--archive-root", "/tmp/retro-test"],
    ["--apply", "--expected-sha256", "0" * 64, "--archive-root", "/tmp/retro-test"],
])
def test_apply_requires_explicit_selection_and_hash(monkeypatch, args):
    setup(monkeypatch, args)
    with pytest.raises(SystemExit) as exc:
        sync_cli.main()
    assert exc.value.code == 2


def test_apply_downloads_and_stages_only_selected_source(monkeypatch, tmp_path):
    from retro_rag.importer.staging import PlannedChange, digest

    dav = setup(monkeypatch, [
        "--apply", "--source-key", "777", "--expected-sha256", digest(b"test"),
        "--archive-root", str(tmp_path),
    ])
    staged = []

    def record_stage(conn, candidate, data, archive_root):
        staged.append((candidate.source_key, data))
        return PlannedChange("new", candidate.source_key, candidate.name, digest(data))

    monkeypatch.setattr(sync_cli, "stage_file", record_stage)
    sync_cli.main()
    assert dav.download_calls == ["777"]
    assert staged == [("777", b"test")]


def test_apply_rejects_hash_change_before_staging(monkeypatch, tmp_path):
    dav = setup(monkeypatch, [
        "--apply", "--source-key", "777", "--expected-sha256", "0" * 64,
        "--archive-root", str(tmp_path),
    ])
    monkeypatch.setattr(
        sync_cli, "stage_file", lambda *a, **k: pytest.fail("Stage trotz Hash-Wechsel")
    )
    with pytest.raises(RuntimeError, match="SHA-256"):
        sync_cli.main()
    assert dav.download_calls == ["777"]


def test_apply_rejects_unknown_source_before_download(monkeypatch, tmp_path):
    dav = setup(monkeypatch, [
        "--apply", "--source-key", "missing", "--expected-sha256", "0" * 64,
        "--archive-root", str(tmp_path),
    ])
    with pytest.raises(RuntimeError, match="nicht eindeutig"):
        sync_cli.main()
    assert dav.download_calls == []


def test_apply_network_error_cannot_reach_staging(monkeypatch, tmp_path):
    dav = setup(monkeypatch, [
        "--apply", "--source-key", "777", "--expected-sha256", "0" * 64,
        "--archive-root", str(tmp_path),
    ])

    def broken_download(*args, **kwargs):
        raise TimeoutError("simulated WebDAV timeout")

    dav.download = broken_download
    monkeypatch.setattr(
        sync_cli, "stage_file", lambda *a, **k: pytest.fail("Stage trotz Timeout")
    )
    with pytest.raises(TimeoutError, match="timeout"):
        sync_cli.main()
