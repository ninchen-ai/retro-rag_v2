"""Three isolated PostgreSQL acceptance tests: crash, gate, importer RBAC.

These tests commit disposable fixtures and temporarily enable a login role.
They MUST NEVER target an existing Poseidon database or container.
"""
from __future__ import annotations

import hashlib
import os
from uuid import uuid4

import psycopg
import pytest

from retro_rag.importer.activation import activate_version
from retro_rag.importer.contract import Chunk, Document, ImportContract, Source
from retro_rag.importer.worker import claim_job, finish_job

CLUSTER = "retro-rag-v2-worker-isolated"
DSN_ENV = "RETRO_V2_WORKER_ISOLATED_DSN"


def isolated_dsn() -> str:
    dsn = os.getenv(DSN_ENV)
    if not dsn:
        pytest.skip(f"{DSN_ENV} fehlt")
    return dsn


def verify_disposable(cur) -> None:
    cur.execute("SELECT current_database(), current_setting('cluster_name'), session_user")
    if cur.fetchone() != ("retro_rag_v2_test", CLUSTER, "postgres"):
        raise RuntimeError("Schreibender Test ausschließlich im isolierten Worker-Cluster")
    cur.execute("SELECT max(version) FROM rag_v2.schema_migration")
    if cur.fetchone() != (6,):
        raise RuntimeError("Migrationsstand 0006 erforderlich")


@pytest.fixture
def isolated(tmp_path):
    """A single disposable fixture; restore even if a test assertion fails."""
    dsn = isolated_dsn()
    with psycopg.connect(dsn, autocommit=True) as admin:
        with admin.cursor() as cur:
            verify_disposable(cur)
            cur.execute("SELECT writes_enabled FROM rag_v2.write_gate WHERE id=true")
            if cur.fetchone() != (False,):
                raise RuntimeError("Write-Gate muss vor Testbeginn geschlossen sein")
            cur.execute("SELECT count(*) FROM rag_v2.processing_job")
            if cur.fetchone() != (0,):
                raise RuntimeError("Isolierte Jobqueue muss vor Testbeginn leer sein")
            cur.execute(
                "SELECT rolcanlogin FROM pg_roles WHERE rolname='rag_v2_importer_login'"
            )
            if cur.fetchone() != (False,):
                raise RuntimeError("Importer muss im Wegwerfcluster zunächst NOLOGIN sein")
        ids = {}
        try:
            with admin.cursor() as cur:
                # Only in disposable cluster. Host TCP trust is already isolated.
                cur.execute("ALTER ROLE rag_v2_importer_login LOGIN")
                cur.execute(
                    """UPDATE rag_v2.write_gate SET writes_enabled=true,
                       reason='Isolated transaction/permissions test' WHERE id=true"""
                )
                content = b"isolated atomic extraction fixture"
                sha = hashlib.sha256(content).hexdigest()
                root = tmp_path / "originals"
                archive = root / sha[:2] / (sha + ".md")
                archive.parent.mkdir(parents=True)
                archive.write_bytes(content)
                cur.execute(
                    "INSERT INTO rag_v2.document(title) VALUES (%s) RETURNING id",
                    ("isolated-" + str(uuid4()),),
                )
                ids["doc"] = cur.fetchone()[0]
                cur.execute(
                    """INSERT INTO rag_v2.document_version
                       (document_id,version_no,content_hash,archive_uri,source_filename)
                       VALUES (%s,1,%s,%s,'synthetic.md') RETURNING id""",
                    (ids["doc"], sha, archive.as_uri()),
                )
                ids["version"] = cur.fetchone()[0]
                cur.execute(
                    """INSERT INTO rag_v2.processing_job(document_version_id,job_type)
                       VALUES (%s,'document_import') RETURNING id""",
                    (ids["version"],),
                )
                ids["job"] = cur.fetchone()[0]
                cur.execute(
                    """INSERT INTO rag_v2.processing_step
                       (processing_job_id,step_name,status,input_hash,completed_at)
                       VALUES (%s,'source_archived','completed',%s,now())""",
                    (ids["job"], sha),
                )
                ids["hash"] = sha
                ids["archive"] = archive
                text = "Synthetischer Inhalt fuer PostgreSQL-Worker-Test"
                ids["contract"] = ImportContract(
                    source=Source(
                        source_id="document_version:" + str(ids["version"]),
                        location=str(archive),
                        content_hash=sha,
                        kind="markdown",
                    ),
                    document=Document(title="synthetic", document_type="markdown"),
                    chunks=[Chunk(
                        ordinal=0, text=text,
                        chunk_hash=hashlib.sha256(text.encode()).hexdigest(),
                    )],
                )
            yield dsn, admin, ids
        finally:
            # For this purpose only the isolated test's synthetic objects exist.
            # Keep cleanup independent of any failed transaction or disconnected worker.
            with admin.cursor() as cur:
                try:
                    if "job" in ids:
                        cur.execute(
                            """DELETE FROM rag_v2.processing_artifact WHERE processing_step_id
                               IN (SELECT id FROM rag_v2.processing_step
                                   WHERE processing_job_id=%s)""",
                            (ids["job"],),
                        )
                        cur.execute(
                            "DELETE FROM rag_v2.processing_step WHERE processing_job_id=%s",
                            (ids["job"],),
                        )
                    if "version" in ids:
                        cur.execute(
                            "DELETE FROM rag_v2.chunk_embedding WHERE chunk_id IN "
                            "(SELECT id FROM rag_v2.chunk WHERE document_version_id=%s)",
                            (ids["version"],),
                        )
                        cur.execute(
                            "DELETE FROM rag_v2.chunk WHERE document_version_id=%s",
                            (ids["version"],),
                        )
                    if "job" in ids:
                        cur.execute(
                            "DELETE FROM rag_v2.processing_job WHERE id=%s",
                            (ids["job"],),
                        )
                    if "version" in ids:
                        cur.execute(
                            "DELETE FROM rag_v2.document_version WHERE id=%s",
                            (ids["version"],),
                        )
                    if "doc" in ids:
                        cur.execute("DELETE FROM rag_v2.document WHERE id=%s", (ids["doc"],))
                finally:
                    cur.execute(
                        """UPDATE rag_v2.write_gate SET writes_enabled=false,
                           reason='Isolated worker acceptance test completed' WHERE id=true"""
                    )
                    cur.execute("ALTER ROLE rag_v2_importer_login NOLOGIN")
            with admin.cursor() as cur:
                cur.execute("SELECT writes_enabled FROM rag_v2.write_gate WHERE id=true")
                assert cur.fetchone() == (False,)


def importer_dsn(admin_dsn):
    params = psycopg.conninfo.conninfo_to_dict(admin_dsn)
    params["user"] = "rag_v2_importer_login"
    return psycopg.conninfo.make_conninfo(**params)


def claim_as_importer(dsn, owner):
    with psycopg.connect(importer_dsn(dsn), autocommit=True) as conn:
        with conn.cursor() as cur:
            assert cur.execute("SELECT session_user").fetchone() == (
                "rag_v2_importer_login",)
        return claim_job(conn, owner)


def test_killed_backend_rolls_back_chunks_and_recovery(isolated):
    """Backend termination before commit must rollback every uncommitted row."""
    dsn, admin, ids = isolated
    job = claim_as_importer(dsn, "worker-crashed")
    assert job is not None and job[0] == ids["job"]
    worker_conn = psycopg.connect(importer_dsn(dsn), autocommit=False)
    try:
        with worker_conn.cursor() as cur:
            cur.execute("SELECT pg_backend_pid()")
            pid = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO rag_v2.chunk
                   (document_version_id,sequence_no,content,content_hash)
                   VALUES (%s,0,%s,%s)""",
                (ids["version"], ids["contract"].chunks[0].text,
                 ids["contract"].chunks[0].chunk_hash),
            )
            cur.execute(
                """INSERT INTO rag_v2.processing_step
                   (processing_job_id,step_name,status,input_hash)
                   VALUES (%s,'text_extracted','completed',%s) RETURNING id""",
                (ids["job"], ids["hash"]),
            )
            step_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO rag_v2.processing_artifact
                   (processing_step_id,artifact_kind,artifact_uri,content_hash)
                   VALUES (%s,'chunk_set',%s,%s)""",
                (step_id, "db:rag_v2.chunk/" + str(ids["version"]), ids["hash"]),
            )
        with admin.cursor() as cur:
            cur.execute("SELECT pg_terminate_backend(%s)", (pid,))
            assert cur.fetchone() == (True,)
    finally:
        worker_conn.close()
    with admin.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM rag_v2.chunk WHERE document_version_id=%s",
            (ids["version"],),
        )
        assert cur.fetchone() == (0,)
        cur.execute(
            """SELECT count(*) FROM rag_v2.processing_step
               WHERE processing_job_id=%s AND step_name='text_extracted'""",
            (ids["job"],),
        )
        assert cur.fetchone() == (0,)
        cur.execute(
            """SELECT count(*) FROM rag_v2.processing_artifact a
               JOIN rag_v2.processing_step s ON s.id=a.processing_step_id
               WHERE s.processing_job_id=%s AND a.artifact_kind='chunk_set'""",
            (ids["job"],),
        )
        assert cur.fetchone() == (0,)
        # Simulate the lease timeout following an abrupt process death.
        cur.execute(
            "UPDATE rag_v2.processing_job SET lease_until=now()-interval '1 second' "
            "WHERE id=%s", (ids["job"],),
        )
    resumed = claim_as_importer(dsn, "worker-resumed")
    assert resumed is not None and resumed[0] == ids["job"]
    with psycopg.connect(importer_dsn(dsn), autocommit=True) as conn:
        finish_job(conn, resumed, "worker-resumed", ids["archive"], ids["contract"])
    with admin.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM rag_v2.chunk WHERE document_version_id=%s",
            (ids["version"],),
        )
        assert cur.fetchone() == (1,)
        cur.execute(
            """SELECT status,lease_owner FROM rag_v2.processing_job WHERE id=%s""",
            (ids["job"],),
        )
        assert cur.fetchone() == ("running", None)
        cur.execute(
            "SELECT processing_state,state FROM rag_v2.document_version WHERE id=%s",
            (ids["version"],),
        )
        assert cur.fetchone() == ("processing", None)


def test_gate_closed_after_claim_refuses_persistence(isolated):
    """Gate closed after short claim must reject the later, separate commit."""
    dsn, admin, ids = isolated
    job = claim_as_importer(dsn, "worker-before-close")
    assert job is not None
    with admin.cursor() as cur:
        cur.execute(
            "UPDATE rag_v2.write_gate SET writes_enabled=false WHERE id=true"
        )
    with (
        psycopg.connect(importer_dsn(dsn), autocommit=True) as conn,
        pytest.raises(psycopg.errors.InsufficientPrivilege, match="Schreibsperre"),
    ):
        finish_job(conn, job, "worker-before-close", ids["archive"], ids["contract"])
    with admin.cursor() as cur:
        cur.execute("SELECT count(*) FROM rag_v2.chunk WHERE document_version_id=%s",
                    (ids["version"],))
        assert cur.fetchone() == (0,)
        cur.execute("SELECT processing_state FROM rag_v2.document_version WHERE id=%s",
                    (ids["version"],))
        assert cur.fetchone() == ("discovered",)


def test_importer_rbac_and_no_premature_activation(isolated):
    """Actual login inherits importer DML but cannot touch gate or publish."""
    dsn, admin, ids = isolated
    with psycopg.connect(importer_dsn(dsn), autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT session_user")
        assert cur.fetchone() == ("rag_v2_importer_login",)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cur.execute("UPDATE rag_v2.write_gate SET writes_enabled=false")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cur.execute("INSERT INTO rag_v2.fact DEFAULT VALUES")
    job = claim_as_importer(dsn, "worker-activation-check")
    assert job is not None
    with psycopg.connect(importer_dsn(dsn), autocommit=True) as conn:
        finish_job(conn, job, "worker-activation-check", ids["archive"], ids["contract"])
    with psycopg.connect(dsn, autocommit=False) as verifier:
        with pytest.raises(ValueError, match="nicht vollständig"):
            activate_version(verifier, ids["version"])
        verifier.rollback()
    with admin.cursor() as cur:
        cur.execute("SELECT status FROM rag_v2.processing_job WHERE id=%s", (ids["job"],))
        assert cur.fetchone() == ("running",)
        cur.execute("SELECT processing_state,state FROM rag_v2.document_version WHERE id=%s",
                    (ids["version"],))
        assert cur.fetchone() == ("processing", None)
