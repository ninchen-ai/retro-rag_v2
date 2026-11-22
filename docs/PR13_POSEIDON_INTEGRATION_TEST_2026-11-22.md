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

**Elf Skips, keine Fehltests:** vier `tests/test_document_identity_integration.py` (`RETRO_V2_IDENTITY_TEST_DSN` fehlt), sechs `tests/test_version_activation_integration.py` (`RETRO_V2_C1_TEST_DSN` fehlt), einer `tests/test_version_activation_concurrency.py` (`RETRO_V2_C1_ISOLATED_DSN` fehlt). Die zehn rollback-only DB-Tests wurden **in diesem regulären Pytest-Durchlauf** übersprungen, anschließend aber separat erfolgreich ausgeführt (siehe Abschnitt 5.7). Der isolierte C1-Konkurrenztest ist nicht für den laufenden V2-Testcluster vorgesehen.

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

### 5.5 Nachtrag: tatsächliche HBA-Datei lesend überprüft (22.11.2026)

**Betreiberseitiger Nachweis:** `docker exec -i codeanalyse-postgres psql -X -v ON_ERROR_STOP=1 -U codeanalyse -d retro_rag_v2_test` mit `BEGIN READ ONLY`, `SHOW hba_file` über `current_setting('hba_file')`, `pg_hba_file_rules` und abschließendem `COMMIT`. Aktuelle HBA-Datei: **`/var/lib/postgresql/data/pg_hba.conf`**. Die Abfrage lieferte **17 wirksame/ausgewertete Regelzeilen ohne Fehlerwert** in der Spalte `error`.

| Zeile(n) | Typ / Ziel | Rollen | Adresse / Authentifizierung |
| --- | --- | --- | --- |
| 2 | local / all | `rag_v2_reader_login` | `reject` |
| 3–4 | host / `retro_rag_v2_test` | `rag_v2_reader_login` | `127.0.0.1`, `::1`; `scram-sha-256` |
| 5–6 | host / all | `rag_v2_reader_login` | `0.0.0.0`, `::`; `reject` |
| 125 | local / all | `rag_v2_importer_login`, `rag_v2_migrator_login` | `reject` |
| 126–127 | host / `retro_rag_v2_test` | `rag_v2_importer_login`, `rag_v2_migrator_login` | `127.0.0.1`, `::1`; `scram-sha-256` |
| 128–129 | host / all | `rag_v2_importer_login`, `rag_v2_migrator_login` | `0.0.0.0`, `::`; `reject` |
| 131, 133, 135 | local bzw. host / all | all | Socket bzw. `127.0.0.1`, `::1`; `trust` |
| 138–140 | lokale/Loopback-Replikation | all | `trust` |
| 142 | host / all | all | `all`; `scram-sha-256` |

**Auswertung:** Die V2-spezifischen Regeln stehen vor den allgemeinen Regeln. Die gelisteten HBA-Adressen wurden genau wie von `pg_hba_file_rules` ausgegeben übernommen; die Netzmasken sind in dieser Auswertung nicht separat ausgewiesen und werden hier nicht aus der Darstellung abgeleitet. Für die geprüfte Verbindung vom Poseidon-Host meldete PostgreSQL `172.19.0.1`, worauf `reject` für Importer greift. Die Container-interne Loopback-Anmeldung mit `rag_v2_importer_login` gelang. Damit ist die HBA-Grenze nicht nur anhand der Vorlage plausibel, sondern anhand des aktuellen Dateistands und des beobachteten Anmeldeverhaltens bestätigt. **Die SQL-Sicht auf die Datei allein bestätigt nicht den Zeitpunkt des letzten HBA-Reloads.** 

**Gate-Nachkontrolle:** `writes_enabled=f`, Grund `Parallelitätstest erfolgreich; Freigabe ausstehend`. Die Prüfung erfolgte rein lesend; kein Reload, kein Regel-Edit und keine DB-Schreiboperation. Weiter offen bleibt eine gemeinsame WebDAV-/DB-Netzwerkführung ohne pauschale Bridge-Freigabe.

Die vorherige Aussage in 5.3 („noch nicht ausgelesen“) beschreibt ausdrücklich den **früheren Zwischenstand vor diesem Nachtrag** und ist seit dieser Prüfung überholt.

### 5.6 Netzwerk-Topologie – Docker-Inspect auf Poseidon (22.11.2026)

Zusätzlicher, vom Betreiber direkt auf Poseidon gelieferter Lesebefund:

```text
docker inspect codeanalyse-postgres --format '...'
Netz: ai-network, IP: 172.19.0.4, Gateway: 172.19.0.1
docker port codeanalyse-postgres
5432/tcp -> 127.0.0.1:5432
```

**Schlussfolgerung:** PostgreSQL ist als Container `172.19.0.4` an `ai-network` angeschlossen; der Host veröffentlicht dessen Port 5432 nur auf Host-Loopback. Bei der Host-zu-Container-Verbindung über diese Portweiterleitung sieht PostgreSQL tatsächlich den Gateway-`172.19.0.1` als Quelladresse; die V2-HBA-Ausnahmeregeln für Container-`127.0.0.1` passen daher nicht. Das Port-Binding auf Host-Loopback schützt vor direktem externem Zugriff, **umgeht aber nicht** die HBA-Quelladresskontrolle.

**Keine Änderung** an HBA, Docker-Netzen, PostgreSQL-Ports, Anwendungsrechten oder Write-Gate erfolgt. Ein geeigneter gemeinsamer Netzwerkpfad für den nur lesenden `sync_cli`-Test ist weiterhin offen. Für getrennte rollback-only DB-Tests ist die bereits bekannte Ausführung im PostgreSQL-Netzwerk-Namespace mit echten, auf den V2-Testcluster begrenzten Loginrollen ein möglicher Weg; sie muss pro Durchlauf unabhängig verifiziert werden. Diese Ausgabe belegt noch nicht die Nextcloud-Erreichbarkeit aus dem PostgreSQL-Namespace. `ai-network` wird auch für andere Dienste verwendet: **keine pauschalen Subnetzfreigaben**.

### 5.7 Zehn DB-Integrationstests und unabhängige Rollback-Kontrolle (22.11.2026)

Auf Poseidon wurde nach Git-Fast-forward auf den Dokumentationsstand `196f74aa7c3e90fc8fe9908d128d97a9bc21c99a` der laufende Container `codeanalyse-postgres` mit PID `1942` bestätigt. Unter Nutzung von `nsenter --target "$PG_PID" --net` und anschließendem `setpriv` zurück auf den lokalen Benutzer wurden die beiden vorgesehenen Umgebungsvariablen `RETRO_V2_IDENTITY_TEST_DSN` und `RETRO_V2_C1_TEST_DSN` ausschließlich für `retro_rag_v2_test` mit `rag_v2_migrator_login` gesetzt. Das Passwort wurde interaktiv eingelesen und nicht im Git-Repository gespeichert.

```text
python -m pytest -q -rs \
  tests/test_document_identity_integration.py \
  tests/test_version_activation_integration.py

.......... [100%]
10 passed in 0.23s
DB_TEST_EXIT=0
```

Die Test-Fixtures aktivieren ein Gate nur **innerhalb der lokalen, am Ende zurückgerollten DB-Transaktion**; es gibt keine persistente Freigabe. Im Anschluss erfolgte durch eine **separate SQL-Sitzung** mit `BEGIN READ ONLY` / `COMMIT` eine unabhängige Zustandserhebung:

| Kontrollpunkt | Nachher |
| --- | --- |
| `MAX(rag_v2.schema_migration.version)` | `6` |
| `rag_v2.write_gate.writes_enabled` | `f` |
| Gate-Grund | `Parallelitätstest erfolgreich; Freigabe ausstehend` |
| `document` / `document_source` / `document_version` | jeweils `0` |
| `processing_job` / `review_item` / `knowledge_proposal` | jeweils `0` |

**Abnahme:** Zehn DB-Integrationstests auf diesem Integrationsstand erfolgreich; keine persistierten Fixtures in den sechs geprüften Tabellen und Gate weiterhin geschlossen. Zusammen mit dem separaten Basislauf sind **153 reguläre + 10 separate DB-Tests erfolgreich**; der isolierte Konkurrenztest wurde nicht ausgeführt. Die Datenbankkontrolle umfasst die ausdrücklich aufgeführten Tabellen und behauptet keinen vollständigen Vergleich aller 43 Tabellen.

### 5.8 Wiederholter Live-PDF/OCR-Test mit gezwungener Leerseiten-OCR (22.11.2026)

Nach Fast-forward auf den Dokumentationsstand `9ae76ea` erfolgte auf Poseidon erneut ein **schreibfreier** Durchlauf von `python -m retro_rag.importer.pdf_preview_cli` für Nextcloud `poseidon-nextcloud`, Datei-ID `172`, `cubx-103.pdf`, mit geprüftem SHA-256 `f10dc04911aa75241adcb29731af62fc4ce4c5e5a21b0a69ff621778c784f82b`. Parameter: `--ocr-mode auto --ocr-page 111 --ocr-page 112 --ocr-language eng+deu --ocr-dpi 200`.

| Wert | Live-Ergebnis |
| --- | --- |
| `page_count` / `chunk_count` | `112` / `114` |
| `ocr_pages` | `[111]` |
| `ocr_failed_pages` | `[112]` |
| `warnings` | `Seite 112: OCR lieferte keinen Text` |
| `indexing_allowed` / `fact_proposal_count` | `false` / `0` |
| `PDF_PREVIEW_EXIT` | `0` |

**Korrekte Einordnung:** Der Goldstandard und die Roadmap vom **21.11.2026** hatten bereits gezeigt, dass Seite **112 eine weiße Leerseite** ist und deshalb keine sinnvollen OCR-Inhalte erwartet werden. Die Warnung entsteht durch den ausdrücklich angeforderten OCR-Versuch auf dieser Leerseite; sie ist **kein nachgewiesener Verlust relevanten Texts**. Seite **111** wurde erkannt, ohne dass daraus eine Vollseiten-CER/WER-Freigabe folgt. Bereits am **21.11.2026** wurde ein separater Live-Kontrolllauf mit ausschließlich `ocr_pages={111}` dokumentiert: `ocr_pages=[111]`, `ocr_failed_pages=[]`, `warnings=[]`, 114 Chunks, Indexierung weiterhin gesperrt. Diese Ergebnisse dürfen nicht als Widerspruch oder als neue unbehobene Regression dargestellt werden.

**Abnahmegrenze:** Exitcode 0 bedeutet erfolgreiche schreibfreie Vorschau einschließlich korrekt ausgewiesenem OCR-Teilfehler, nicht OCR-Erfolg auf allen angeforderten Seiten. Der Vorschauvertrag führt zu keiner Speicherung, Freigabe oder Indexierung. Offene fachliche Prüfung bleibt die manuell belegte CER/WER-Qualität und technische Terminologie auf Seite 111 sowie die persistente Gesamtintegration. Der Abschnitt ergänzt den früheren OCR-Nachtrag in [`PROJECT_ROADMAP.md`](PROJECT_ROADMAP.md), ohne den historischen Befund zu überschreiben.

### 5.9 Fast-Forward-Übernahme und Abschluss-Regressionslauf (22.11.2026)

Der separat entwickelte Job-Adapter-Branch `feat/processing-job-contract-adapter-2026-11-22` wurde nach Prüfung eines reinen Vorwärtsstands (**26 Commits voraus, 0 zurück**) per **Fast-Forward** auf `integration/pdf-ocr-webdav-2026-11-21` übernommen. Die GitHub-Branchspitze wurde auf `dfaa75d8a11dd175acb6dff6dd6d87575979be25` verifiziert; PR #13 bleibt **open / Draft / unmerged** gegen `integration/import-pipeline-2026-11-09`. Das ist ausdrücklich **kein Merge von PR #13 in den Basisbranch**.

Auf Poseidon erfolgte danach die unabhängige Aktualisierung des **PR-Branches** auf genau `dfaa75d` und der reguläre Regressionslauf:

```text
git branch --show-current        integration/pdf-ocr-webdav-2026-11-21
git rev-parse --short HEAD       dfaa75d
python -m ruff check .          All checks passed!
python -m pytest -q -rs         174 passed, 14 skipped in 0.71s
python -m pip check             No broken requirements found.
git diff --check                keine Ausgabe
git status --short              keine Ausgabe
```

Die 14 Skips sind **erwartete, nicht aktivierte** DB-/Konkurrenztests im Standardlauf; die früheren echten Verbindungs- und Rollbackprüfungen sind als **gesonderte Läufe** auf dem Featurebranch ausgeführt und nach dokumentiertem Fast-Forward inhaltlich unverändert übernommen worden. Der Standardlauf allein behauptet keine erneute Ausführung sämtlicher DB-Tests auf der aktuellen PR-Branchspitze.

**Zusätzliche gesonderte Poseidon-Nachweise auf dem später übernommenen Featurebranch** (siehe [`JOB_CONTRACT_ADAPTER.md`](JOB_CONTRACT_ADAPTER.md)):

| Nachweis | Ergebnis |
| --- | --- |
| Live Nextcloud `fileid=480` → Hashvalidierung → DB-`plan_file` über begrenzte Pipe | `READ ONLY planned_action=new`, Exitcode `0` |
| Importer-Login + geschlossenes Gate, `persist_contract` | Erwartete SQLSTATE `42501`, `1 passed` |
| Synthetisches PDF → Importvertrag → Chunks/Steps/Artefakte → Test-Embeddings → Aktivierung | Transaktionaler Rollbacktest `1 passed`, Exitcode `0` |
| Zwei-Rollen-Gate-Serialisierung mit nachgewiesener PostgreSQL-Blockierung | `1 passed`, Exitcode `0` |
| Administrative unabhängige Nachkontrolle nach diesen DB-Tests | Migration `6`, Gate `false`, zehn Import-/Reviewtabellen je `0` |

Der Synthese-Test verwendet **synthetische Embeddings**, keinen echten Embedding-Worker. Die Gate-Serialisierung ist **kein** Nachweis zweier erfolgreicher konkurrierender C1-Aktivierungen. Die Live-WebDAV-Brücke testet **read-only Planung**, keinen `--apply`, kein Archivieren und keine persistente Ende-zu-Ende-Indexierung. **Keine Gate-/HBA-/Netzwerkänderung oder produktive Freigabe.**

## 6. Abschlusstand und verbleibende Abnahmen von PR #13 (22.11.2026)

**Abgeschlossen / nachgewiesen:** Basis- und Abschlussregression auf Poseidon, Ruff und Abhängigkeiten; zehn gesonderte rollback-only DB-Integrationstests, read-only Live-WebDAV-/DB-Einzeldateiplanung über `plan_bridge`, reale PDF-/OCR-Vorschau, synthetische Job-/Chunk-/Artefakt-/Embedding-/Aktivierungskette sowie Gate-Serialisierung einschließlich unabhängiger DB-Nachkontrollen. Alle diese Befunde gelten für die dokumentierten konkreten Testläufe; die auf PR #13 übernommene Branchspitze hat zusätzlich die **vollständige Standard-Regression** bestanden (Abschnitt 5.9).

**Weiter getrennt offen:**

1. **C1-Konkurrenz zweier erfolgreicher Aktivierungen:** Der bestehende Test committet Fixtures und verlangt ein eigenes isoliertes Cluster. Der auf der bestehenden Testdatenbank erfolgreich getestete **Gate-Blockierungs-/Ablehnungstest** ist kein Ersatz dafür. Keine Änderung der vorhandenen C1-Testschutzschranke ohne gesonderte Entscheidung.
2. **Echte Embedding-Erzeugung, persistente Job-Finalisierung und vollständiger E2E-Import:** Der synthetische Rollbacktest beweist SQL-Verkettung und technische Aktivierung, nicht die reale automatische Indexierung. Der WebDAV-Durchlauf war `READ ONLY`, ohne `--apply` oder Originalarchivierung.
3. **OCR-Qualitätsoptimierung und vollständiger Goldstandard:** Die Extraktion und gezielte OCR-Seitenfälle sind geprüft; die vollständig manuell bestätigte Vollseiten-CER/WER-Referenz ist eine separate Qualitätssicherung.
4. **Archiv-Mount-/Backup-Lesekontrolle:** Vor einer schreibenden Freigabe nochmals mit tatsächlichen Mount- und Backup-Nachweisen validieren.
5. **Betriebliche Freigabe:** Keine automatische Agenten-/Faktenfreigabe, kein produktiver Import und kein Merge von PR #13 in seinen Basisbranch oder `main` ohne ausdrückliche Freigabe.

**Freigabeschranke:** PR #13 bleibt **Draft**, `rag_v2.write_gate.writes_enabled=false`; keine HBA-, Docker-, Archiv- oder Betriebskonfigurationsänderung durch diese Abnahme.


## 7. Nachtrag 22.11.2026 – Real-Dokument-E2E im isolierten PR13-Cluster

**Umgebung:** neuer Container `retro-rag-v2-pr13-e2e` mit `--network none`,
PostgreSQL 16.15/pgvector, Clusterkennung
`retro-rag-v2-pr13-e2e-isolated`, privater Unix-Socket
`/data/retro-rag/v2/e2e-isolated/socket-v2`, eigene Datenbank
`retro_rag_v2_test`. Migrationen `0001` bis `0006` aus dem Repository
wurden dort erfolgreich angewandt. Unabhängige Kontrolle: **6 Migrationen,
43 Tabellen, 15 Entitätstypen, Write-Gate false**. Der Cluster ist nicht
der laufende `codeanalyse-postgres`; keine HBA-Änderung und keine
Netzwerkfreigabe. `rag_v2_migrator_login` nur im isolierten Cluster aktiviert.
Die Testtransaktionen öffnen das **isolierte** Gate ausschließlich
uncommitted und führen im `finally` einen Rollback aus.

### 7.1 Echte Markdown-Quelle – PASS

- Nextcloud `poseidon-nextcloud`, Datei-ID `480`,
  `test-mainboard.md`, **371 Bytes**; SHA-256
  `70e1b0ce4dc3d7cc3497763c4e907f1f3df65843cb3b5cef7c38bf8ee66efab6`.
- SHA-verifizierte lokale Staging-Kopie; `stage_file` im
  isolierten, rollback-only Test; archivierte Testkopie, `prepare_job`,
  Chunk-Persistierung, reale lokale Ollama-Embeddings mit
  `nomic-embed-text` (768 Dimensionen), technische Job-Finalisierung
  und `activate_version` im Testcode.
- Der erste Testlauf schlug **ausschließlich** wegen einer fehlerhaften
  Testannahme fehl: Der Markdown-Adapter liefert absichtlich die Warnung,
  dass Quellenautorisierung, Schema- und Konfliktprüfung noch nicht
  implementiert sind. Die Testassertion wurde in Commit `3c7aae1`
  korrigiert, **nicht** die Warnung entfernt. `indexing_allowed=false`
  bleibt zwingend.
- Nach erneutem Start: **`1 passed in 0.70s`**, anschließend getrennte
  DB-Verbindung: Gate `false`, Dokumente/Versionen/Jobs `(0,0,0)`.
  Abschlussausgabe `PR13 MARKDOWN-E2E PASS`.

### 7.2 Echtes PDF mit OCR und 114 Ollama-Embeddings – PASS

- Nextcloud `poseidon-nextcloud`, Datei-ID `172`,
  `cubx-103.pdf`, **4.914.302 Bytes**, SHA-256
  `f10dc04911aa75241adcb29731af62fc4ce4c5e5a21b0a69ff621778c784f82b`.
  SHA sowohl direkt nach WebDAV-GET als auch unabhängig an der
  lokalen Kopie unter
  `/data/retro-rag/v2/e2e-isolated/cubx-103.pdf` bestätigt,
  Dateimodus `0600`.
- Test in Commit `7149ae3`:
  `tests/test_real_pdf_ocr_e2e_isolated.py`. PDF-Adapter mit
  `ocr_mode=auto, ocr_pages={111}`:
  **112 Seiten, 114 Chunks, OCR erfolgreich auf Seite 111,
  keine fehlgeschlagenen OCR-Seiten, keine Warnungen**.
  Weiße Seite 112 wurde **nicht** zwangsweise per OCR verarbeitet.
- Für alle 114 Chunks echte lokale Ollama-`nomic-embed-text`-Embeddings
  mit **768 Dimensionen** erzeugt und nur im isolierten,
  uncommitted Test in `pgvector` geschrieben. Vor technischer
  Job-Finalisierung verhindert `activate_version` die Aktivierung;
  nach im Test explizit gesetzten technischen Job-/Versionsstatus
  funktioniert die Aktivierung. Das ist **keine** automatische
  Produktionsfreigabe: `indexing_allowed=false`, kein
  tatsächlicher Embedding-/Finalisierungsworker implementiert.
- Auf Poseidon bestätigt: `ruff check` für die neue Testdatei
  **PASS**; `pytest`: **`1 passed in 21.46s`**;
  nachfolgende unabhängige DB-Sitzung:
  Write-Gate `false` und Dokumente/Versionen/Jobs/Chunks/Embeddings
  `(0,0,0,0,0)`. Abschlussausgabe `PR13 PDF/OCR-E2E PASS`.

### 7.3 Abnahmegrenzen und Folgeschritte

Die neuen E2E-Prüfungen schließen die zuvor fehlende
**technische Real-Dokument-Verkettung als isolierte
Rollback-Smoke-Tests**. Sie ersetzen **nicht** einen produktiven
WebDAV-`--apply`, einen dauerhaft laufenden Verarbeitungsworker,
eine automatisierte Indexierungs-/Faktenfreigabe, eine komplette
OCR-Qualitätsfreigabe oder eine persistente End-to-End-Einspielung.
Die isolierte Transaktions-Aktivierung ist **nicht** mit dem
Einverständnis zur automatischen Veröffentlichung gleichzusetzen.

Vor Abschluss dieses PR-Reviews:
- Abschlussregression einschließlich `ruff check .`,
  `pytest -q -rs`, `pip check`, `git diff --check`,
  Git-Status **auf dem aktuellen PR-Head** erneut auf Poseidon ausführen;
  deren Ergebnis liegt für Commit `7149ae3` noch nicht vor.
- Originalarchiv-Mount und **Backup-Lesbarkeit** unabhängig prüfen.
  Das Verzeichnis `/data` ist als `/dev/sda1` ext4 gemountet,
  `originals` Modus `700`; ein unabhängiger Restore ist nicht
  hiermit bewiesen.
- Isolierten Testcontainer nach dokumentierter Schlusskontrolle
  aufräumen (seine Daten liegen in einem tmpfs).
- GitHub PR #13 bleibt **Draft, open, unmerged**. Aktuell meldet
  GitHub zudem **mergeable=false**; vor einer Freigabe muss
  diese Aussage anhand der PR-Konflikt-/Prüfdetails geklärt werden.
  Kein Merge und keine Produktivschaltung durch diese Tests.


## 8. Schlussregression und bewusste Abgrenzung der Backup-Aufgabe (22.11.2026)

**Poseidon, Code- und Dokumentationsstand `1f311b3`:** Fast-forward,
`python -m ruff check .` **PASS**;
`python -m pytest -q -rs` **174 passed, 16 skipped in 0.71s**;
`python -m pip check` **No broken requirements found**;
`git diff --check` ohne Ausgabe; `git status --short` leer.
Branch `integration/pdf-ocr-webdav-2026-11-21`, HEAD `1f311b3`.
Die 16 Skips betreffen nicht aktivierte, separat opt-in ausgeführte
DB-/E2E-Tests; insbesondere die beiden echten Markdown- und
CUBX-PDF/OCR-Tests bestanden zuvor einzeln mit `1 passed`.
Die Schlussregression fand **vor diesem Dokumentationsnachtrag**
statt; eine erneute Regression nach reinen Markdown-Dokumentationscommits
ist damit nicht behauptet.

**Originalarchiv:** `findmnt -T /data/retro-rag/v2/originals` zeigte
`/dev/sda1` (ext4, rw,noatime) an `/data`, und
`stat` ergab `700 nina:nina`: Mount-/Berechtigungsprüfung **PASS**.

**Backup nicht abgenommen, ausdrücklich vertagt:**
Drei lokale V2-`*.dump`-Dateien sind vorhanden (09.11., 11.11. und
20.11.2026). Der zunächst versuchte Lesetest konnte wegen
fehlendem `pg_restore` auf dem Poseidon-Host **nicht ausgeführt**
werden; die ausgegebenen FAIL-Zeilen sind daher **kein Beleg beschädigter
Dumps**. `borg-backup.service` meldete für den 22.11.2026
`Result=exit-code`, `ExecMainStatus=1`; laut Betreiber war das
Rotationsmedium zu diesem Termin nicht eingelegt, ist nun wieder
eingelegt. Ein erfolgreicher Nachhol- oder Restore-Lauf ist nicht belegt.
Wichtiger: Im gesonderten Infrastruktur-Repository umfasst die
Borg-Quellliste bislang **nicht** `/data/retro-rag/v2`; auch ein
wiederkehrender Dump von `retro_rag_v2_test` fehlt. Die
Backup-Erweiterung und Restore-Abnahme sind als **separater späterer
Roadmap-Punkt** dokumentiert; sie werden **nicht als erledigt
ausgewiesen** und sollen den technischen Testabschluss von PR #13
nicht blockieren. Vor produktivem Schreibbetrieb gesondert freigeben.

**GitHub-Prüfung:** PR #13 weiterhin `open`, `Draft`, `merged=false`,
auf `integration/import-pipeline-2026-11-09`, zuletzt
`mergeable=true`. Der frühere `mergeable=false`-Zwischenwert ist
durch den neueren Befund überholt. **Keine Merge-/Produktivfreigabe**
aus der Testabnahme ableiten.

**Restarbeiten vor formalem Abschluss:** isolierten temporären
Testcontainer `retro-rag-v2-pr13-e2e` mit tmpfs-Datenbank sauber
stoppen/entfernen; dann bewusste Entscheidung zum
Draft-/Merge-Status. Quellenautorisierung, automatischer Worker,
fachliche Freigabe und OCR-Qualitätsoptimierung bleiben eigene
Entwicklungsaufgaben und werden nicht als durch den Smoke-Test
implementiert bezeichnet.
