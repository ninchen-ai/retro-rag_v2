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

`tests/test_job_pipeline_integration.py` enthält jetzt einen **explizit aktivierbaren** Negativtest. Er stellt eine echte `psycopg`-Verbindung mit `rag_v2_importer_login` zu `retro_rag_v2_test` her, kontrolliert das geschlossenene Write-Gate und ruft `persist_contract()` mit synthetischem Text und nicht existierenden Job-/Versions-IDs auf. Erwartet ist **SQLSTATE 42501** (`V2-Schreibsperre ist geschlossen`). Eine Rolle, Datenbank oder Gate-Freigabe wird weder erstellt noch geändert. Der synthetische Originaltext liegt nur in einer temporären lokalen Pytest-Datei. Die Verbindung führt im `finally` ein Rollback aus.

**Noch nicht auf Poseidon ausgeführt.** Für den Test einen gesicherten Importer-Login und den bereits geprüften PostgreSQL-Netzwerk-Namespace nutzen; keine Ausweitung des Docker-HBA-Netzes.

```bash
cd ~/projects/retro-rag_v2
git pull --ff-only
source .venv/bin/activate

python -m ruff check .
python -m pytest -q -rs
```

Die reguläre Suite überspringt diesen realen DB-Test ohne `RETRO_V2_JOB_TEST_DSN`; der Umgebungsschlüssel wird nur für eine explizite Testausführung gesetzt. Der negative SQL-Test darf **nicht** als erfolgreicher positiver Chunk-Apply gewertet werden. Ein Positivtest benötigt eine separate Isolation; auf der vorhandenen V2-Testdatenbank wird das Gate nicht geöffnet. Nach dem Negativlauf sind das Gate und die Tabellenzähler über eine **zweite** DB-Sitzung unabhängig zu kontrollieren.

## Abnahmekriterien vor späterer Integration

1. Alle schreibfreien Tests PASS; keine unerwarteten Änderungen an bestehender Testanzahl oder Ruff.
2. Kritische Negativfälle (fehlender Job, falscher Hash, Pfadausbruch, fehlender Archiv-Schritt, geschlossenes Gate, doppelte Chunks) unter realen Rollen und Rollback geprüft.
3. Bei einem kontrollierten synthetischen Positivtest müssen Chunks, Schritt, Artefakt und Jobstatus gemeinsam zurückgerollt werden; kein persistierter Datenbankinhalt.
4. Fehler- und Reviewzustände, Embedding-Handoff und Crash-/Retry-Verhalten definieren, bevor der Adapter produktive `processing_job`-Daten bearbeitet.
5. Keine automatische Freigabe, kein Merge ohne explizite Architektur-/Testabnahme.
