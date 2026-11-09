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

**Stand 08.11.2026:** `rag_v2_importer_login` wurde mit eigenem Passwort aktiviert; HBA-Positiv- und Ablehnungstests über IPv4 wurden bestanden. Migration `0004_import_write_gate.sql` wurde ausgeführt und überprüft. `stage_file()` prüft die geschlossene Schreibsperre über `rag_v2.assert_import_write_gate()` (SECURITY DEFINER mit zeilenweiser Transaktionssperre). Der Importer hat nur EXECUTE auf die Funktion, kein UPDATE auf `write_gate`. **Realtest bei geöffnetem Gate als Importer erfolgreich (BEGIN, Funktionsaufruf, ROLLBACK), Gate anschließend per Migrator geschlossen und Schließung mit dem Importer bestätigt.** Kein `--apply`-Integrationstest durchgeführt. Bei einem konkurrierenden Gate-UPDATE trat ein 3-Sekunden-Lock-Timeout auf; die blockierende Importer-Session wurde nicht zweifelsfrei protokolliert. Ein vollständig korrelierter Parallelitätstest bleibt offen. Anschließend wurde das Gate wieder geschlossen (`writes_enabled=false`, Grund: `Parallelitätstest erfolgreich; Freigabe ausstehend`). Siehe [`IMPORTER_WRITE_GATE.md`](IMPORTER_WRITE_GATE.md).

## Noch offen

- Sichere Erkennung mehrdeutiger Dokumentidentität bei mehreren Quellen.
- Die `document_source`-Identität wird aus der Nextcloud-fileid gebildet; ein Wechsel der Nextcloud-Instanz benötigt ein späteres Namespace-Konzept.
- Vor jedem Apply sollte die vollständige Datei- und Änderungsmenge geprüft werden.
- Rekursionsgrenze für Verzeichnisse, Größenlimit und Netztimeout sind vorläufig.
- Job-Worker, OCR/PDF, Extraktion, Chunks, Embeddings und Reviews folgen später.
- Atomare Übernahme neuer Versionen erfolgt erst nach vollständiger technischer Indexierung.
- Unterbrochene Transfers, ETag-/Hash-Rennen und Validierung des Archiv-Dateityps sind zu härten.


## Nachtrag 09.11.2026: Punkt B im Entwicklungsbranch

Die oben als offen markierte Instanz- und Dublettenidentität ist in `feat/document-identity-review` als Migration 0005 plus Code und Unit-Tests vorbereitet. Die Umgebung benötigt zusätzlich `RETRO_V2_NEXTCLOUD_INSTANCE_ID`. Identische Hashes neuer, verschiedener Quellidentitäten werden in `review_item(document_identity)` ohne Processing-Job erfasst. Die Schema-Migration 0005 und ihre lesende Verifikation sind auf Poseidon nachgewiesen; der echte mehrquellige Import-/Review-Integrationstest und die Review-Auflösung stehen aus. Siehe [DOCUMENT_IDENTITY.md](DOCUMENT_IDENTITY.md). Das ist eine bestätigte **Schema-Abnahme**, aber noch keine End-to-End-Abnahme.

## Tatsächlicher Datenbankstand 09.11.2026

Die Testdatenbank `retro_rag_v2_test` erhielt Migration **0005** nach einer `pg_dump -Fc`-Sicherung (123 KB; `pg_restore --list` lesbar). `verify_0005.sql` wurde erfolgreich ausgeführt. Kontrolliert wurden die neue Spalte `source_instance text` (nullable, mit Nextcloud-spezifischer CHECK-Regel), der eindeutige Quellidentitätsindex `document_source_identity_idx`, Versionsmarker 5 und das weiterhin geschlossene Write-Gate (`writes_enabled=f`). Der Python-Testlauf vor dem Eingriff meldete **17 Tests bestanden**. `--apply` wurde dabei nicht ausgeführt. Siehe [Dokumentidentität](DOCUMENT_IDENTITY.md) und [Schema-Status](../db/SCHEMA_CURRENT.md).

## Regression/Integration – 09.11.2026

`tests/test_document_identity_integration.py` prüft den echten Staging-SQL-Pfad mit vier Rollback-Testfällen. Noch **nicht auf Poseidon ausgeführt**. Testanleitung und Ergebnismatrix: [DOCUMENT_IDENTITY_INTEGRATION_TESTS.md](DOCUMENT_IDENTITY_INTEGRATION_TESTS.md). Kein realer WebDAV-`--apply`-Test und keine freigegebene Review-Auflösung.

**Integrationstests am 09.11.2026:** Auf Poseidon wurden vier Datenbanktests über den Container-Netzwerk-Namespace mit `4 passed in 0.14s` bestanden (Instanzidentität, Hash-Review, Job-Sperre und Idempotenz). Die HBA-Regeln blieben unverändert. Der unabhängige Nachcheck des persistenten Write-Gates und der Tabellenzähler steht noch aus. Siehe [Integrationstest-Nachweis](DOCUMENT_IDENTITY_INTEGRATION_TESTS.md).

## Punkt B: abschließende Datenbankabnahme (09.11.2026)

**Abnahme 09.11.2026:** Vier Integrationstests bestanden (`4 passed in 0.14s`). Anschließende unabhängige SQL-Kontrolle: `writes_enabled=f`, Grund `Parallelitätstest erfolgreich; Freigabe ausstehend`; `document=0`, `document_source=0`, `document_version=0`, `review_item=0`, `processing_job=0`. Damit sind Test-Rollback und unveränderter persistenter Gate-Zustand nachgewiesen. Kein echter WebDAV-`--apply`-Test und keine Review-Auflösung durchgeführt.
