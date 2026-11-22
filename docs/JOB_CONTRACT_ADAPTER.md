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

**Nachkontrolle PASS (22.11.2026):** Nach diesem Lauf unabhängige administrative `BEGIN READ ONLY`-Sitzung als `codeanalyse` bestätigt: Migration `6`, `writes_enabled=f`, Sperrgrund `Parallelitätstest erfolgreich; Freigabe ausstehend`; `document`, `document_source`, `document_version`, `processing_job`, `processing_step`, `processing_artifact`, `chunk`, `chunk_embedding`, `review_item`, `knowledge_proposal` jeweils `0`. Weiter offen ist die reproduzierbare WebDAV-/DB-Importplanung. Für C1-Concurrency ist der vorhandene Test wegen mehrerer verbindungsübergreifender Commits unverändert nicht für diesen Testdatenbank-Lauf geeignet. Die Embeddings wurden synthetisch erzeugt, kein Embedding-Worker bewiesen. Kein Gate persistent geöffnet.


## WebDAV → PostgreSQL: reproduzierbarer schreibfreier Pipe-Test (22.11.2026, noch auszuführen)

`src/retro_rag/importer/plan_bridge.py` verbindet die beiden **bestehenden**, getrennten Netzwerkzugänge, ohne Passwörter oder Rohdateien zu speichern:

- **`fetch` auf Poseidon-Host:** WebDAV-Protokoll nur über HTTP-Loopback `127.0.0.1` / `localhost` (ausdrücklich keine Docker-Bridge); Auswahl genau einer `fileid`, bedingter Nextcloud-GET, Inhalts-Hash-Vergleich. Auf `stdout` wird eine binär gerahmte Nachricht aus kleinen JSON-Metadaten + maximal 1 MB Originalbytes ausgegeben. **Nicht direkt im Terminal ohne Pipe ausführen.**
- **`plan` im PostgreSQL-Netz-Namespace:** nimmt ausschließlich diese Pipe entgegen, prüft Längen, Identität und Hash erneut und verlangt `retro_rag_v2_test` sowie `rag_v2_importer_login` und ein geschlossenes Gate. Danach `BEGIN READ ONLY`, `plan_file()` und `ROLLBACK`.
- Kein `--apply`, keine Archivdatei, keine HBA-/Docker-Änderung, kein V1-/Nextcloud-Schreibzugriff. Im Test werden für die `fileid=480` ausschließlich die zuvor bestätigten Originalbytes erwartet.

**Noch nicht auf Poseidon ausgeführt.** Vorab `python -m ruff check .` und `python -m pytest -q -rs` auf dem separaten Featurebranch. Für den Live-Durchlauf sind die bereits funktionierenden `RETRO_V2_WEBDAV_*`-Variablen auf dem Host erforderlich und der Importer-Login wird nur im empfangenden Prozess benötigt.

```bash
cd ~/projects/retro-rag_v2
source .venv/bin/activate
git pull --ff-only
python -m ruff check .
python -m pytest -q tests/test_plan_bridge.py -rs
python -m pytest -q -rs

(
  set -o pipefail
  PG_PID="$(docker inspect -f '{{.State.Pid}}' codeanalyse-postgres)"
  test "$PG_PID" -gt 1 || exit 1
  read -rsp "V2-Importer-Passwort: " PGPASSWORD
  echo
  export PGPASSWORD
  export RETRO_V2_JOB_TEST_DSN='host=127.0.0.1 port=5432 dbname=retro_rag_v2_test user=rag_v2_importer_login connect_timeout=5'

  python -m retro_rag.importer.plan_bridge fetch \
    --source-key 480 \
    --expected-sha256 70e1b0ce4dc3d7cc3497763c4e907f1f3df65843cb3b5cef7c38bf8ee66efab6 |
  sudo --preserve-env=PGPASSWORD,RETRO_V2_JOB_TEST_DSN \
    nsenter --target "$PG_PID" --net -- \
    setpriv --reuid "$(id -u)" --regid "$(id -g)" --init-groups \
    "$(pwd)/.venv/bin/python" -m retro_rag.importer.plan_bridge plan \
      --expected-sha256 70e1b0ce4dc3d7cc3497763c4e907f1f3df65843cb3b5cef7c38bf8ee66efab6
  echo "WEB_DAV_DB_PLAN_EXIT=$?"
)
```

Bei bisher unveränderten Quell-/DB-Inhalten wird `READ ONLY planned_action=new source_key=480` erwartet. Den Abschluss nur nach tatsächlicher Betreiber-Ausgabe und unabhängiger DB-Gate-/Zählerkontrolle protokollieren.

**C1-Parallelität:** Der vorhandene `test_version_activation_concurrency.py` committet Fixtures und Gate-Freigabe und darf unverändert nicht auf dieser Datenbank ausgeführt werden. Eine vollständig reale Konkurrenz zweier erfolgreicher Versionenaktivierungen setzt sichtbare, committete Testversionen und ein verbindungsübergreifend offenes Gate voraus. Rollback-only mit geschlossenem Gate kann hingegen die Gate-Serialisierung/Blockierung und Ablehnung, nicht zwei erfolgreiche konkurrierende Aktivierungen, nachweisen. Diese beiden Abnahmekriterien nicht verwechseln.


### Reale Pipe-Planung auf Poseidon – PASS (22.11.2026)

Die Betreiberin führte den `fetch | nsenter ... plan`-Aufruf mit den dokumentierten WebDAV-Umgebungsvariablen am Host und dem dedizierten `rag_v2_importer_login` über das PostgreSQL-Netzwerk-Namespace aus. Die Brücke prüfte Nextcloud-`source_key=480` (`test-mainboard.md`) mit SHA-256 `70e1b0ce4dc3d7cc3497763c4e907f1f3df65843cb3b5cef7c38bf8ee66efab6` und plante ausschließlich lesend:

```text
READ ONLY planned_action=new source_key=480 sha256=70e1b0ce4dc3d7cc3497763c4e907f1f3df65843cb3b5cef7c38bf8ee66efab6
WEBDAV_DB_PLAN_EXIT=0
```

Damit ist die **reale WebDAV → PostgreSQL-Importplanung im selben Aufruf bestanden**. Die Pipe überträgt keine WebDAV-Zugangsdaten; die Datenbanksitzung verwendet `BEGIN READ ONLY`. Dieser Test archiviert keine Originale, erzeugt keine Jobs/Chunks und ist kein persistenter `--apply`. Eine unabhängige Gate-/Zählerprüfung **nach genau diesem** Lauf wurde noch nicht geliefert. Ferner wurde die Ruff-Typfehlerkorrektur `624dbbe` auf Poseidon noch nicht durch neue Testausgaben bestätigt.


## Gate-Sperrkonkurrenz auf `retro_rag_v2_test` – Poseidon-Test PASS (22.11.2026)

`tests/test_gate_concurrency_rollback.py` führt einen echten Test mit **drei gleichzeitigen Datenbankverbindungen** durch: zweimal `rag_v2_migrator_login` (Writer, Observer) und einmal `rag_v2_importer_login` (Reader). Die dedizierten Rollen/Passwörter sind erforderlich; ein echter `rag_v2_migrator`-`SET LOCAL ROLE` wird nur für das Rollback-Update verwendet.

**Ablauf:** Die Writer-Transaktion prüft Ausgangsdatenbank und initial geschlossenes Gate, aktualisiert die Gate-Zeile auf `true` **ohne Commit** und hält die exklusive Zeilensperre. Parallel wartet ein Importer-Aufruf von `rag_v2.assert_import_write_gate()` auf `FOR SHARE`. Der Observer muss den tatsächlichen PostgreSQL-Blockierer über `pg_blocking_pids` nachweisen. Dann rollt der Writer zurück; der Importer muss danach **SQLSTATE 42501** (`V2-Schreibsperre ist geschlossen`) erhalten. Abschließend sind Gate-Zustand und unveränderter Sperrgrund zu prüfen. Keine Dokument-/Chunk-/Archiv-Fixtures, kein `COMMIT` und kein Gate-Apply.

**Sicherer Start auf Poseidon nach lokaler Regression (nur wenn kein anderer Importer läuft):**

```bash
cd ~/projects/retro-rag_v2
source .venv/bin/activate
git pull --ff-only
python -m ruff check .
python -m pytest -q -rs

(
  PG_PID="$(docker inspect -f '{{.State.Pid}}' codeanalyse-postgres)"
  test "$PG_PID" -gt 1 || exit 1

  read -rsp "V2-Migrator-Passwort: " RETRO_V2_GATE_MIGRATOR_PASSWORD
  echo
  read -rsp "V2-Importer-Passwort: " RETRO_V2_GATE_IMPORTER_PASSWORD
  echo
  export RETRO_V2_GATE_MIGRATOR_PASSWORD RETRO_V2_GATE_IMPORTER_PASSWORD
  export RETRO_V2_GATE_MIGRATOR_DSN='host=127.0.0.1 port=5432 dbname=retro_rag_v2_test user=rag_v2_migrator_login connect_timeout=5'
  export RETRO_V2_GATE_IMPORTER_DSN='host=127.0.0.1 port=5432 dbname=retro_rag_v2_test user=rag_v2_importer_login connect_timeout=5'

  sudo --preserve-env=RETRO_V2_GATE_MIGRATOR_PASSWORD,RETRO_V2_GATE_IMPORTER_PASSWORD,RETRO_V2_GATE_MIGRATOR_DSN,RETRO_V2_GATE_IMPORTER_DSN \
    nsenter --target "$PG_PID" --net -- \
    setpriv --reuid "$(id -u)" --regid "$(id -g)" --init-groups \
    "$(pwd)/.venv/bin/python" -m pytest -q -rs tests/test_gate_concurrency_rollback.py
  echo "GATE_CONCURRENCY_EXIT=$?"
)
```

**Echter Poseidon-Lauf:** Nach lokalem Fast-forward auf `bdcd889` meldeten `python -m ruff check .` **All checks passed!** und `python -m pytest -q -rs` **174 passed, 14 skipped** (0,71 s), Git-Arbeitsbaum sauber. Der gezielte Gate-Test wurde anschließend im PostgreSQL-Netzwerk-Namespace unter Verwendung der echten `rag_v2_migrator_login`- und `rag_v2_importer_login`-Anmeldungen erfolgreich ausgeführt:

```text
. [100%]
1 passed in 0.15s
GATE_CONCURRENCY_EXIT=0
```

Die Assertions des Tests prüfen die PostgreSQL-Blockierer-PID, die erwartete Abweisung `SQLSTATE 42501` nach Rollback sowie den unveränderten Sperrgrund und `writes_enabled=false` durch die gesonderte Observer-Verbindung. **Nach diesem Test steht eine zusätzliche, unabhängige administrative `BEGIN READ ONLY`-Nachkontrolle der zehn Tabellenzähler noch aus.** Der Test erzeugt keine Dokument-/Chunk-Fixtures und hat keine persistente Gate-Freigabe durchgeführt.

**Diese Prüfung deckt die Gate-Serialisierung ab, nicht die eigentliche Konkurrenz zweier erfolgreicher C1-Aktivierungen.** Der bestehende C1-Test mit committed Fixtures ist weiterhin nur für eine entsprechend isolierte Umgebung sicher. Nach dem Betreiberlauf Gate und zehn Tabellensummen unabhängig per read-only SQL prüfen; erst danach Teilabnahme vermerken. Ohne beide Test-DSNs/Passwörter wird der neue Test übersprungen.
