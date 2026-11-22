# PR #13 – Poseidon-Integrationsprüfung (22.11.2026)

**Status:** Teilabnahme, **keine Merge-/Produktivfreigabe**. Betreiberseitige Terminalausgaben vom 22.11.2026, in diesem Bericht nachvollziehbar eingeordnet. Die Prüfungen fanden auf Poseidon statt; die Repository-Dokumentation wurde nach den Prüfungen ergänzt.

- Repository: `ninchen-ai/retro-rag_v2`
- Draft PR: [#13](https://github.com/ninchen-ai/retro-rag_v2/pull/13)
- geprüfter Branch: `integration/pdf-ocr-webdav-2026-11-21`
- geprüfter **Code-Commit vor diesem Dokumentationsnachtrag**: `7abbc34c85f5b06b0aff032b97672498d9b653cf`
- Zielbranch: `integration/import-pipeline-2026-11-09`
- Bereich: PDF/OCR, kontrollierter WebDAV-Einzelabruf, Rollen- und HBA-Verbindungsweg, V2-Testdatenbank
- Grundsatz: **Write-Gate bleibt geschlossen**, kein `--apply`, keine DDL/HBA-Änderungen, keine Produktivfreigabe.

## 1. Regression und installierte Abhängigkeiten

| Prüfung | Nachweis / Ergebnis |
| --- | --- |
| Git | Fast-forward auf `7abbc34`; `git branch --show-current` korrekt; `git diff --check` ohne Ausgabe; `git status --short` leer |
| Python | 3.13.5 |
| pytest / Ruff | pytest 9.2.0; Ruff 0.17.4 |
| weitere Pakete | pydantic 2.14.3; PyYAML 6.0.3; psycopg 3.3.8; PyMuPDF 1.28.2 |
| `python -m pip check` | `No broken requirements found.` |
| `python -m pytest -q -rs` | **153 passed, 11 skipped in 0.67s**, Exitcode 0 |
| `python -m ruff check .` | **All checks passed!**, Exitcode 0 |

**Elf Skips, keine Fehltests:** vier `tests/test_document_identity_integration.py` (`RETRO_V2_IDENTITY_TEST_DSN` fehlt), sechs `tests/test_version_activation_integration.py` (`RETRO_V2_C1_TEST_DSN` fehlt), einer `tests/test_version_activation_concurrency.py` (`RETRO_V2_C1_ISOLATED_DSN` fehlt). Die zehn rollback-only DB-Tests wurden **in diesem erneuten Durchlauf** nicht ausgeführt; frühere erfolgreiche Tests auf einem älteren Staging-Commit sind davon zu unterscheiden. Der isolierte C1-Konkurrenztest ist nicht für den laufenden V2-Testcluster vorgesehen.

## 2. Echte OCR-Laufzeit (ohne DB und Originalarchiv)

- Tesseract **5.5.0**, Sprachen `deu`, `eng`, `osd`.
- Synthetische Bild-PDF-Seite aus im Speicher gerendertem `ASUS CUBX AGP 4X` erstellt (200 DPI, ohne eingebetteten Quelltext).
- `retro_rag.importer.pdf_ocr.extract_page_text(page, mode="auto", language="eng+deu", dpi=200)`: `status=ocr`, Text **`ASUS CUBX AGP 4X`**, `warning=None`, Exitcode **0**.
- **Bewiesen:** PyMuPDF/Tesseract-Laufzeitintegration für dieses synthetische Beispiel. **Nicht bewiesen:** OCR-Qualität an realen CUBX-Scans, CER/WER, komplizierte Seitenlayouts, vollständige PDF-/Job-/Index-Pipeline oder automatische Freigabe.

## 3. Datenbank-Ausgangszustand – unabhängige read-only SQL-Abfrage

Über `docker exec -i codeanalyse-postgres psql -X -v ON_ERROR_STOP=1 -U codeanalyse -d retro_rag_v2_test`, Transaktion `BEGIN READ ONLY` bis `COMMIT`:

- `current_database() = retro_rag_v2_test`
- `MAX(rag_v2.schema_migration.version) = 6`
- `rag_v2.write_gate`: `writes_enabled = false`, `reason = 'Parallelitätstest erfolgreich; Freigabe ausstehend'`
- Anzahl `document = 0`, `document_source = 0`, `document_version = 0`, `processing_job = 0`, `review_item = 0`.

Dies ist ein bestätigter **Ausgangszustand**, kein nachfolgender Test-Apply- oder Rollback-Nachweis.

## 4. WebDAV-Live-Leseprüfung (ohne Datenbank)

Zunächst waren alle fünf für `sync_cli` benötigten Umgebungsvariablen in der neuen Shell **nicht gesetzt**: `RETRO_V2_WEBDAV_URL`, `RETRO_V2_WEBDAV_USER`, `RETRO_V2_WEBDAV_APP_PASSWORD`, `RETRO_V2_NEXTCLOUD_INSTANCE_ID`, `RETRO_V2_DATABASE_DSN`. Sie wurden für den WebDAV-Einzeltest temporär bereitgestellt.

`WebDAV.list_files()` fand **40** geeignete Dateien. `fileid=480` war genau einmal vorhanden und bezeichnete `test-mainboard.md`; `WebDAV.download(..., max_bytes=1_000_000)` las **371 Bytes**. SHA-256:

```text
70e1b0ce4dc3d7cc3497763c4e907f1f3df65843cb3b5cef7c38bf8ee66efab6
```

Der Hash stimmt mit dem früher dokumentierten Einzeldatei-Abruf überein. Abschlussmeldung `WEBDAV_READ_ONLY_PASS`. **Keine DB-Verbindung und kein `sync_cli`-Planungslauf in dieser Prüfung**. Aus der Dateizahl 40 folgt kein Nachweis, dass alle Ausschlussregeln für den gesamten Nextcloud-Bestand live korrekt sind; diese sind separat zu kontrollieren.

## 5. PostgreSQL-HBA: bestätigter Zugriffsunterschied

### 5.1 Beobachtung vom Host

Verbindung aus der Poseidon-`.venv` mittels psycopg 3.3.8 und `rag_v2_importer_login` an `127.0.0.1:5432`, Datenbank `retro_rag_v2_test`, **abgewiesen**:

```text
psycopg.OperationalError: connection failed:
connection to server at "127.0.0.1", port 5432 failed:
FATAL: pg_hba.conf rejects connection for host "172.19.0.1",
user "rag_v2_importer_login", database "retro_rag_v2_test", no encryption
```

**Befund:** Der Server meldet als Client-Adresse `172.19.0.1`, **nicht** `127.0.0.1`. Die Docker-Portweiterleitung bzw. Netzwerktopologie verändert den aus PostgreSQL sichtbaren Quellweg. `no encryption` beschreibt die unverschlüsselte Verbindungsvariante in der Fehlermeldung und ist **für sich allein kein Nachweis**, dass TLS zwingend erforderlich ist oder die Zugangsdaten falsch sind. Der Host-to-Container-Zugriff ist auf diesem Pfad derzeit nicht autorisiert.

### 5.2 Gegenprobe innerhalb des PostgreSQL-Containers

```bash
docker exec -it codeanalyse-postgres \
  psql -X -W -v ON_ERROR_STOP=1 \
  -h 127.0.0.1 \
  -U rag_v2_importer_login \
  -d retro_rag_v2_test \
  -c "SELECT current_database(), session_user, current_user;" \
  -c "SELECT writes_enabled, reason FROM rag_v2.write_gate WHERE id=true;"
```

**Erfolgreich authentifiziert:** `current_database=retro_rag_v2_test`, `session_user=current_user=rag_v2_importer_login`. Gate `writes_enabled=f` bei unverändertem Sperrgrund. Der Login funktioniert somit auf dem erlaubten **Container-Loopback-Pfad** mit seinem Passwort. Das widerlegt einen generellen Defekt der Rolle, beweist aber nicht, dass vom Host derselbe Weg erreichbar ist.

### 5.3 Dokumentierte HBA-Vorlage vs. tatsächlich geladene Regeln

Die versionierte Vorlage [`deploy/postgresql/pg_hba_v2_example.conf`](../deploy/postgresql/pg_hba_v2_example.conf) sieht für die sieben V2-Logins in dieser Reihenfolge vor:

1. `local all <V2-Logins> reject` (Unix-Sockets für diese Rollen sperren);
2. `host retro_rag_v2,retro_rag_v2_test <V2-Logins> 127.0.0.1/32 scram-sha-256`;
3. entsprechende `::1/128`-Regel;
4. abschließende `host all <V2-Logins> 0.0.0.0/0 reject` und `::/0 reject`.

Die erste passende HBA-Regel gewinnt. **`172.19.0.1` wird von der dokumentierten Loopback-Freigabe nicht erfasst.** Eine auf diesen Client passende `reject`-Regel ist daher eine zur Fehlermeldung passende Erklärung. Die **aktuell geladene** `pg_hba.conf` bzw. `pg_hba_file_rules` wurde in diesem Durchlauf **nicht ausgelesen**; es ist deshalb nicht belegt, dass die Live-Datei bytegleich der Vorlage ist, welche Regelzeile tatsächlich getroffen hat oder ob darüber hinaus weitere Regeln bestehen.

### 5.4 Sicherheitsentscheidung und offene read-only Diagnose

- **Keine** pauschale Freigabe von `172.19.0.0/16`, kein Umstellen auf `trust`, keine Veränderung an V1-/Nextcloud-Regeln und keine ungesicherte Docker-Portfreigabe.
- **Keine** HBA-Dateiänderung, kein `pg_reload_conf()`, kein TLS-/Auth-Wechsel in dieser Abnahme.
- Für den vollständigen `sync_cli`-Read-only-Lauf ist ein **gemeinsamer, minimal privilegierter Netzwerkpfad** erforderlich, über den derselbe Prozess WebDAV und den Importer-DB-Login erreichen kann. Der Container-Loopback allein beweist keine Nextcloud-Erreichbarkeit.
- Vor einem Architekturentscheid: Live-Regeln **nur lesend** einschließlich Reihenfolge/Fehler prüfen, Netzwerktopologie und Quelladressen feststellen. Beispiel (als administrative lokale SQL-Abfrage, Ausgabe vor Veröffentlichung auf sensible Netzangaben prüfen):

```bash
docker exec codeanalyse-postgres \
  psql -X -v ON_ERROR_STOP=1 -U codeanalyse -d retro_rag_v2_test \
  -c "SHOW hba_file;" \
  -c "SELECT line_number, type, database, user_name, address, auth_method, error FROM pg_hba_file_rules ORDER BY line_number;"
```

`pg_hba_file_rules` liest den Dateistand; dies **beweist allein nicht**, dass neu editierte Regeln bereits vom Server geladen wurden. Für eine HBA-Änderung wären gesonderte Prüfung, Freigabe und Reload erforderlich. Bis dahin ist der aktuelle Zugriffspfad **bewusst nicht zu erweitern**.

## 6. Offene Abnahme von PR #13

1. **Zehn** rollback-only DB-Integrationstests auf dem geprüften Branch ausführen, sichere DSNs nur an den vorgesehenen Migrator-Login/Test-DB binden; nach Test per unabhängiger SQL-Sitzung Gate und Tabellenzähler vergleichen. Der isolierte C1-Konkurrenztest bleibt separat.
2. Gemeinsamen, sicheren WebDAV-/DB-Lesezugriff herstellen und `sync_cli --source-key 480 --max-bytes 1000000` **ohne `--apply`** ausführen; Ergebnis und unveränderte DB prüfen.
3. Echte PDF-/OCR-Goldstandardfälle inkl. Fehler- und Reviewpfad; Tesseract, DocLayout und optionale Modelle getrennt bewerten.
4. Archiv-Mount, Originalintegrität und vorhandene Backups lesend validieren; keine Archivänderung aus diesem Test.
5. Zusammenhängende Datenflussprüfung WebDAV → PDF/OCR → Staging → Jobs/Artefakte → Chunks/Embeddings → Aktivierung bleibt offen. Bestehende Unit-Tests beweisen keine vollständige E2E-Abnahme.

**Freigabeschranke:** PR #13 bleibt Draft, kein Merge in regulären Integrationsbranch oder `main`; `rag_v2.write_gate.writes_enabled=false`. Das Protokoll dokumentiert Ergebnisse und eine HBA-Zugriffsgrenze, **keine Konfigurationsänderung**.
