# Import-Pipeline, Stufe 1: WebDAV und Staging

Stand: 08.11.2026. Entwicklungsbranch `feat/import-webdav-staging`.

## Umfang

- Verbindliche Datenbankstruktur: `feature/phase0-database` (Migrationen 0001–0004).
- Vorhandene Markdown-Vorstufe aus `feat/import-pipeline-foundation` integriert.
- WebDAV-Discovery per Depth-1-PROPFIND mit explizit angeforderter Nextcloud-`oc:fileid` als Quellkennung.
- Die Verzeichnisse `Import`, `retro-rag-hardware-vorlagen-v1` und `Sofortupload` werden unabhängig von Groß-/Kleinschreibung auf jeder Ebene vor der rekursiven Traversierung ausgeschlossen.
- SHA-256 anhand heruntergeladener Originalbytes.
- Dry-Run zeigt neue, geänderte und bereits vorhandene Inhalte.
- `--apply` erstellt ausschließlich Dokument, Quelle, Version, Job, abgeschlossenen Archivschritt und Archivartefakt in `retro_rag_v2_test`.
- Keine Indexierung, keine automatische Quellenfreigabe, keine Bestandsänderung, keine Deaktivierung oder Löschung.

## Konfiguration (nur Umgebungsvariablen)

```bash
export RETRO_V2_WEBDAV_URL='https://nextcloud.example/remote.php/dav/files/USER/Retro-Computing/'
export RETRO_V2_WEBDAV_USER='USER'
# Passwort sicher per nicht-committeter lokaler Umgebung bereitstellen
export RETRO_V2_WEBDAV_APP_PASSWORD='...'
export RETRO_V2_DATABASE_DSN='postgresql://rag_v2_importer_login@127.0.0.1:5432/retro_rag_v2_test'
```

`RETRO_V2_WEBDAV_URL` muss den einzulesenden Root-Ordner bezeichnen. HTTP ist nur für Loopback erlaubt. Netz-Redirects werden nicht unterstützt. Zugangsdaten nie in Git einchecken.

```bash
pip install -e '.[dev]'
python -m retro_rag.importer.sync_cli
# Erst nach Test, aktiver Importer-Loginrolle und bewusster Freigabe von rag_v2.write_gate:
python -m retro_rag.importer.sync_cli --apply --archive-root /srv/retro-rag-v2/originals
```

**Stand 08.11.2026:** `rag_v2_importer_login` wurde mit eigenem Passwort aktiviert; HBA-Positiv- und Ablehnungstests über IPv4 wurden bestanden. Migration `0004_import_write_gate.sql` wurde ausgeführt und überprüft. `stage_file()` prüft die geschlossene Schreibsperre über `rag_v2.assert_import_write_gate()` (SECURITY DEFINER mit zeilenweiser Transaktionssperre). Der Importer hat nur EXECUTE auf die Funktion, kein UPDATE auf `write_gate`. **Kein `--apply`-Integrationstest durchgeführt, Gate weiterhin geschlossen.** Siehe [`IMPORTER_WRITE_GATE.md`](IMPORTER_WRITE_GATE.md).

## Noch offen

- Sichere Erkennung mehrdeutiger Dokumentidentität bei mehreren Quellen.
- Die `document_source`-Identität wird aus der Nextcloud-fileid gebildet; ein Wechsel der Nextcloud-Instanz benötigt ein späteres Namespace-Konzept.
- Vor jedem Apply sollte die vollständige Datei- und Änderungsmenge geprüft werden.
- Rekursionsgrenze für Verzeichnisse, Größenlimit und Netztimeout sind vorläufig.
- Job-Worker, OCR/PDF, Extraktion, Chunks, Embeddings und Reviews folgen später.
- Atomare Übernahme neuer Versionen erfolgt erst nach vollständiger technischer Indexierung.
- Unterbrochene Transfers, ETag-/Hash-Rennen und Validierung des Archiv-Dateityps sind zu härten.
