# Retro-RAG V2 – WebDAV- und Archivabsicherung

Stand: 09.11.2026
Branch: fix/atomic-original-archive
Basis-Commit: 9418c0f

## 1. Architekturentscheidung

Die ursprüngliche Architektur bleibt bestehen.

- Nextcloud ist führende Quelle für Originaldokumente.
- Neue und geänderte Dokumentinhalte erhalten dauerhafte Archivkopien.
- Identische Inhalte werden anhand SHA-256 wiederverwendet.
- PostgreSQL speichert Dokumentidentitäten, Versionen,
  Archiv-URIs, Verarbeitungsschritte und später RAG-Daten.
- Originaldateien werden nicht als Binärdaten in PostgreSQL gespeichert.
- Das Archiv soll Bestandteil der Borg-Sicherung werden.

## 2. Dauerhaftes Originalarchiv

Server: Poseidon
Datenträger: TOSHIBA DT01ACA100
Partition: /dev/sda1
Dateisystem: ext4
UUID: 0ad31014-cd69-4b01-b177-b30bfd832481
Mountpoint: /data

Verzeichnisse:

- /data/retro-rag/v2/originals
- /data/retro-rag/v2/staging
- /data/retro-rag/v2/quarantine

Eigentümer: nina:nina
Berechtigungen: 0700

Die Verzeichnisse wurden angelegt und der Mountpoint
mittels findmnt überprüft.

## 3. Atomare Archivierung

Implementierung:
src/retro_rag/importer/staging.py

Die Archivfunktion verwendet:

- Temporäre Dateien im Zielverzeichnis
- fsync der geschriebenen Datei
- SHA-256-Integritätsprüfung
- Atomare Veröffentlichung durch os.link
- Keine Überschreibung vorhandener Archivdateien
- Erneute Integritätsprüfung bestehender Dateien
- Bereinigung temporärer Dateien bei regulären Fehlern

Die dazugehörigen Unit-Tests wurden bestanden.

Einschränkung:
Ein harter Prozessabbruch kann temporäre Dateien hinterlassen.
Dateisystem und PostgreSQL besitzen keine gemeinsame Transaktion.

## 4. Mountpoint-Sicherung

Neue Datei:
src/retro_rag/importer/archive_mount.py

Prüffunktion:
verify_archive_mount()

Geprüft werden:

- Freigegebener Archivpfad
- Existierender Mountpoint /data
- Erwartete Geräte-UUID
- Tatsächliches Blockgerät
- Zugehörigkeit zum erwarteten Dateisystem
- Vorhandenes Archivverzeichnis

Ergebnis auf Poseidon:
PASS: Richtige Archiv-HDD erkannt

Die CLI bindet diese Prüfung bei --apply ein.
Ein abweichender Archivpfad wird abgewiesen.

Negativtest:

--apply --archive-root /tmp/retro-rag-falscher-pfad

Ergebnis:
Exit-Code 2
Fehlermeldung:
--apply erfordert --archive-root /data/retro-rag/v2/originals

Einschränkung:
Direkte Aufrufe von stage_file() umgehen die CLI-Pfadprüfung.
Ein negativer Test mit tatsächlich fehlendem Mountpoint
wurde noch nicht durchgeführt.

## 5. Archiv-/Datenbank-Audit

Neue Datei:
scripts/audit_original_archive.py

Das Skript vergleicht die in PostgreSQL registrierten
Archiv-URIs und SHA-256-Werte mit den Archivdateien.

Geprüft werden:

- Fehlende Dateien
- Hash-Abweichungen
- Dateien ohne Dokumentversionsreferenz
- Temporäre Archivdateien
- Unerwartete Archiv-URIs und Symlinks

Das Audit arbeitet rein lesend.
Es löscht oder verändert keine Dateien.

Erfolgreicher Test gegen retro_rag_v2_test:

Registrierte Archivdateien: 0
Verwaiste Dateien: 0
Integritätsprobleme: 0
PASS: Archiv und Datenbank konsistent

Dieser Test bestätigt nur den leeren Ausgangszustand.
Eine tatsächliche Recovery-Situation wurde noch nicht geprüft.

## 6. Echter WebDAV-Download

Bestehende Nextcloud-Instanz auf Poseidon.
Keine zusätzliche Nextcloud-Instanz erforderlich.

WebDAV-Discovery:
3 PDF-Dateien erkannt.

- cubx-103.pdf, File-ID 172, 4914302 Bytes
- cusl2c-104.pdf, File-ID 173, 5164564 Bytes
- p5ab-107.pdf, File-ID 175, 1093414 Bytes

Echter Download von p5ab-107.pdf erfolgreich.

Empfangene Bytes: 1093414
Erwartete Bytes: 1093414
PDF-Signatur: gültig

SHA-256:
cd0a615819b7f8e0e085f5aec77529537cb9c7fde61f8a889e5402618cb5cff4

Der Download wurde nicht als --apply ausgeführt.

## 7. Downloadfehler

Geänderte Datei:
src/retro_rag/importer/webdav.py

Die Downloadfunktion vergleicht nun die empfangene
Bytezahl mit der zuvor durch WebDAV gemeldeten Größe.

Bei Abweichung wird ein IOError ausgelöst.

Neuer Regressionstest:
test_download_rejects_incomplete_transfer

Testfall:
100 Bytes angekündigt, 50 Bytes empfangen.

Ergebnis:
PASS: Unvollständiger oder inkonsistenter Download erkannt.

Der Test wurde anschließend in die bestehende
WebDAV-Testsuite aufgenommen.

Einschränkungen:
- HTTP-Fehler und Verbindungsabbruch nicht separat injiziert.
- Gleich große Inhaltsänderungen werden nicht erkannt.
- ETag-Konsistenz vor/nach Download noch nicht geprüft.
- Das Größenlimit wird weiterhin erst nach dem Lesen
  zusätzlich anhand der tatsächlich empfangenen Bytes geprüft.

## 8. PostgreSQL und Berechtigungen

Testdatenbank: retro_rag_v2_test
Importer-Rolle: rag_v2_importer_login

Der direkte Hostzugriff auf PostgreSQL über
127.0.0.1:5432 wurde durch pg_hba.conf abgewiesen,
weil der Container die Quelladresse 172.19.0.1 sah.

Die Verbindung wurde anschließend erfolgreich aus dem
PostgreSQL-Netzwerk-Namespace mit eingeschränkter
Benutzeridentität hergestellt.

Bestätigte Ausgabe:

Verbindung:
('rag_v2_importer_login', 'retro_rag_v2_test')

Write-Gate:
False

Es wurden hierbei keine Daten importiert.

Die reguläre Netzwerkverbindung für einen späteren
Importer-Worker ist noch gesondert festzulegen.

## 9. Testergebnisse

Archiv- und WebDAV-Staging-Tests nach Einführung
der atomaren Archivierung:

11 passed in 0.09s

WebDAV-Staging-Tests nach Ergänzung des
Download-Regressionstests:

9 passed in 0.09s

Vollständige Python-Testsuite:

28 passed, 11 skipped in 0.18s

Python-Syntaxprüfung:
erfolgreich

Git-Diff-Whitespaceprüfung:
ohne Befund

Die elf übersprungenen Tests gelten nicht als bestanden.
Ihre Ausführung benötigt teilweise gesonderte
Datenbank-/Isolationseinstellungen.

## 10. Noch offene Abnahmepunkte

1. Abgebrochenen Download beziehungsweise HTTP-Fehler
   kontrolliert simulieren.
2. PostgreSQL-Rollback nach Archivveröffentlichung testen.
3. Verwaiste Archivdatei erkennen und sicher wiederverwenden.
4. Wiederholung eines unterbrochenen Imports prüfen.
5. Echten WebDAV-Apply mit genau einer ausgewählten Datei
   und dem eingeschränkten Importer durchführen.
6. Danach DB-Datensätze, Hash und Archivdatei vergleichen.
7. Write-Gate nach dem kontrollierten Test wieder schließen.

## 11. Sicherheitsstatus

Kein vollständiger WebDAV-Apply durchgeführt.
Keine produktive Importfreigabe.
Keine automatische Dokumentlöschung.
Keine Änderung an den Nextcloud-Originaldateien.

Letzter bestätigter Write-Gate-Zustand:
writes_enabled = false


## 12. Nachtrag: Recovery- und Rollback-Nachweise (09.11.2026)

Die Aussagen in Abschnitt 10 sind der damalige Zwischenstand. Für die hier dokumentierten
Teilaspekte liegen inzwischen folgende **tatsächlich auf Poseidon ausgeführte** Nachweise vor.

### A. Archivdatei nach simuliertem DB-Fehler wiederverwenden

- Testdaten: Markdown-Bytes mit Titel `Recovery-Test`.
- SHA-256: `7731afe825d20470f1f579031a732612f0611ffb837735fc84c078f7df2fc851`.
- `archive_original()` legte das Original auf `/data` an.
- Wiederholter Aufruf mit identischen Bytes verwendete dieselbe Archivdatei;
  keine zweite Kopie entstand.
- Die Datei wurde nach exakter Inhaltsprüfung entfernt.
- **Grenze:** Bei diesem Test wurde der DB-Fehler nur simuliert, nicht durch
  `stage_file()` ausgelöst.

### B. Echte Erkennung eines verwaisten Archivartefakts

- Separates `Audit-Orphan-Test`-Markdown wurde im Archiv angelegt.
- `scripts/audit_original_archive.py` gegen `retro_rag_v2_test` meldete:
  `Registrierte Archivdateien: 0`,
  `Verwaiste Dateien: 1`,
  `Integritätsprobleme: 0`.
- Gemeldeter Pfad:
  `/data/retro-rag/v2/originals/af/af9a165758ebcefd1b3d8532cb8b39934e1e6cb346d60aecd4481fcc2f652e20.md`.
- Exit-Code `1` war als erwartete Negativtest-Antwort korrekt.
- Die Datei wurde nur nach Prüfung auf Symlinkfreiheit und exakter Bytegleichheit
  manuell entfernt. Ein anschließendes Audit meldete
  `0` registrierte Dateien, `0` verwaiste Dateien, `0` Integritätsprobleme
  und `PASS: Archiv und Datenbank konsistent`.

### C. PostgreSQL-Rollback bei bereits veröffentlichter Archivdatei

Ein realer PostgreSQL-Transaktionskontext wurde verwendet, aber **nicht**
`stage_file()`: `CREATE TEMP TABLE rollback_probe`, INSERT, Veröffentlichung
einer Markdown-Testdatei durch `archive_original()` innerhalb der Transaktion
und ein absichtlich ausgelöster `RuntimeError`, der den Rollback bewirkte.

Ausgaben:

```text
PASS: Archivdatei innerhalb der DB-Transaktion angelegt
PASS: PostgreSQL-Transaktion zurückgerollt
PASS: Archivdatei nach Rollback vorhanden
PASS: Archivdatei beim Wiederanlauf wiederverwendet
```

- SHA-256: `74b79e257092b31508c4e0eb8cac41c3312efef466410a3368c9c70c0a893445`.
- Die Datei blieb unter
  `/data/retro-rag/v2/originals/74/74b79e257092b31508c4e0eb8cac41c3312efef466410a3368c9c70c0a893445.md`
  nach Rollback bestehen; Wiederverwendung mit demselben Inhalt funktionierte.
- Anschließendes Audit:
  `Registrierte Archivdateien: 0`,
  `Verwaiste Dateien: 1`, `Integritätsprobleme: 0`;
  Exit-Code `1` (erwartet).
- Die Testdatei wurde nach Prüfung von Hash, Pfad, Inhalt und fehlender
  Symlink-Eigenschaft kontrolliert entfernt:
  `PASS: SQL-Rollback-Testdatei sicher entfernt`.
- **Grenze:** Diese Prüfung zeigt die Nicht-Atomarität von Dateisystem und
  PostgreSQL sowie die Wiedererkennung verwaister Dateien. Sie prüft weder
  persistente `rag_v2`-Tabellenänderungen noch einen vollständigen
  `stage_file()`-Rollback. Eine weitere Audit-Ausführung nach dieser letzten
  Löschung ist in den bereitgestellten Ergebnissen nicht enthalten.

### D. Unverändert offene Punkte

1. Vollständiger `stage_file()`-Integrationstest einschließlich eines
   erzwungenen SQL-Fehlers mit realem Importer, sicherer Gate-Steuerung,
   Persistenzprüfung und Wiederanlauf.
2. Kontrollierter WebDAV-`--apply` für **genau eine** Quell-Datei
   (`p5ab-107.pdf`, Nextcloud-fileid `175`) und anschließender
   Abgleich von Datenbankeintrag und Archiv-Hash.
3. Begrenzung des CLI-Imports auf exakt eine gewählte Quell-ID, bevor
   `--apply` aktiviert wird; die aktuelle CLI verarbeitet sonst alle
   gefundenen Dateien unter ihrer konfigurierten Wurzel.
4. Separate Fehler-Injektion für HTTP-Fehler und abgebrochenen Transfer;
   ETag-/Inhaltsrennen und Begrenzung des Downloads während des Lesens.
5. Negativtest bei fehlendem/falschem Mountpoint, Audit unter
   parallelem Import und sichere Behandlung temporärer Dateien nach hartem
   Prozessabbruch.
6. Nach dem späteren Apply: unabhängiger DB-/Archiv-Nachcheck und
   dokumentierte erneute Schließung des Write-Gates.

**Keine neue Produktivfreigabe.** Der zuletzt direkt gemeldete Write-Gate-Wert
war `false`; in diesen Recovery-Tests wurde das Gate nicht geöffnet.
Die früheren `28 passed, 11 skipped` betreffen den zuletzt gemeldeten
pytest-Lauf. Die obigen Recovery-Nachweise sind separate manuelle Testläufe,
keine zusätzlichen pytest-Fälle.

## 13. Abnahme: isolierter echter `stage_file()`-Rollback und Wiederanlauf (09.11.2026)

**Status: erfolgreich auf Poseidon ausgeführter manueller Integrationstest.**
Dieser Nachtrag ersetzt den entsprechenden offenen Zwischenstand in Abschnitt 12.D.1,
nicht aber die noch offenen WebDAV-/Netzwerk- und Produktivabnahmen.

### Isolierte Testumgebung

- Container `retro-rag-v2-staging-isolated`, Image `pgvector/pgvector:pg16`,
  `--network none`, PostgreSQL-Daten auf `tmpfs`, `--rm`.
- Datenbank `retro_rag_v2_test`; verpflichtende Identitätsprüfung auf
  `current_setting('cluster_name') = 'retro-rag-v2-staging-isolated'`
  und `session_user = 'postgres'`.
- Schema aus dem vorhandenen V2-Testcluster **nur als DDL** übernommen; im
  isolierten Cluster wurden Migrationsmarker 1–5 und ein zunächst geschlossenes
  `write_gate` angelegt.
- Python-venv auf Poseidon per `nsenter` in den Netzwerk-Namespace **des
  isolierten Containers** eingebunden; die bestehenden Container-Daten
  blieben getrennt.
- Temporäres Dateisystem-Archiv per `tempfile.TemporaryDirectory` unter
  `/data/retro-rag/v2/staging`, **nicht** im dauerhaften Originalarchiv.
  Synthetische Markdown-Quelldatei; kein WebDAV-Download.
- Nur im isolierten Cluster wurde das Gate für den Test temporär geöffnet
  und danach im `finally`-Block wieder geschlossen.

### Fehler-Injektion und geprüfter Ablauf

Ein ausschließlich im isolierten Cluster installierter PostgreSQL-Trigger
auf `rag_v2.processing_job` löste beim echten `stage_file()`-Aufruf
absichtlich die Exception
`Simulierter SQL-Fehler im Staging` aus. Dies geschieht **nach**
Erstellung der Archivdatei und nach vorangehenden SQL-Änderungen.

Der erste Versuch erreichte diesen Trigger, brach jedoch im
**Testskript** bei der Exception-Behandlung ab:
`AttributeError: module 'psycopg' has no attribute 'RaiseException'`.
Korrektur im Testaufruf:
`psycopg.errors.RaiseException`. Das Gate wurde bereits beim
fehlerhaften ersten Testlauf durch `finally` geschlossen.
Anschließende Kontrolle: Gate `false`, Dokumente/Versionen/Jobs `0`;
keine verbliebenen Test-Trigger bzw. Test-Funktionen.

Der korrigierte Wiederholungslauf wurde vollständig erfolgreich ausgeführt:

```text
PASS: SQL-Fehler ausgelöst
PASS: DB-Transaktion vollständig zurückgerollt
PASS: Archivdatei trotz Rollback vorhanden
PASS: Wiederanlauf erfolgreich
PASS: DB-Datensätze konsistent
PASS: Wiederholter Import idempotent
PASS: Isoliertes Write-Gate geschlossen
PASS: Integrationstest vollständig abgeschlossen
```

Nach erzwungenem Fehler ergab die Zählung der Tabellen
`document`, `document_source`, `document_version`,
`processing_job` und `processing_artifact` jeweils **0**.
Die Archivdatei bestand unverändert weiter und entsprach den
synthetischen Quelldaten. Nach Entfernen des Fehler-Triggers
lieferte `stage_file()` `action = 'new'` und alle fünf
Tabellen enthielten jeweils **1** Eintrag. Ein erneuter
`stage_file()`-Aufruf lieferte `action = 'unchanged'`;
die Tabellenzähler blieben unverändert bei jeweils **1**.

### Unabhängige Nachkontrolle und Bereinigung

Unabhängig über `docker exec codeanalyse-postgres` geprüft:

```text
writes_enabled = f
reason = Parallelitätstest erfolgreich; Freigabe ausstehend
dokumente = 0
quellen = 0
versionen = 0
jobs = 0
reviews = 0
```

Unabhängig im isolierten Container geprüft:

```text
writes_enabled = f
reason = Isolierter Staging-Test beendet
dokumente = 1
versionen = 1
jobs = 1
```

Anschließend:

```text
docker stop retro-rag-v2-staging-isolated
retro-rag-v2-staging-isolated

docker ps -a --filter 'name=^/retro-rag-v2-staging-isolated$'
CONTAINER ID   IMAGE   COMMAND   CREATED   STATUS   PORTS   NAMES
```

Damit sind das geschlossene persistente Gate und die unveränderten
Tabellenzähler des bestehenden V2-Testclusters sowie das Ende
des temporären Containers bestätigt.

### Geltungsbereich / weiterhin offen

- Bestanden: tatsächlicher `stage_file()`-Pfad mit absichtlich
  ausgelöstem SQL-Fehler, DB-Rollback, unveränderter Archivkopie,
  Wiederanlauf, Idempotenz und separater Nachkontrolle.
- Der Test benutzte den Datenbank-Superuser **nur im isolierten Container**;
  die vollständige identische Ausführung mit dem eingeschränkten
  `rag_v2_importer_login` wurde hier nicht erneut nachgewiesen.
- Es handelt sich um einen manuell ausgeführten Integrationstest,
  **nicht** um einen neuen eingecheckten pytest-Test; der letzte
  bestätigte Suite-Lauf bleibt `28 passed, 11 skipped`.
- Noch offen: kontrollierter **Einzeldatei**-WebDAV-`--apply`, Abgleich
  von realem PDF-Hash/DB-Referenz/Originalarchiv, HTTP-Fehler und
  Verbindungsabbruch, ETag-Rennen und gegebenenfalls weitere
  Crash-/Mountpoint-Fehlerfälle.
- **Keine produktive Importfreigabe, kein Merge nach `main`.**
