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
