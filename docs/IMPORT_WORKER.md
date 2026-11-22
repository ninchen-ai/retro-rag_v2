# Restartable Import Extraction Worker (22.11.2026)

Branch: `feat/resumable-import-worker-2026-11-22`, based on
`integration/import-pipeline-2026-11-09`.

## What this actually implements

This is the **first runnable, persisted worker stage** for files already
staged by the controlled single-file WebDAV apply. It is deliberately **not**
the completed end-to-end indexing/activation pipeline.

- `processing_job` is the PostgreSQL queue; no Redis/Celery.
- Claims use `FOR UPDATE OF j SKIP LOCKED`, bounded leases, a unique owner and
  a maximum of three attempts (existing schema defaults).
- The worker processes **one job per invocation** and is therefore suitable
  for later systemd timer operation. A crashed process can be retried once its
  lease expires. Lost leases prevent final commits.
- The original is read only from an explicitly selected archive root and
  verified against its stored SHA-256. No WebDAV write or re-download.
- PDF goes through `read_pdf`; Markdown through `read_markdown`. The
  canonical `text_extracted` step, `chunk_set` artifact and version-specific
  chunks commit in the same transaction via `job_pipeline.py`.
- PDF pages with extraction warnings or OCR gaps fail closed. Markdown
  metadata/format validation still applies. Markdown's existing warning
  concerning *unimplemented trust authorization* does **not** approve facts.
- Existing `source_archived` step is preserved. Identity-review candidates
  are not claimed. All writes recheck the existing write gate.
- Successful extraction sets `document_version.processing_state=processing`,
  **never** `indexed`. No embeddings, version activation, reviewer approval,
  inventory changes or automatic factual promotion occur here.

The extraction stage now releases its lease while leaving `document_import`
`running` and `document_version.processing_state=processing`. Jobs with a
completed `text_extracted` step are not claimed again. Embeddings and technical
indexing must finish before the job is marked completed or a version activated.

## Operator workflow

Do **not** apply the worker against live databases or enable a timer yet.
Run on Poseidon only after backup and explicit operator authorization.

```bash
cd ~/projects/retro-rag_v2
git fetch origin
git switch --track origin/feat/resumable-import-worker-2026-11-22
source .venv/bin/activate
python -m pip install -e '.[dev,pdf]'
python -m ruff check src/retro_rag/importer/worker.py tests/test_import_worker.py
python -m pytest -q tests/test_import_worker.py -rs
python -m pytest -q -rs
```

Dry run does not claim a job:

```bash
python -m retro_rag.importer.worker --archive-root /data/retro-rag/v2/originals
```

Only for the **test database** `retro_rag_v2_test`, with a dedicated
`rag_v2_importer_login` connection and separately approved, temporarily opened
test write gate:

```bash
export RETRO_V2_DATABASE_DSN='host=127.0.0.1 dbname=retro_rag_v2_test user=rag_v2_importer_login'
python -m retro_rag.importer.worker --apply \
  --archive-root /data/retro-rag/v2/originals --ocr-mode off
```

Do not place credentials in terminal commands or tracked files. Close the
test write gate **immediately** after the approved test, then independently
verify jobs, chunks, artifacts, old active versions and the gate state.
For `cubx-103.pdf` the known page-111 OCR-quality issue means automatic
indexing must stay blocked. Do not schedule the worker until database
concurrency, crash/restart and read-only permission checks pass on Poseidon.

## Remaining acceptance conditions

1. Run real database tests for two competing workers, expired leases,
   exhausted retries, gate closure mid-extraction and interrupted commit.
2. Retain extraction warnings/quality metadata as persistently retrievable
   artifacts (currently only a summary hash and chunk reference are saved).
3. Add resumable embedding generation and atomic publication once **every**
   chunk has a verified model embedding; update job completion semantics.
4. Add independent, trusted authorization/review decisions; OCR quality
   alone is not a factual approval.
5. Ship a disabled-by-default systemd service/timer only after those tests.

No migration applied, no Gate changed, no production job started by this PR.

## Poseidon safety check and follow-up (22.11.2026)

The operator confirmed on the earlier revision: 184 passed, 16 skipped,
Ruff clean; dry-run did not claim work and the DB gate was `false`.
**These results precede the canonical-persistence refactoring.** Run the
full suite again; concurrency/retry tests and isolated DB acceptance remain
outstanding. No `--apply` or timer activation is authorized.


## Isolated PostgreSQL lease/concurrency test (22.11.2026)

`tests/test_import_worker_isolated_integration.py` exercises competing real
connections, exclusive claims, simulated worker death/expired lease, recovery,
live-lease protection and the third/final retry. It creates and commits
synthetic fixtures, so it **must never run against Poseidon's persistent
`codeanalyse-postgres` cluster**.

Required: a separately provisioned disposable PostgreSQL 16 cluster,
`cluster_name='retro-rag-v2-worker-isolated'`, a dedicated
`retro_rag_v2_test` database with migrations 0001–0006, a completely empty
`processing_job` table and a **closed** write gate. The test requires
`session_user=postgres` and checks all those preconditions before any write.
Its `finally` cleanup deletes synthetic fixtures and closes only the
disposable cluster's gate. If the test process is hard-killed, destroy the
disposable cluster rather than reusing its potentially open gate.

Run the test only after verifying the exact container and DSN target:

```bash
# Example only. Supply an independently verified disposable-cluster DSN.
export RETRO_V2_WORKER_ISOLATED_DSN='host=127.0.0.1 port=<isolated-port> dbname=retro_rag_v2_test user=postgres'
python -m pytest -q tests/test_import_worker_isolated_integration.py -rs
unset RETRO_V2_WORKER_ISOLATED_DSN
```

No real Nextcloud, Ollama, documents, or production storage are accessed.
The 185-pass baseline predates the addition of this isolated test and the
source-id correction. Those new changes require a fresh Poseidon regression.
