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
  `content_extracted` step and version-specific chunks commit in the same
  database transaction. The artifact is a DB reference to those chunks.
- PDF pages with extraction warnings or OCR gaps fail closed. Markdown
  metadata/format validation still applies. Markdown's existing warning
  concerning *unimplemented trust authorization* does **not** approve facts.
- Existing `source_archived` step is preserved. Identity-review candidates
  are not claimed. All writes recheck the existing write gate.
- Successful extraction sets `document_version.processing_state=processing`,
  **never** `indexed`. No embeddings, version activation, reviewer approval,
  inventory changes or automatic factual promotion occur here.

A completed `document_import` job currently means *extraction persisted*,
not *technically indexed*. Version activation remains blocked by the
`processing_state=indexed` requirement and missing embeddings. Before the
full pipeline is shipped, extend the job lifecycle to include an explicit
embedding step and only mark complete after the index is ready.

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
