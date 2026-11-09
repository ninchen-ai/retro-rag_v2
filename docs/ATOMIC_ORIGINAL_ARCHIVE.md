# Retro-RAG V2 – Atomares Originalarchiv

Stand: 09.11.2026
Branch: fix/atomic-original-archive

## Architektur

Nextcloud bleibt die führende Dokumentquelle.

Originaldateien werden bei erstmaliger Übernahme und bei
inhaltlichen Änderungen dauerhaft im lokalen Archiv abgelegt.

PostgreSQL speichert Dokumentidentitäten, Versionen, Hashes,
Archiv-URIs und Verarbeitungszustände, nicht die binären
Originaldokumente.

## Speicherort

Server: Poseidon
Datenträger: Toshiba DT01ACA100, /dev/sda1
UUID: 0ad31014-cd69-4b01-b177-b30bfd832481
Dateisystem: ext4
Mountpoint: /data

Verzeichnisse:

- /data/retro-rag/v2/originals
- /data/retro-rag/v2/staging
- /data/retro-rag/v2/quarantine

Eigentümer: nina:nina
Berechtigungen: 0700

Die Verzeichnisse staging und quarantine sind vorbereitet.
Die aktuelle Archivfunktion nutzt temporäre Dateien direkt
innerhalb der jeweiligen Hash-Unterverzeichnisse von originals.

## Archivverfahren

Implementierung:
src/retro_rag/importer/staging.py

Funktion: archive_original()

1. SHA-256 der Originalbytes berechnen.
2. Dateiformat anhand der Erweiterung prüfen.
3. Hash-Unterverzeichnis bestimmen.
4. Vorhandene Archivdatei auf Integrität prüfen.
5. Neue Datei temporär im Zielverzeichnis schreiben.
6. Datei mittels fsync synchronisieren.
7. Temporäre Datei erneut auf SHA-256 prüfen.
8. Mit os.link ohne Überschreiben veröffentlichen.
9. Verzeichnis mittels fsync synchronisieren.
10. Temporäre Datei bei regulärem Abschluss bereinigen.

Identische Inhalte mit identischer Dateierweiterung
verwenden denselben Archivpfad.

## Bisherige Testergebnisse

09.11.2026:

- WebDAV-Discovery: 3 PDF-Dateien gefunden.
- Download p5ab-107.pdf erfolgreich.
- Nextcloud-fileid: 175.
- Dateigröße: 1.093.414 Bytes.
- SHA-256:
  cd0a615819b7f8e0e085f5aec77529537cb9c7fde61f8a889e5402618cb5cff4
- PostgreSQL-Verbindung als rag_v2_importer_login erfolgreich.
- Write-Gate weiterhin geschlossen.
- 11 Python-Tests bestanden (0,09 Sekunden).
- git diff --check ohne Befund.

Die 11 Tests betreffen die atomare Archivfunktion
und die bestehende WebDAV-Staging-Testsuite.

## Noch offene Prüfungen

- Kontrollierter echter WebDAV-Apply mit genau einer Datei.
- Fehlerfall: abgebrochener oder unvollständiger Download.
- Fehlerfall: PostgreSQL-Rollback nach Archivveröffentlichung.
- Erkennung und Behandlung verwaister Archivdateien.
- Wiederanlauf nach fehlgeschlagenem Import.
- Bereinigung temporärer Dateien nach hartem Prozessabbruch.
- Prüfung des erwarteten Datenträgers vor Archivschreibzugriffen.
- Wiederherstellbarkeit über Borg praktisch prüfen.

## Einschränkungen

Das Dateisystem und PostgreSQL bilden keine gemeinsame
Transaktion. Nach einem Datenbankfehler können verwaiste
Archivdateien zurückbleiben.

Ein hart beendeter Prozess kann temporäre Dateien hinterlassen.

Die bestehende Funktion enthält noch keine Prüfung
der erwarteten Mountpoint-UUID.

Eine vollständige Stromausfall- und Recovery-Abnahme
liegt noch nicht vor.

## Betriebsregel

Bis zur vollständigen Abnahme bleibt das V2-Write-Gate
geschlossen. Es erfolgt kein automatischer Produktivimport.
