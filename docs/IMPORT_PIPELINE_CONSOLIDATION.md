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

## Gemeinsamer Testlauf auf Poseidon – 09.11.2026

Betreiberseitige Terminalausgabe auf dem Integrationsbranch nach
`python -m pip install -e '.[dev]'`:

```text
24 passed, 11 skipped in 0.18s
All checks passed!
```

- 24 lokal ausgeführte Tests bestanden; 0 fehlgeschlagen.
- Vier Dokumentidentitäts-DB-Tests übersprungen: `RETRO_V2_IDENTITY_TEST_DSN` nicht gesetzt.
- Sechs C1-DB-Tests übersprungen: `RETRO_V2_C1_TEST_DSN` nicht gesetzt.
- Ein isolierter C1-Konkurrenztest übersprungen: `RETRO_V2_C1_ISOLATED_DSN` nicht gesetzt.
- Ruff-Prüfung für `markdown.py`, `metadata.py` und `test_import_metadata.py`: `All checks passed!`.
- `git diff --check` ohne Ausgabe.

**Einordnung:** Der gemeinsame Unit-Testlauf und die Metadatenintegration sind
bestätigt. Die sieben C1- und vier Identitäts-DB-Tests wurden zuvor auf den
Einzelbranches erfolgreich durchgeführt, aber **nicht erneut auf dem
Integrationsbranch**. Ein übersprungener Test gilt nicht als bestanden.
Keine Freigabe für produktiven oder schreibenden Vollimport; das Write-Gate
bleibt geschlossen.

## Gemeinsame PostgreSQL-Abnahme auf Poseidon – 09.11.2026

Die Betreiberin hat auf `integration/import-pipeline-2026-11-09` beide
realen DB-Testsuiten mit dem dedizierten `rag_v2_migrator_login`
im Netzwerk-Namespace des bestehenden PostgreSQL-Containers ausgeführt.
`RETRO_V2_IDENTITY_TEST_DSN` und `RETRO_V2_C1_TEST_DSN` waren gesetzt;
die Tests wurden nicht übersprungen.

```text
.......... [100%]
10 passed in 0.23s
```

Anschließend wurde unabhängig lesend im bestehenden Container
`codeanalyse-postgres` gegen `retro_rag_v2_test` kontrolliert:

```text
writes_enabled = f
reason = Parallelitätstest erfolgreich; Freigabe ausstehend
documents = 0
sources   = 0
versions  = 0
reviews   = 0
jobs      = 0
```

**Ergebnis:** Die vier Identitätstests und sechs C1-Aktivierungstests
sind auf dem konsolidierten Branch bestanden; die synthetischen Daten
wurden zurückgerollt und die persistente Schreibsperre blieb geschlossen.
Zusammen mit dem zuvor dokumentierten gemeinsamen Lauf
(`24 passed, 11 skipped`) sind nun 24 Unit-Tests sowie 10 echte
PostgreSQL-Integrationstests auf dem Integrationsbranch bestätigt.

Der elfte zuvor übersprungene Test, der isolierte C1-Konkurrenztest,
wurde auf diesem Integrationsbranch **noch nicht erneut ausgeführt**.
Er ist nur auf dem vorgelagerten C1-Branch abgenommen. Ein echter
WebDAV-End-to-End-`--apply`-Import und Worker-/Embedding-Verarbeitung
stehen ebenfalls aus; keine produktive Schreibfreigabe.

## Wiederholter C1-Konkurrenztest im Integrationsbranch (09.11.2026)

Betreiberseitig auf Poseidon mit separatem Container `retro-rag-v2-c1-isolated`,
dessen Netzwerk-Namespace und `RETRO_V2_C1_ISOLATED_DSN` durchgeführt:

```text
. [100%]
1 passed in 0.16s
```

Damit wurden im konsolidierten Integrationsbranch insgesamt **24 Unit-Tests
und 11 echte PostgreSQL-Integrationstests** erfolgreich ausgeführt (4
Dokumentidentität, 6 C1-Aktivierung und 1 isolierter C1-Konkurrenztest).
Der Konkurrenztest verifiziert programmgesteuert auch die Blockierung
zweier konkurrierender Aktivierungen.

**Noch zu bestätigen:** unabhängige lesende Nachkontrolle des persistenten
V2-Write-Gates und der Tabellenzähler im bestehenden PostgreSQL-Container,
anschließend Stoppen des isolierten Testcontainers. Diese Schritte sind
nicht Bestandteil der übermittelten Testausgabe; ihre Durchführung darf
nicht vorweggenommen werden.

Keine automatische Freigabe für WebDAV-`--apply`, Indexierungs-Worker
oder Produktionsbetrieb. `main` wurde nicht verändert.
