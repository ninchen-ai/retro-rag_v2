# Aktuelles Datenbankschema – Retro-RAG V2

**Stand:** 08.11.2026 · **Entwicklungszweig:** `feature/phase0-database`

## Autoritativer Stand

- PostgreSQL 16.15, pgvector 0.8.6, Schema `rag_v2`.
- Angelegte und auf Poseidon geprüfte Datenbank: `retro_rag_v2_test`.
- Angewendete Migrationen: `0001_init.sql`, `0002_roles.sql`, `0003_access.sql` (Versionsmarker 3).
- 37 Tabellen; Eigentümer des Schemas und der V2-Objekte: `rag_v2_migrator`.
- Sieben Berechtigungsgruppen; `rag_v2_reader_login` als einzige bislang aktivierte V2-Loginrolle, mit Reader-Rechten.
- `retro_rag_v2` (Produktion) wurde noch nicht eingerichtet.
- V1-Datenbanken `retro_rag` und `retro_rag_test` sind **nicht Teil dieses Schemas** und bleiben unangetastet.

Die **Migrationen** sind die versionierte Definition und Quelle der Änderungen:

1. `db/migrations/0001_init.sql` – Tabellen, Constraints, Indizes, Trigger, Funktionen.
2. `db/migrations/0002_roles.sql` – Berechtigungsgruppen und Grants.
3. `db/migrations/0003_access.sql` – vorbereitete Loginrollen und Eigentümertransfer.

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

Auf Poseidon im Branch `feature/phase0-database`:

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
Migrationsstand 3, erzeugt danach mit `pg_dump --schema-only
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
