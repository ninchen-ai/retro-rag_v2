"""Dokumentidentität: unabhängige Quellen und identische Bytes."""
from contextlib import contextmanager
from types import SimpleNamespace

from retro_rag.importer.staging import plan_file, stage_file
from retro_rag.importer.webdav import RemoteFile


def remote(instance, key, name="manual.pdf"):
    return RemoteFile(
        source_key=key, uri=f"https://nc.example/files/{name}",
        name=name, etag=None, byte_size=None,
        content_type="application/pdf", instance_id=instance,
    )


class PlanCursor:
    def __init__(self, existing=None, same_document_version=False, collision=False):
        self.existing = existing
        self.same_document_version = same_document_version
        self.collision = collision
        self.queries = []
        self.result = None

    def execute(self, sql, args=None):
        self.queries.append((sql, args))
        if "FROM rag_v2.document_source s" in sql and "s.source_instance = %s" in sql:
            self.result = self.existing
        elif "SELECT 1 FROM rag_v2.document_version v" in sql:
            self.result = (1,) if self.collision else None
        elif "SELECT 1 FROM rag_v2.document_version" in sql:
            self.result = (1,) if self.same_document_version else None
        else:
            raise AssertionError(sql)

    def fetchone(self):
        return self.result

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class PlanConnection:
    def __init__(self, cur):
        self.cur = cur

    def cursor(self):
        return self.cur


def test_same_fileid_is_scoped_to_instance():
    cur = PlanCursor()
    result = plan_file(PlanConnection(cur), remote("nc-B", "777"), b"same data")
    assert result.action == "new"
    assert cur.queries[0][1] == ("nc-B", "777")


def test_hash_collision_produces_review_not_merge():
    cur = PlanCursor(collision=True)
    result = plan_file(PlanConnection(cur), remote("nc-B", "777"), b"same data")
    assert result.action == "review"


def test_known_source_and_known_version_is_unchanged():
    cur = PlanCursor(existing=("doc-uuid", None), same_document_version=True)
    assert plan_file(PlanConnection(cur), remote("nc-A", "777"), b"same data").action == "unchanged"


def test_known_source_changed_hash_is_new_version():
    cur = PlanCursor(existing=("doc-uuid", None), same_document_version=False)
    assert plan_file(PlanConnection(cur), remote("nc-A", "777"), b"changed data").action == "changed"


def test_missing_instance_fails_closed():
    import pytest
    with pytest.raises(ValueError, match="Instanzkennung"):
        plan_file(PlanConnection(PlanCursor()), remote("", "777"), b"data")
