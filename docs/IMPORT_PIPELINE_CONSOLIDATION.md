# Konsolidierung der Import-Pipeline (09.11.2026)

Branch: `integration/import-pipeline-2026-11-09`

## Enthaltene Entwicklungslinien

- `feature/phase0-database`: Migrationen 0001–0003, Schema und Rollen.
- `feat/import-pipeline-foundation`: Pydantic-Vertrag, Markdown-Adapter und Tests.
- `feat/import-webdav-staging`: WebDAV-Dateierkennung, Ausschlüsse, Originalarchiv/Staging.
- `fix/importer-write-gate`: Migration 0004, gesicherte Gate-Funktion.
- `feat/document-identity-review`: Migration 0005, Instanz-ID, Dublettenreview.
- `feature/c1-atomic-version-activation`: atomare Versionenaktivierung und DB-Tests.
- `feat/import-contract-metadata`: separate YAML-Metadatenprüfung, Integration in Markdown-Adapter und Tests.

Der Integrationscommit besitzt den C1-Stand und den Metadaten-Stand als
Git-Eltern. Die Metadaten-Änderungen wurden über ihren gemeinsamen
Vorfahr `fdee774` abgeglichen. Die veraltete Statuszeile im README des
Metadatenbranches wurde nicht übernommen; die aktuelle C1-Statuszeile bleibt
erhalten.

## Abnahme und Grenzen

Die zuvor dokumentierten Einzeltests der jeweiligen Entwicklungsbranches sind
historische Nachweise und **kein** gemeinsamer Integrationstest dieses Branches.
Vor einem Merge nach `main` auf Poseidon ausführen:

```bash
git fetch origin
git switch --track origin/integration/import-pipeline-2026-11-09
python -m pip install -e '.[dev]'
python -m pytest -q -rs
python -m ruff check src/retro_rag/importer/markdown.py src/retro_rag/importer/metadata.py tests/test_import_metadata.py
git diff --check
```

PostgreSQL-Tests mit echtem DB-Zugang sind separat gemäß
`docs/DOCUMENT_IDENTITY_INTEGRATION_TESTS.md` und
`docs/C1_ATOMIC_VERSION_ACTIVATION.md` durchzuführen. `skipped` ist
kein bestandener Integrationstest.

Die Datenbank `retro_rag_v2_test` bleibt gesperrt, bis der
schreibende Import separat freigegeben wird. Keine Migration, keine
WebDAV-Änderung, kein Gate-Öffnen und kein `--apply` durch diese
Konsolidierung. Original-Feature-Branches bleiben erhalten.
