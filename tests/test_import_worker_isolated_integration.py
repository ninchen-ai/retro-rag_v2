"""Real PostgreSQL lease/concurrency checks on a disposable isolated cluster ONLY.

NEVER point this test at Poseidon's persistent V2 test database. The test
creates and commits synthetic objects and temporarily opens a disposable
cluster's write gate; no V1/Nextcloud/real archive access is involved.
"""
import hashlib
import os
from concurrent.futures import ThreadPoolExecutor

import psycopg
import pytest

from retro_rag.importer.worker import claim_job

ISOLATED_CLUSTER = "retro-rag-v2-worker-isolated"


def _check_isolation(cur):
    cur.execute(
        "SELECT current_database(), current_setting('cluster_name'), session_user"
    )
    if cur.fetchone() != ("retro_rag_v2_test", ISOLATED_CLUSTER, "postgres"):
        raise RuntimeError("Worker-Lease-Test nur als postgres im isolierten Testcluster")
    cur.execute("SELECT max(version) FROM rag_v2.schema_migration")
    if cur.fetchone()[0] != 6:
        raise RuntimeError("Isolierter Worker-Test benötigt Migration 0006")


def _claim(dsn, owner):
    with psycopg.connect(dsn, autocommit=True) as conn:
        return claim_job(conn, owner)


def test_concurrent_workers_expiry_and_retry_exhaustion():
    dsn = os.getenv("RETRO_V2_WORKER_ISOLATED_DSN")
    if not dsn:
        pytest.skip("RETRO_V2_WORKER_ISOLATED_DSN fehlt; isolierter Cluster erforderlich")
    job_id = document_id = version_id = None
    with psycopg.connect(dsn, autocommit=True) as admin:
        with admin.cursor() as cur:
            _check_isolation(cur)
            cur.execute("SELECT writes_enabled FROM rag_v2.write_gate WHERE id=true")
            if cur.fetchone() != (False,):
                raise RuntimeError("Isolierter Testcluster muss mit geschlossenem Gate starten")
            # No existing work may be accidentally claimed.
            cur.execute("SELECT count(*) FROM rag_v2.processing_job")
            if cur.fetchone()[0] != 0:
                raise RuntimeError("Isolierter Worker-Cluster benötigt eine leere Jobtabelle")
        try:
            with admin.cursor() as cur:
                cur.execute(
                    """UPDATE rag_v2.write_gate
                       SET writes_enabled=true,
                           reason='Temporary disposable worker lease test'
                       WHERE id=true"""
                )
                cur.execute(
                    """INSERT INTO rag_v2.document (title)
                       VALUES ('Synthetic isolated lease job') RETURNING id"""
                )
                document_id = cur.fetchone()[0]
                content_hash = hashlib.sha256(b"isolated worker fixture").hexdigest()
                cur.execute(
                    """INSERT INTO rag_v2.document_version
                       (document_id,version_no,content_hash,source_filename,archive_uri)
                       VALUES (%s,1,%s,'synthetic.md',%s) RETURNING id""",
                    (document_id, content_hash, "file:///isolated/" + content_hash + ".md"),
                )
                version_id = cur.fetchone()[0]
                cur.execute(
                    """INSERT INTO rag_v2.processing_job
                       (document_version_id,job_type,max_attempts)
                       VALUES (%s,'document_import',3) RETURNING id""",
                    (version_id,),
                )
                job_id = cur.fetchone()[0]
                cur.execute(
                    """INSERT INTO rag_v2.processing_step
                       (processing_job_id,step_name,status,input_hash,completed_at)
                       VALUES (%s,'source_archived','completed',%s,now())""",
                    (job_id, content_hash),
                )

            # Real independent connections racing for exactly one row.
            with ThreadPoolExecutor(max_workers=2) as pool:
                future_a = pool.submit(_claim, dsn, "worker-a")
                future_b = pool.submit(_claim, dsn, "worker-b")
                results = [future_a.result(timeout=15), future_b.result(timeout=15)]
            claimed = [item for item in results if item is not None]
            assert len(claimed) == 1
            assert claimed[0][0] == job_id
            with admin.cursor() as cur:
                cur.execute(
                    "SELECT status,attempts,lease_owner FROM rag_v2.processing_job WHERE id=%s",
                    (job_id,),
                )
                status, attempts, first_owner = cur.fetchone()
                assert (status, attempts) == ("running", 1)
                assert first_owner in ("worker-a", "worker-b")
                # Simulated process death: lease expires, without changing the job.
                cur.execute(
                    """UPDATE rag_v2.processing_job
                       SET lease_until=now()-interval '1 second' WHERE id=%s""",
                    (job_id,),
                )
            resumed = _claim(dsn, "worker-restarted")
            assert resumed is not None and resumed[0] == job_id
            with admin.cursor() as cur:
                cur.execute(
                    "SELECT attempts,lease_owner FROM rag_v2.processing_job WHERE id=%s",
                    (job_id,),
                )
                assert cur.fetchone() == (2, "worker-restarted")
                # A still valid lease cannot be stolen.
                assert _claim(dsn, "worker-intruder") is None
                cur.execute(
                    """UPDATE rag_v2.processing_job
                       SET lease_until=now()-interval '1 second' WHERE id=%s""",
                    (job_id,),
                )
            final = _claim(dsn, "worker-final")
            assert final is not None and final[0] == job_id
            with admin.cursor() as cur:
                cur.execute(
                    "SELECT attempts FROM rag_v2.processing_job WHERE id=%s",
                    (job_id,),
                )
                assert cur.fetchone() == (3,)
                cur.execute(
                    """UPDATE rag_v2.processing_job
                       SET lease_until=now()-interval '1 second' WHERE id=%s""",
                    (job_id,),
                )
            assert _claim(dsn, "worker-too-many") is None
            with admin.cursor() as cur:
                cur.execute(
                    "SELECT attempts FROM rag_v2.processing_job WHERE id=%s",
                    (job_id,),
                )
                assert cur.fetchone() == (3,)
        finally:
            # This test owns the whole disposable cluster's queue by design.
            # Remove fixtures and ALWAYS close the isolated write gate.
            with admin.cursor() as cur:
                try:
                    if job_id is not None:
                        cur.execute(
                            "DELETE FROM rag_v2.processing_step WHERE processing_job_id=%s",
                            (job_id,),
                        )
                        cur.execute(
                            "DELETE FROM rag_v2.processing_job WHERE id=%s", (job_id,)
                        )
                    if version_id is not None:
                        cur.execute(
                            "DELETE FROM rag_v2.document_version WHERE id=%s", (version_id,)
                        )
                    if document_id is not None:
                        cur.execute(
                            "DELETE FROM rag_v2.document WHERE id=%s", (document_id,)
                        )
                finally:
                    cur.execute(
                        """UPDATE rag_v2.write_gate
                           SET writes_enabled=false,
                               reason='Isolated worker lease test completed'
                           WHERE id=true"""
                    )
            with admin.cursor() as cur:
                cur.execute("SELECT writes_enabled FROM rag_v2.write_gate WHERE id=true")
                assert cur.fetchone() == (False,)
