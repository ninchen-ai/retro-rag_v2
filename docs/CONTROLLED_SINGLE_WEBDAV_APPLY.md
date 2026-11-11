# Kontrollierter Einzeldatei-WebDAV-Apply und Fehlerfälle

Stand: 11.11.2026. Entwicklungsbranch: `feat/controlled-single-webdav-apply` (Basis: `integration/import-pipeline-2026-11-09`).

## Umfang und Sicherheitsgrenzen

- `--apply` ist nur mit **genau einer** `--source-key` (Nextcloud-`oc:fileid`) und einem zuvor verifizierten `--expected-sha256` möglich.
- Eine Datei-ID wird gegen die aktuelle WebDAV-Liste aufgelöst. Ein fehlender oder nicht eindeutiger Treffer ist ein harter Fehler.
- Der SHA-256 wird nach vollständigem Download, aber **vor** Archivierung und Datenbank-Staging geprüft.
- WebDAV-GET wird mit `If-Match` für einen vorhandenen ETag ausgeführt; HTTP 412, ETag-Wechsel, abgebrochene Verbindung, gekürzter oder zu großer Download schlagen fehl. Es gibt keinen automatischen Retry eines schreibenden Vorgangs.
- Der Download erfolgt in begrenzten Blöcken; die Gesamtdaten werden erst nach vollständigem Lesen zurückgegeben. Keine SQL-/Archivschreiboperation bei Downloadfehler.
- Originalarchiv: inhaltsadressierte temp-Datei, `fsync`, atomare Veröffentlichung über `os.link` (gleicher Dateisystempfad) und Verzeichnis-`fsync`. Bestehende Archivobjekte werden auf SHA-256 geprüft und nie überschrieben. Nach einem Prozessabsturz vor `os.link` kann eine `.pending-*`-Datei zurückbleiben, aber **kein teilweises endgültiges Archivobjekt**.
- Staging nutzt weiterhin `rag_v2.assert_import_write_gate()`, advisory locks und eine PostgreSQL-Transaktion. Ein SQL-Fehler rollt die DB-Änderungen zurück; eine bereits vollständig geschriebene Archivdatei kann als verwaistes, unveränderliches Artefakt verbleiben. Das ist kein verteilter DB/Dateisystem-Commit.
- Es gibt **keine** Versionenaktivierung, keinen Workerstart, keine Inventaränderung, kein Schreiben nach Nextcloud und keine V1-Schreiboperation.

## Testabnahme auf Poseidon (zunächst ohne Apply)

```bash
cd ~/projects/retro-rag_v2
git fetch origin
git switch --track origin/feat/controlled-single-webdav-apply
source .venv/bin/activate
python -m pip install -e '.[dev]'

python -m pytest -q tests/test_webdav_staging.py \
  tests/test_single_webdav_apply_failures.py \
  tests/test_single_apply_cli.py -rs
python -m ruff check src/retro_rag/importer/{webdav,staging,sync_cli}.py \
  tests/test_single_webdav_apply_failures.py tests/test_single_apply_cli.py
python -m pytest -q -rs
git diff --check
```

**Erfolg ist erst nach realer Testausgabe bestätigt.** Der bloße Commit der Tests zählt nicht als bestandener Test.

## Kontrollierter Ablauf mit genau einer Datei

1. PostgreSQL-Backup/Restore-Pfad prüfen; `retro_rag_v2_test` und Rolle `rag_v2_importer_login` verifizieren. Der aktuell dokumentierte Anfangszustand hat `writes_enabled=false` und leere Importtabellen. Der Istzustand ist unmittelbar vor dem Test erneut abzufragen.
2. WebDAV-Zugangsdaten ausschließlich über Umgebungsvariablen bzw. geschützte Sitzung setzen: `RETRO_V2_WEBDAV_URL`, `RETRO_V2_WEBDAV_USER`, `RETRO_V2_WEBDAV_APP_PASSWORD`, `RETRO_V2_NEXTCLOUD_INSTANCE_ID` und `RETRO_V2_DATABASE_DSN`. Nur das Test-DB-Importer-Login verwenden; keine Passwörter protokollieren.
3. **Gate geschlossen lassen**, zunächst lesend die Datei-ID ermitteln und anschließend nur diese Datei planen:

```bash
python -m retro_rag.importer.sync_cli --source-key '<NEXTCLOUD_FILEID>'
```

   Die Ausgabe enthält `sha256=<64 Hex-Zeichen>`. Datei, Hash und geplante Aktion dokumentieren.
4. Erst nach expliziter Betreiberfreigabe in einer separaten Migrator-Sitzung das **Test-Gate** zeitlich begrenzt öffnen. Niemals dem Importer Rechte zur Gate-Änderung geben. Während des offenen Gates keine anderen Importer-Prozesse starten.
5. Eine einzige Datei stagen (keine weiteren Importdateien):

```bash
python -m retro_rag.importer.sync_cli \
  --apply --source-key '<NEXTCLOUD_FILEID>' \
  --expected-sha256 '<64-STELLIGER-SHA256-AUS-PLANUNG>' \
  --archive-root '/ABSOLUTER/GEPRUEFTER/ARCHIVPFAD'
```

6. **Unmittelbar** mit dem Migrator das Gate wieder schließen, auch bei Fehlern. Abschlusskontrolle als separater lesender DB-Zugang: `SELECT writes_enabled, reason FROM rag_v2.write_gate;` sowie Zählung der fünf Tabellen `document`, `document_source`, `document_version`, `processing_job`, `review_item`. Archivhash prüfen. Ein zweiter identischer Apply soll `unchanged` zurückliefern und keine neue Version erzeugen. Bei Fehler niemals blind erneut freigeben: erst Datenbank und Archivzustand prüfen.

## Weitere Fehlerfälle und Grenzen

| Fall | Erwartung |
| --- | --- |
| Timeout/Verbindungsabbruch vor vollständigem GET | Keine Archiv-/DB-Schreiboperation |
| HTTP 412 oder geänderter ETag | Abbruch vor Staging |
| Datei zwischen Vorschau und Apply geändert | SHA-256-Abweichung; kein Staging |
| Zu großer/verkürzter Download | Abbruch; kein Staging |
| Prozessabsturz beim Archivschreiben | Kein teilweise veröffentlichtes Zielobjekt; möglicherweise `.pending-*` |
| Prozessabsturz nach Archivierung, vor DB-Commit | DB-Rollback; eventuell verwaiste vollständige Archivdatei |
| Prozessabsturz nach DB-Commit, vor CLI-Ausgabe | Commitstatus zunächst ungewiss; read-only DB-Abgleich und danach idempotenter Re-Apply |
| Gate geschlossen | `assert_import_write_gate()` lehnt Staging ab; kein Archivschreiben |
| Wiederholung gleicher Datei/gleicher Hash | `unchanged`, keine neue Version |
| Parallele Writer für gleiche Quelle | Bestehende advisory locks/DB-Sperren; tatsächliche DB-Parallelität separat prüfen |

**Abnahmestatus (11.11.2026):** Auf Poseidon wurden zweimal die 27 gezielt ausgewählten Unit-Tests erfolgreich ausgeführt (`27 passed in 0.13s` bzw. `27 passed in 0.12s`). Der erste Ruff-Lauf meldete acht Beanstandungen (Importreihenfolge, ungenutzter Import, SIM117); nach Korrektur meldete der zweite Ruff-Lauf ausschließlich `I001` wegen einer überzähligen Leerzeile nach den Imports in `webdav.py`. Diese letzte Stelle wurde mit Commit `69400e1` korrigiert, **aber noch nicht erneut auf Poseidon geprüft**. `git diff --check` lieferte beim zweiten Testlauf keine Ausgabe. Ein vollständiger Suite-Lauf, realer Nextcloud-/PostgreSQL-End-to-End-Apply, kontrollierte Gate-Freigabe, realer Crash-/Netzwerktest und unabhängige DB-Nachkontrolle sind weiterhin offen. Keine Produktionsfreigabe.

**Hinweis:** Ein hartes Ausschalten der gesamten Maschine kann selbst nach `fsync` je nach Storage-/Controller-Cache zusätzliche Risiken haben. Das hier beschriebene Verfahren behandelt Anwendungskonflikte und Prozessabbrüche; ein Restore-Test bleibt notwendig.
