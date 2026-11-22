# Importjob → ImportContract → Chunks: erster Adapterentwurf

**Stand:** 22.11.2026 · **Entwicklungsbranch:** `feat/processing-job-contract-adapter-2026-11-22` (ab PR #13, Commit `2a6cced`).

**Status: Code vorbereitet, NICHT auf Poseidon getestet und NICHT freigegeben.**
Keine Änderung an HBA, DB-Migrationen, Docker-Ports, Write-Gate, Archiv oder produktiven Importern.

## Warum dieser Adapter?

Vorhanden sind drei technisch getrennte Komponenten:

- `staging.stage_file` erzeugt bereits `document_version`, `processing_job`, den abgeschlossenen `source_archived`-Schritt und das zugehörige Originalartefakt. Ein positiver `--apply` ist nicht freigegeben.
- `pdf.read_pdf` / `markdown.read_markdown` liefern schreibfreie `ImportContract`-Objekte mit Text-Chunks und Quellhash. Eine Vorschau besitzt grundsätzlich `indexing_allowed=false`.
- `activation.activate_version` erwartet erst später einen abgeschlossenen Importjob und Chunks mit Embeddings. Zwischen Extraktion und Persistierung gab es noch keinen Adapter.

Der neue `src/retro_rag/importer/job_pipeline.py` adressiert **nur den mittleren Übergang**.

## Funktionen

### `prepare_job(conn, job_id, archive_root, ocr_mode="off", ocr_pages=None)`

Nur lesender Vorbereitungsschritt. Verlangt `retro_rag_v2_test`, einen existierenden `pending`-`document_import`-Job, eine Version im Zustand `discovered`, eine abgeschlossene `source_archived`-Stufe und eine existierende lokale Archivdatei unter dem expliziten Archiv-Root. Verweigert externe `https://`-URIs, Pfadausbrüche und Symlink-Fluchten. Vergleicht den SHA-256 des Archivoriginals und den Extraktionsvertrag mit dem Datenbankhash. Ordnet `.pdf` dem PDF-Adapter und `.md` dem Markdown-Adapter zu.

Rückgabe: `PreparedJob` mit Job-/Versions-ID, Archivpfad und `ImportContract`. **Keine Datenbankänderung, kein WebDAV und keine Indexfreigabe.**

### `persist_contract(conn, prepared)`

**Schreibende Funktion, nur als ausdrücklich freizugebender Folgeschritt.** Sie verlangt eine bereits offene DB-Transaktion, die Anmeldung als `rag_v2_importer_login` in `retro_rag_v2_test` und die serverseitige Funktion `rag_v2.assert_import_write_gate()`. Sie verweigert OCR-Fehlerseiten und PDF-Extraktionswarnungen, leere oder übergroße Chunk-Sätze, geänderte Quell-/Chunk-Hashes, ungültige Chunk-Reihenfolge sowie inzwischen veränderte Job-/Versionszustände. Die betroffenen Job-/Versionszeilen werden gesperrt. Vorhandene `text_extracted`-Schritte sind nicht erneut übertragbar, damit keine Doppel-Chunks entstehen.

Bei geöffneter, gültiger Freigabe erzeugt sie innerhalb der **vom Aufrufer kontrollierten** Transaktion:

1. Versionengebundene `rag_v2.chunk`-Einträge mit Seitenkoordinaten und `source_locator`.
2. `processing_step('text_extracted', 'completed')` mit Originalhash.
3. Ein `processing_artifact('chunk_set')` als Referenz auf die versionengebundenen DB-Chunks; dessen Hash bezeichnet die geordnete Liste der Chunk-Hashes, keine externe Textdatei.
4. Version `processing_state='processing'` und Job `status='running'`.

**Es erfolgen weder `COMMIT` noch `ROLLBACK` innerhalb dieser Funktion.** Der Aufrufer entscheidet selbst. Keine Embeddings werden erzeugt; deshalb **kein** `processing_state='indexed'`, **kein** `job.status='completed'` und **keine** Versionsaktivierung. Das spätere Weiterverarbeiten und Wiederaufnehmen eines `running`-Jobs ist noch nicht implementiert.

## Sicherheits- und Funktionsgrenzen

- Die Implementierung ist eine **Bibliotheksfunktion**, kein Scheduler/CLI mit `--apply`. Sie wird nirgendwo automatisch gestartet.
- Solange das persistente Write-Gate geschlossen bleibt, muss jeder Schreibaufruf an `assert_import_write_gate()` scheitern. **Gate für diese Entwicklung nicht öffnen.**
- Es gibt noch keine vollständige Retry-/Lease-Logik; aus diesem Grund **nicht für reale Imports ausführen**.
- Parserwarnungen (z. B. problematische leselose Seiten) werden durch den ersten Adapter nicht als eigene DB-Artefakte persistiert. OCR-Fehlerseiten sperren die Persistierung; eine zusätzliche persistente Fehler-/Review-Verwaltung ist notwendig.
- Es fehlen noch strukturierte PDF-/OCR-Metadatenartefakte, Embedding-Erzeugung und Job-Finalisierung.
- `source_locator` verweist auf die versionsgebundene Quelle, nicht auf eine bestätigte technische Tatsache. Es erfolgt keine Wissens-/Faktenextraktion.
- Für die erste Abnahme ausschließlich Syntax, Ruff, Unit-Tests und danach rollback-only DB-Tests mit synthetischen Daten und unabhängiger Gate-/Zähler-Nachkontrolle. Der positive Write-Pfad bedarf einer separaten Teststrategie, bei der das Gate **nie persistent** geöffnet wird; eine echte Live-Freigabe ist nicht erteilt.
- Die bisherige Sicherungs- und HBA-Dokumentation in [`PR13_POSEIDON_INTEGRATION_TEST_2026-11-22.md`](PR13_POSEIDON_INTEGRATION_TEST_2026-11-22.md) bleibt maßgeblich.

## Erstprüfung auf Poseidon (nur Code, kein DB-Schreibtest)

**Nicht blind auf dem offenen PR-#13-Integrationsbranch testen.** In einer sauberen lokalen Kopie auf den eigenen Featurebranch wechseln:

```bash
cd ~/projects/retro-rag_v2
git status --short
git fetch origin
git switch --track origin/feat/processing-job-contract-adapter-2026-11-22
source .venv/bin/activate

python -m pytest -q tests/test_job_pipeline.py -rs
python -m pytest -q -rs
python -m ruff check .
git diff --check
```

Die Ausgabe ist noch **nicht** nachgewiesen. Die reguläre Suite darf weiterhin DB-Tests ohne explizit gesetzten DSN skippen. Für den isolierten C1-Konkurrenztest einen separaten Cluster verwenden.

## PostgreSQL-Negativtest mit echter Importer-Rolle (vorbereitet 22.11.2026)

`tests/test_job_pipeline_integration.py` enthält jetzt einen **explizit aktivierbaren** Negativtest. Er stellt eine echte `psycopg`-Verbindung mit `rag_v2_importer_login` zu `retro_rag_v2_test` her, kontrolliert das geschlossene Write-Gate und ruft `persist_contract()` mit synthetischem Text und nicht existierenden Job-/Versions-IDs auf. Erwartet ist **SQLSTATE 42501** (`V2-Schreibsperre ist geschlossen`). Eine Rolle, Datenbank oder Gate-Freigabe wird weder erstellt noch geändert. Der synthetische Originaltext liegt nur in einer temporären lokalen Pytest-Datei. Die Verbindung führt im `finally` ein Rollback aus.

**Noch nicht auf Poseidon ausgeführt.** Für den Test einen gesicherten Importer-Login und den bereits geprüften PostgreSQL-Netzwerk-Namespace nutzen; keine Ausweitung des Docker-HBA-Netzes.

```bash
cd ~/projects/retro-rag_v2
git pull --ff-only
source .venv/bin/activate

python -m ruff check .
python -m pytest -q -rs
```

Die reguläre Suite überspringt diesen realen DB-Test ohne `RETRO_V2_JOB_TEST_DSN`; der Umgebungsschlüssel wird nur für eine explizite Testausführung gesetzt. Der negative SQL-Test darf **nicht** als erfolgreicher positiver Chunk-Apply gewertet werden. Ein Positivtest benötigt eine separate Isolation; auf der vorhandenen V2-Testdatenbank wird das Gate nicht geöffnet. Nach dem Negativlauf sind das Gate und die Tabellenzähler über eine **zweite** DB-Sitzung unabhängig zu kontrollieren.

## Poseidon-Testnachweis – 22.11.2026

**Code- und Regressionstest:** Nach Fast-forward auf `0ebec66` im separaten Featurebranch:

- `python -m ruff check .` → **All checks passed!**
- `python -m pytest -q -rs` → **163 passed, 12 skipped** (0,69 s). Zehn DB-Tests für Identity/C1, ein isolierter Concurrency-Test und der neue, optional über DSN aktivierbare Gate-Test blieben im regulären Lauf übersprungen.
- `git status --short` ohne Ausgabe; Arbeitsbaum sauber.

**Echter PostgreSQL-Gate-Negativtest:** Im Netzwerk-Namespace des laufenden `codeanalyse-postgres` wurde `tests/test_job_pipeline_integration.py` mit `rag_v2_importer_login` an `retro_rag_v2_test` über `127.0.0.1:5432` ausgeführt. DSN in `RETRO_V2_JOB_TEST_DSN`, Passwort interaktiv eingelesen, kein HBA-Edit:

```text
. [100%]
1 passed in 0.20s
JOB_DB_TEST_EXIT=0
```

Das Testskript kontrolliert Datenbank, Sessionuser und geschlossenes Gate und erwartet eine `psycopg.errors.InsufficientPrivilege` wegen `V2-Schreibsperre ist geschlossen` beim Versuch `persist_contract()`. Es verwendet ausschließlich synthetische lokale Originalbytes und keine realen Dokument-/Job-IDs; seine Verbindung wird im `finally` zurückgerollt. Das **bestätigt die Gate-Ablehnung**, nicht den positiven Chunk-/Artefakt-Schreibpfad.

**Unabhängige read-only SQL-Nachkontrolle – PASS (22.11.2026):** Die Betreiberin hat nach dem echten Importer-Gate-Negativtest eine separate Sitzung mittels `docker exec -i codeanalyse-postgres psql -X -v ON_ERROR_STOP=1 -U codeanalyse -d retro_rag_v2_test` mit `BEGIN READ ONLY` / `COMMIT` ausgeführt. Ergebnisse:

| Kontrollpunkt | Nachkontrolle |
| --- | --- |
| Migration `MAX(schema_migration.version)` | `6` |
| `write_gate.writes_enabled` | `f` |
| Sperrgrund | `Parallelitätstest erfolgreich; Freigabe ausstehend` |
| `document`, `document_source`, `document_version` | jeweils `0` |
| `processing_job`, `processing_step`, `processing_artifact` | jeweils `0` |
| `chunk`, `chunk_embedding` | jeweils `0` |
| `review_item`, `knowledge_proposal` | jeweils `0` |

Damit sind der geschlossene Gate-Zustand und **alle zehn überprüften Tabellenzähler** nach dem Negativtest unabhängig bestätigt. Diese Kontrolle betrifft die aufgelisteten Tabellen, nicht einen Vollvergleich der gesamten Datenbank. Es gab keinen positiven Import, keine DB-Migration und keine Gate-Freigabe. Die positive Transaktionsprüfung bleibt ein eigenständiges, strikt isoliertes Arbeitspaket.

## Abnahmekriterien vor späterer Integration

1. Alle schreibfreien Tests PASS; keine unerwarteten Änderungen an bestehender Testanzahl oder Ruff.
2. Kritische Negativfälle (fehlender Job, falscher Hash, Pfadausbruch, fehlender Archiv-Schritt, geschlossenes Gate, doppelte Chunks) unter realen Rollen und Rollback geprüft.
3. Bei einem kontrollierten synthetischen Positivtest müssen Chunks, Schritt, Artefakt und Jobstatus gemeinsam zurückgerollt werden; kein persistierter Datenbankinhalt.
4. Fehler- und Reviewzustände, Embedding-Handoff und Crash-/Retry-Verhalten definieren, bevor der Adapter produktive `processing_job`-Daten bearbeitet.
5. Keine automatische Freigabe, kein Merge ohne explizite Architektur-/Testabnahme.


## Rollback-only Positivtest auf bestehender V2-Testdatenbank (22.11.2026, auf Poseidon bestanden)

**Testdatei:** `tests/test_job_pipeline_rollback_integration.py`. Kein weiterer Cluster und keine neue Datenbank nötig. Der Test akzeptiert ausschließlich `retro_rag_v2_test` mit `rag_v2_migrator_login`, Migration `0006`, **anfänglich geschlossenem** Gate. Alle Testdaten (inklusive Gate-Update) verbleiben in **einer einzigen Transaktion ohne Commit**, die in `finally` zurückgerollt wird. Der Test schreibt **nur ein synthetisches PDF** in ein privates temporäres Pytest-Verzeichnis, niemals in das vorhandene V2-Originalarchiv.

Prüfpfad: synthetisches archiviertes PDF → Dokumentversion + Importjob + `source_archived` → `prepare_job` → `_persist_contract_rows` → versionengebundene Chunks + `text_extracted` + `chunk_set` → **synthetische** 3D-Embeddings → technische Aktivierung → Rollback → unabhängige DB-Wiedereinwahl und Prüfung des geschlossenen Gates sowie der Test-IDs.

**Sicherheits-/Abnahmegrenzen:**

- Der produktive `persist_contract`-Einstieg behält die exakte Importer-Sessionprüfung und `assert_import_write_gate()`. `_persist_contract_rows` ist ein **interner, nicht als Anwendungsschnittstelle zulässiger** SQL-Kern für den Rollbacktest.
- Nur die Test-Transaktion setzt `writes_enabled=true`. Es gibt **keine persistente Freigabe**, keinen echten `--apply` und keine Arbeit an realen Archivdateien.
- Die technischen Embeddings sind Testvektoren; dieser Test belegt **nicht** das Funktionieren eines Embedding-Workers, eine semantisch korrekte Suche oder eine End-to-End-Verarbeitung mit realem WebDAV.
- Der bestehende C1-Konkurrenztest in `tests/test_version_activation_concurrency.py` ist **separat zu betrachten**: Er führt Commits aus und verlangt ausdrücklich einen isolierten Cluster. Ihn nicht gegen die laufende Testdatenbank umbiegen.
- Erst nach einem bestandenen Lauf und unabhängiger read-only SQL-Zählerprüfung wird die Rollback-Teststufe abgenommen.

**Echter Poseidon-Lauf nach Fast-forward auf `d393c44` (22.11.2026):**

```text
python -m ruff check .                 → All checks passed!
python -m pytest -q -rs                → 163 passed, 13 skipped in 0.71s
python -m pytest -q -rs tests/test_job_pipeline_rollback_integration.py
                                        → 1 passed in 0.22s
JOB_ROLLBACK_TEST_EXIT=0
```

Der gezielte Test lief im PostgreSQL-Netzwerk-Namespace mit `rag_v2_migrator_login` gegen `retro_rag_v2_test` (Migration 0006). Er prüfte den synthetischen PDF-/Job-/Chunk-/Artefakt-/Embedding-/Aktivierungspfad und danach Rollback sowie erneute DB-Anmeldung auf geschlossenen Gate-Zustand und Abwesenheit der künstlichen IDs. Die aktuelle reguläre Suite überspringt den Positivtest ohne `RETRO_V2_JOB_ROLLBACK_DSN`; sein separater Erfolg ist daher gesondert zu zählen. **Positiver SQL-Transaktionspfad PASS.**

**Noch ausstehend:** unabhängige administrative `BEGIN READ ONLY`-Zählerkontrolle nach diesem Lauf und ein echter gemeinsam durchlaufener WebDAV-/DB-Planungsprozess. Für C1-Concurrency ist der vorhandene Test wegen mehrerer verbindungsübergreifender Commits unverändert nicht für diesen Testdatenbank-Lauf geeignet. Die Embeddings wurden synthetisch erzeugt, kein Embedding-Worker bewiesen. Kein Gate persistent geöffnet.
