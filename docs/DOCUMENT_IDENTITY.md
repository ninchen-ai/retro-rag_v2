# Dokumentidentität und Dublettenprüfung (Punkt B)

Stand: 09.11.2026. Implementiert im Branch `feat/document-identity-review`, aufbauend auf `fix/importer-write-gate`. **Migration 0005 auf Poseidon angewendet und lesend geprüft am 09.11.2026; Integrationstests noch offen.**

## Identitäten

- `document.id`: stabile UUID des logischen Dokuments; niemals aus Inhaltshash ableiten.
- `document_source.source_system`: Provider, aktuell `nextcloud`.
- `document_source.source_instance`: stabile, vom Betreiber vergebene Kennung der *Installation*. Kein Hostname, Benutzer, Ordner oder zufällig pro Start generierter Wert. Bei Änderung der URL derselben Installation unverändert lassen. Bei Restore/Klon und unabhängig betriebenen Instanzen unterschiedliche Kennungen zuweisen. Vorherige Quellenidentitäten nicht wiederverwenden.
- `document_source.source_key`: Nextcloud-`oc:fileid` **innerhalb dieser Instanz**.
- `document_version.content_hash`: SHA-256 der unveränderten Originalbytes; ausschließlich Inhaltsidentität.

Bei Rename/Move innerhalb derselben Installation bleibt die Quellidentität erhalten. Gleiche Datei-IDs auf getrennten Installationen sind unterschiedliche Quellen. Identischer Hash über getrennte Quellen ist *kein* Nachweis derselben logischen Dokumentidentität.

## Entscheidungslogik (fail closed)

1. Quelle mit genau (`source_system`, `source_instance`, `source_key`) vorhanden, Hash bereits als Version desselben Dokuments bekannt: `unchanged`.
2. Gleiche Quelle mit neuem Hash: `changed`; neue Version derselben logischen UUID.
3. Unbekannte Quellidentität, bisher unbekannter Hash: `new`; eigene Dokument-UUID und Staging-Job.
4. Unbekannte Quellidentität, bereits vorhandener Hash: `review`; **eigene** vorläufige Dokument-UUID, Quellenzeile, Version und `review_item(item_kind='document_identity')` mit Kandidaten-UUIDs. **Kein Verarbeitungsjob/keine Indexierung/keine automatische Zusammenführung.**
5. Dry-Run erkennt `review` ohne DB-Änderung. Apply benötigt die transaktionale Write-Gate-Prüfung.
6. Auch bei parallelen Erstimporten gleicher Bytes wird die Hash-Entscheidung über ein transaktionales Advisory Lock serialisiert.

Der Review-Eintrag ist ein *Vorschlag*, keine Entscheidung. Eine spätere separate Reviewer-Funktion muss geprüfte Verknüpfung, getrennte Identitäten oder korrigierte Zuordnung sowie Nachweis und Folgejob transaktional behandeln. **Diese Funktion ist noch nicht implementiert**; Review-Fälle bleiben bis dahin absichtlich unverarbeitet. `accepted` an einem Review-Item allein löst hier keine automatische Datenmutation aus.

Rohdatenarchivierung kann bei identischen Bytes denselben inhaltsadressierten Originalblob wiederverwenden. Das bedeutet **keine** Zusammenführung von `document`, `document_source` oder Dokumentversionen.

## Konfiguration

```bash
export RETRO_V2_NEXTCLOUD_INSTANCE_ID='home-nextcloud-primary'
python -m retro_rag.importer.sync_cli
```

Die Instanz-ID wird nicht aus der WebDAV-URL abgeleitet und muss dauerhaft stabil konfiguriert werden. Sie muss nicht geheim sein.

## Migration/Abnahme auf Poseidon

1. `git fetch origin && git switch feat/document-identity-review` (vorher lokale Änderungen prüfen).
2. Verifizieren, dass `rag_v2.document_source` **keine Nextcloud-Zeilen** enthält. Wenn doch: nicht automatisch migrieren; erst tatsächliche Instanzzuordnung klären.
3. Den bestehenden DB-Backup-/Restore-Prozess prüfen. Gate geschlossen lassen.
4. Als `rag_v2_migrator_login` mit `SET ROLE rag_v2_migrator` die Datei `db/migrations/0005_document_identity.sql` ausschließlich in `retro_rag_v2_test` ausführen, wie bei Migration 0004.
5. `db/checks/verify_0005.sql` ausführen; `python -m pytest -q` ausführen.
6. Dry-Run gegen Nextcloud prüfen; insbesondere identische Bytes mit zwei verschiedenen `oc:fileid` und zwei verschiedenen Instanzen simulieren.
7. **Kein automatisches Öffnen des Write-Gates**, keine Änderung der V1-Datenbanken und keine automatische `--apply`-Ausführung.

## Grenzen

Der Test-DB-Status wurde anhand der vom Betreiber am 09.11.2026 übermittelten Terminalausgaben überprüft (kein direkter Datenbankzugriff über den GitHub-Connector). Ein End-to-End-DB-Test und die spätere manuelle Review-Auflösung bleiben offen. Vor Apply muss auch die vom Importer zurückgelieferte vollständige Dateimenge geprüft werden.

## Betriebsnachweis auf Poseidon – 09.11.2026

**Vorab:** `python -m pytest -q` meldete `17 passed in 0.18s`, `git diff --check` blieb ohne Ausgabe. Kontrollabfrage vor Migration 0005: Versionen 1–4 vorhanden, keine `document_source`-Zeilen, `document=0`, `document_version=0`, `review_item=0`; Write-Gate gesperrt.

**Sicherung:** `pg_dump -U codeanalyse -d retro_rag_v2_test -Fc` in `/home/nina/backups/retro-rag-v2/pre_migration_0005.dump`, 123 KB, `-rw-------`. Inhaltsverzeichnis mit `pg_restore --list` erfolgreich gelesen. Der Dump ist **nicht** im Git-Repository; ein erfolgreicher Restore ist damit noch nicht nachgewiesen.

**Schemaänderung:** Nach `docker cp` über `rag_v2_migrator_login` angemeldet, `SET ROLE rag_v2_migrator`, `\\i /tmp/0005_document_identity.sql`. Bestätigte Ausgabe: `BEGIN`, `DO`, `pg_advisory_xact_lock`, drei `ALTER TABLE`, `CREATE INDEX`, `INSERT 0 1`, `COMMIT`. Anschließend `db/checks/verify_0005.sql`: `NOTICE: 0005: Instanzkennung, Identitätsindex, Berechtigungen geprüft` und `DO`. Temporäre SQL-Datei entfernt.

**Nachkontrolle:** `document_source` enthält 10 Spalten. Neue Spalte `source_instance` hat Datentyp `text` und `is_nullable=YES`; für Nextcloud-Quellen gilt die Nichtleer-Pflicht durch `document_source_instance_valid` (durch `verify_0005.sql` geprüft). Drei Indizes: `document_source_pkey`, `document_source_document_idx`, `document_source_identity_idx`; letzterer ist `UNIQUE` auf `(source_system, COALESCE(source_instance, ''::text), source_key)`. Versionsmarker 5 vorhanden. Write-Gate weiterhin `writes_enabled=f` mit Grund `Parallelitätstest erfolgreich; Freigabe ausstehend`.

### Abnahmegrenzen und Folgearbeiten

Schema-Migration und statische/unit-basierte Tests sind bestätigt. **Nicht bestätigt** sind der echte Mehrinstanz-Datensatztest, transaktionale Review-Erzeugung in PostgreSQL, gleichzeitiger Doppelimport, die vollständige WebDAV-`--apply`-Pipeline und die manuelle Review-Auflösung. Das Write-Gate bleibt zu. Der bisherige `db/schema/retro_rag_v2_test.sql`-Snapshot wurde **noch nicht** auf Poseidon nach Migration 0005 neu erzeugt; `scripts/export_schema_v2.sh` wurde im Repository auf erwarteten Migrationsstand 5 angehoben und muss auf Poseidon ausgeführt, geprüft und committed werden.

## Integrationstests (09.11.2026 vorbereitet)

Die vier ausführbaren PostgreSQL-Tests und ihre Sicherheitsbedingungen sind unter [DOCUMENT_IDENTITY_INTEGRATION_TESTS.md](DOCUMENT_IDENTITY_INTEGRATION_TESTS.md) dokumentiert. Die Tests sind **noch nicht ausgeführt**: erst die reale Poseidon-Ausgabe `4 passed` ohne `skipped` und die Nachkontrolle des Gate-Zustands erlauben eine Abnahme. Die Suite simuliert lediglich das Originalarchiv, nicht die SQL-Verarbeitung; sie nutzt den dedizierten Migrator-Login und committet keine Gate-Freigabe.

**Integrationstests am 09.11.2026:** Auf Poseidon wurden vier Datenbanktests über den Container-Netzwerk-Namespace mit `4 passed in 0.14s` bestanden (Instanzidentität, Hash-Review, Job-Sperre und Idempotenz). Die HBA-Regeln blieben unverändert. Der unabhängige Nachcheck des persistenten Write-Gates und der Tabellenzähler steht noch aus. Siehe [Integrationstest-Nachweis](DOCUMENT_IDENTITY_INTEGRATION_TESTS.md).

## Abschließende Abnahme von Punkt B – 09.11.2026

**Abnahme 09.11.2026:** Vier Integrationstests bestanden (`4 passed in 0.14s`). Anschließende unabhängige SQL-Kontrolle: `writes_enabled=f`, Grund `Parallelitätstest erfolgreich; Freigabe ausstehend`; `document=0`, `document_source=0`, `document_version=0`, `review_item=0`, `processing_job=0`. Damit sind Test-Rollback und unveränderter persistenter Gate-Zustand nachgewiesen. Kein echter WebDAV-`--apply`-Test und keine Review-Auflösung durchgeführt.

Die vorstehenden älteren Angaben zum noch ausstehenden Schema-Snapshot oder zur Testausführung sind durch den Git-Commit `04b9c98` (tatsächlicher DDL-Export) und diesen Abnahmenachtrag überholt. Die fachliche Abnahme bezieht sich auf Migration 0005, SQL-Staging und die vier reproduzierbaren Datenbanktests, nicht auf einen vollständigen WebDAV-Workflow.
