# Phase 0 – PostgreSQL-Rollen (Migration 0002)

## Ausgangslage

PostgreSQL 16.15 läuft auf Poseidon im Container `codeanalyse-postgres`.
Die Datenbank `retro_rag_v2_test` und pgvector 0.8.6 sind eingerichtet.
`0001_init.sql` wurde ausgeführt: 37 Tabellen, `verify_0001.sql`
und `smoke_0001_test.sql` waren erfolgreich.

**V1 bleibt unangetastet:** Auf `retro_rag`, `retro_rag_test` und
`nextcloud` werden keine DDL-, ACL- oder Datenänderungen ausgeführt.

## Einschränkung: PostgreSQL-Rollen sind clusterweit

`0002_roles.sql` erzeugt ausschließlich neue, präfixierte
`rag_v2_*`-Berechtigungsgruppen mit `NOLOGIN`. Bestehende Benutzer und
Passwörter werden nicht verändert. PostgreSQL erlaubt über `PUBLIC`
häufig `CONNECT` auf andere Datenbanken. Deshalb garantieren Rollen
allein **noch keine harte V1-Verbindungsisolation**. Das muss später durch
gesonderte Login-Rollen, `pg_hba.conf`, Datenbank-ACLs nach expliziter
Freigabe oder eine separate PostgreSQL-Instanz gelöst werden.

Eine Änderung an den V1-Datenbank-ACLs ist **nicht Teil von Phase 0**.

## Berechtigungsgruppen

| Rolle | Rechte innerhalb von `rag_v2` |
|---|---|
| `rag_v2_reader` | SELECT, keine Änderungen |
| `rag_v2_query_logger` | nur INSERT in `query_log` |
| `rag_v2_importer` | Import-/Index-/Jobdaten und Review-Vorschläge |
| `rag_v2_reviewer` | Fakten, Belege, Freigaben, vertrauenswürdige Quellen |
| `rag_v2_inventory` | Hardwarestammdaten, Inventar, Zuordnungshistorie |
| `rag_v2_lifecycle` | Dokumentstatus, Entfernen von Chunks/Embeddings |
| `rag_v2_migrator` | Vorbereitete DML und CREATE im V2-Schema; Eigentümer- und DDL-Rechte noch offen |

Die neue Migration aktiviert **keine** Schreibprozesse. Der persistente
`write_gate` bleibt gesperrt. Diese Sperre ist noch keine RLS- oder
Trigger-basierte Datenbankbarriere für alle Schreibvorgänge; die spätere
Anwendung muss sie verbindlich erzwingen. Import-/Review-Rechte sind
Sicherheitsgrenzen, keine automatische Durchsetzung der fachlichen
Freigabeentscheidung.

## Vor Ausführung

Die Migration wurde noch **nicht** auf Poseidon getestet. Sie muss als
Tabelleneigentümer von `0001_init.sql` ausgeführt werden. Bitte die
SQL-Datei vor der Ausführung überprüfen.

```bash
cd ~/projects/retro-rag_v2
git pull --ff-only

# Vorprüfung: ausschließlich V2-Ziel
docker exec codeanalyse-postgres \
  psql -X -U codeanalyse -d retro_rag_v2_test -Atc \
  "SELECT current_database(), (SELECT max(version) FROM rag_v2.schema_migration);"

# Migration nur auf der V2-Testdatenbank
docker exec -i codeanalyse-postgres \
  psql -X -v ON_ERROR_STOP=1 -U codeanalyse -d retro_rag_v2_test \
  < db/migrations/0002_roles.sql

# Nur lesender Rechtecheck
docker exec -i codeanalyse-postgres \
  psql -X -v ON_ERROR_STOP=1 -U codeanalyse -d retro_rag_v2_test \
  < db/checks/verify_0002.sql
```

**Achtung:** Rollen werden im gesamten Cluster sichtbar; die durch
`0002` vergebenen Tabellenrechte beziehen sich ausschließlich auf
`rag_v2` in der V2-Testdatenbank. Die Migration verweigert vorhandene
gleichnamige Clusterrollen und ist nicht für wiederholte Ausführung gedacht.

## Noch offen vor Produktivbetrieb

1. Eigene LOGIN-Rollen mit sicheren Zugangsdaten und gezielten Gruppenzuweisungen.
2. Ein Schutz gegen die standardmäßige `PUBLIC CONNECT`-Berechtigung
   auf V1-Datenbanken, ohne bestehende V1-Zugriffe zu beeinträchtigen.
3. Technisch erzwungene Freigabeschritte für Fakten und Inventar.
4. Verantwortung und Eigentümerschaft der Migrationsrolle. GRANT CREATE
   macht sie nicht zur Eigentümerin bereits bestehender Tabellen.
5. Default Privileges für Objekte zukünftiger Migrationen, anschließend
   echte Tests mit separaten LOGIN-Rollen.


## Fortsetzung nach erfolgreich geprüfter Migration 0002

Der vollständige Rollen- und Login-Entwurf ist nun in
[`PHASE0_ACCESS_ARCHITECTURE.md`](PHASE0_ACCESS_ARCHITECTURE.md)
dokumentiert. Migration `0003_access.sql` wird **erst nach Prüfung in
`retro_rag_v2_test`** eingesetzt; sie erzeugt deaktivierte Loginrollen
und überträgt das V2-Objekteigentum. Die Vorlage für HBA-Regeln liegt unter
`deploy/postgresql/pg_hba_v2_example.conf` und wird nicht automatisch aktiviert.

Die schon angewendete Migration `0002_roles.sql` bleibt unverändert.
Für eine spätere Produktivdatenbank in demselben Cluster ist stattdessen
`db/bootstrap/0002_roles_existing_cluster.sql` als geprüfter Rollen-
Wiederverwendungsweg vorgesehen. **V1-Berechtigungen nicht verändern.**


## Aktueller Stand nach Migration 0004 (08.11.2026)

Die vorstehenden Abschnitte beschreiben die ursprüngliche Planung von Migration 0002. Inzwischen wurden 0002 und 0003 auf `retro_rag_v2_test` erfolgreich angewendet. Reader-, Importer- und Migrator-Login sind aktiviert. Die Importer-/Migrator-HBA-Regeln (Zeilen 125–129) wurden vor den allgemeinen `trust`-Regeln ergänzt und geprüft, und je drei real ausgeführte Negativtests pro Rolle bestanden. Migration 0004 führt die transaktional gesperrte Schreibfreigabeprüfung mit `SECURITY DEFINER` ein, ohne `UPDATE` auf `write_gate` zu vergeben. `verify_0004.sql` und der echte Importer-Test bei geschlossenem Gate wurden bestanden. Die übrigen vier Loginrollen, offenes Gate, vollständiges Staging und IPv6-/Container-Fremdzugriffe bleiben offen. Vollständige Details und Nachweise: [`IMPORTER_WRITE_GATE.md`](IMPORTER_WRITE_GATE.md).
