# Dokumentidentität und Dublettenprüfung (Punkt B)

Stand: 09.11.2026. Implementiert im Branch `feat/document-identity-review`, aufbauend auf `fix/importer-write-gate`. **Nicht auf Poseidon ausgeführt.**

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

Der Test-DB-Status ist nur aus dokumentierten Terminalausgaben bekannt, nicht live aus Poseidon bestätigt. Ein End-to-End-DB-Test und die spätere manuelle Review-Auflösung bleiben offen. Vor Apply muss auch die vom Importer zurückgelieferte vollständige Dateimenge geprüft werden.
