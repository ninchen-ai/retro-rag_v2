# Aktuelles Datenbankschema – Retro-RAG V2

**Stand:** 08.11.2026 · **Entwicklungszweig:** `feature/phase0-database`

## Autoritativer Stand

- PostgreSQL 16.15, pgvector 0.8.6, Schema `rag_v2`.
- Angelegte und auf Poseidon geprüfte Datenbank: `retro_rag_v2_test`.
- Angewendete Migrationen: `0001_init.sql`, `0002_roles.sql`, `0003_access.sql`, `0004_import_write_gate.sql` (Versionsmarker 4; erfolgreiche Ausführung und Check 08.11.2026).
- 37 Tabellen; Eigentümer des Schemas und der V2-Objekte: `rag_v2_migrator`.
- Sieben Berechtigungsgruppen; `rag_v2_reader_login`, `rag_v2_importer_login` und `rag_v2_migrator_login` aktiviert (vier weitere deaktiviert), mit getrennten Rollen und minimalen Rechten.
- `retro_rag_v2` (Produktion) wurde noch nicht eingerichtet.
- V1-Datenbanken `retro_rag` und `retro_rag_test` sind **nicht Teil dieses Schemas** und bleiben unangetastet.

Die **Migrationen** sind die versionierte Definition und Quelle der Änderungen:

1. `db/migrations/0001_init.sql` – Tabellen, Constraints, Indizes, Trigger, Funktionen.
2. `db/migrations/0002_roles.sql` – Berechtigungsgruppen und Grants.
3. `db/migrations/0003_access.sql` – vorbereitete Loginrollen und Eigentümertransfer.
4. `db/migrations/0004_import_write_gate.sql` – gesicherte Import-Gate-Funktion (SECURITY DEFINER, `FOR SHARE`) mit minimalem EXECUTE-Grant.

**Write-Gate-Abnahme (08.11.2026):** Versionsmarker 1–4 erneut lesend geprüft; `write_gate` zunächst `false` mit Initialisierungsgrund und `document`, `document_version`, `processing_job` jeweils 0 Zeilen. Im nachfolgenden Realtest wurde das Gate kontrolliert geöffnet, die Prüf-Funktion als echter Importer erfolgreich ausgeführt (`BEGIN` / `ROLLBACK`), anschließend das Gate wieder geschlossen (`writes_enabled=false`). Auch der erneute Ablehnungstest als Importer bei geschlossenem Gate war erfolgreich. Der Sperrgrund lautet seitdem `Importer-Test abgeschlossen; Freigabe ausstehend`. Ein zweiter lesender Zähl-/Migrationsstatus nach dem Test wurde noch nicht vorgelegt; ein End-to-End-Import fand nicht statt.

**Aktueller Gate-Endzustand (08.11.2026):** Nach einem Gate-UPDATE mit 3-Sekunden-Lock-Timeout wurde der Schalter erfolgreich geschlossen (`UPDATE 1`). Die lesende Kontrolle ergab `writes_enabled=false`, Grund `Parallelitätstest erfolgreich; Freigabe ausstehend`. Der Lock-Konflikt wurde beobachtet; die blockierende Session ist nicht durch zeitgleiche Terminal-2-Logs oder `pg_locks` nachgewiesen. Die zuletzt gemeldeten Zähler vor diesen rein gate-bezogenen Tests waren 0/0/0; kein End-to-End-Import wurde ausgeführt.

**Schema-Snapshot:** Die im Repository eingecheckte Datei `db/schema/retro_rag_v2_test.sql` stammt aus dem Stand vor Migration 0004 und muss nach einem neuen Export aktualisiert werden. Sie darf bis dahin nicht als vollständiger DDL-Snapshot des derzeit installierten Schemas ausgegeben werden.

Die **tatsächlich installierte Struktur** kann aus PostgreSQL in
`db/schema/retro_rag_v2_test.sql` exportiert werden. Weil GitHub nicht
direkt auf den lokalen PostgreSQL-Container von Poseidon zugreifen kann, muss
dieser Export **einmal auf Poseidon erzeugt und eingecheckt** werden. Vorher
liegt im Repository kein verifizierter Live-Snapshot; aus Migrationsdateien
abgeleitete SQL-Dateien werden nicht als Live-Dump ausgegeben.

## Tabellenübersicht (37)

| Bereich | Tabellen |
|---|---|
| Migration/Steuerung (2) | `schema_migration`, `write_gate` |
| Hardware und Bestand (10) | `component_type`, `article`, `article_revision`, `article_alias`, `unit`, `system`, `storage_location`, `installation`, `storage_assignment`, `unit_condition_history` |
| Dokumente und Suche (6) | `document`, `document_source`, `document_version`, `chunk`, `embedding_model`, `chunk_embedding` |
| Fakten und Kompatibilität (10) | `reference_entity`, `knowledge_subject`, `property`, `property_component_type`, `fact`, `evidence`, `fact_evidence`, `compatibility_rule`, `compatibility_rule_evidence`, `trusted_source` |
| Verarbeitung (3) | `processing_job`, `processing_step`, `processing_artifact` |
| Review (3) | `review_batch`, `review_item`, `review_decision` |
| Synchronisation, Fehler und Abfragen (3) | `sync_run`, `document_error`, `query_log` |

Diese Gruppierung ist eine Lesehilfe aus `0001_init.sql`; sie verändert keine Schemaobjekte.

## Installiertes Schema als SQL im Repository ablegen

Auf Poseidon im aktuellen Branch `fix/importer-write-gate`:

```bash
cd ~/projects/retro-rag_v2
git pull --ff-only
bash scripts/export_schema_v2.sh
git diff --no-index /dev/null db/schema/retro_rag_v2_test.sql | head -100
git add db/schema/retro_rag_v2_test.sql
git commit -m "docs(db): Snapshot des installierten V2-Testschemas"
git push
```

`git diff --no-index` gibt für Unterschiede Exit-Code 1 zurück;
das ist bei dieser Sichtprüfung normal.

Das Skript überprüft zuerst explizit die V2-Testdatenbank und den
Migrationsstand 4, erzeugt danach mit `pg_dump --schema-only
--schema=rag_v2 --no-owner --no-privileges` einen reinen DDL-Snapshot
und erwartet 37 Tabellen. Es greift nicht auf V1 zu.

**Grenzen des Exports:** Das SQL enthält keine Daten, Rollen, Passwörter,
`pg_hba.conf`, globalen Datenbankberechtigungen oder im Schema
`public` installierte pgvector-Extension. Das Snapshot-SQL ist ein
**Referenzartefakt**, keine Ersatz-Migration und kein vollständiges
Disaster-Recovery-Backup. Ein separater Datenbank-Dump und die Migrationen
bleiben für Wiederherstellung/Bootstrap erforderlich.

Nach jeder neuen Migration: Export erneut ausführen, Änderung prüfen und
Snapshot zusammen mit der Migrationsdatei committen. So wird Schema-Drift sichtbar.


## Vorgesehene Migration 0005 (09.11.2026; noch nicht auf Poseidon angewendet)

Der Branch `feat/document-identity-review` enthält `db/migrations/0005_document_identity.sql`. Die Migration ergänzt `document_source.source_instance`, erzwingt eine nichtleere Instanzkennung für Nextcloud und ersetzt die alte Eindeutigkeit `(source_system,source_key)` durch `(source_system,coalesce(source_instance,''),source_key)`. Bei vorhandenen Nextcloud-Zeilen bricht die Migration ohne manuelle Instanzzuordnung ab. Der hier dokumentierte aktuelle Datenbanksnapshot ist bis zur tatsächlichen Anwendung von 0005 **unverändert**; `db/schema/retro_rag_v2_test.sql` darf erst nach der Migration mit `scripts/export_schema_v2.sh` aktualisiert werden.
