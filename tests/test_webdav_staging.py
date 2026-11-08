"""Unit-Tests ohne Nextcloud und ohne Datenbankzugriff."""

import pytest

from retro_rag.importer.staging import archive_original, digest
from retro_rag.importer.webdav import WebDAV


def test_http_must_be_loopback():
    with pytest.raises(ValueError, match="Loopback"):
        WebDAV("http://nextcloud.example/remote.php/dav/files/u/", "u", "p")


def test_archive_is_content_addressed_and_immutable(tmp_path):
    data = b"---\ntitle: Test\n---\n# Test\n"
    uri1 = archive_original(tmp_path, data, "test.md")
    uri2 = archive_original(tmp_path, data, "test.md")
    assert uri1 == uri2
    assert digest(data) in uri1
    assert len(list(tmp_path.rglob("*.md"))) == 1


def test_archive_rejects_other_extensions(tmp_path):
    with pytest.raises(ValueError, match="Dateiformat"):
        archive_original(tmp_path, b"test", "test.exe")


def test_webdav_requests_explicit_nextcloud_fileid():
    """Nextcloud liefert oc:fileid nicht zwangsläufig bei allprop."""
    from retro_rag.importer.webdav import WebDAV

    client = WebDAV("http://127.0.0.1:8080/remote.php/dav/files/nina/Retro-Computing/", "nina", "secret")
    calls = []
    root = (
        b'<d:multistatus xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">'
        b'<d:response><d:href>/remote.php/dav/files/nina/Retro-Computing/</d:href></d:response>'
        b'<d:response><d:href>/remote.php/dav/files/nina/Retro-Computing/test.md</d:href>'
        b'<d:propstat><d:prop><oc:fileid>777</oc:fileid>'
        b'<d:getcontentlength>12</d:getcontentlength></d:prop>'
        b'<d:status>HTTP/1.1 200 OK</d:status></d:propstat>'
        b'</d:response></d:multistatus>'
    )

    def fake_request(url, method, data=None):
        calls.append((url, method, data))
        return root

    client._request = fake_request
    files = client.list_files()
    assert len(files) == 1
    assert files[0].source_key == "777"
    assert b"<oc:fileid/>" in calls[0][2]
    assert b"<d:allprop/>" not in calls[0][2]
