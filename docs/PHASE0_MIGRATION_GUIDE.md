# Retro-RAG V2 – Phase 0 / Migration `0001_init.sql`

**Stand:** 08.11.2026 · **Status:** Entwurf, noch nicht auf Poseidon ausgeführt.

Grundlage: `README.md`, `conventions.md`, `docs/Retro-Rag V2.mm` (Stand 08.11.2026).

## Ziel und Sicherheitsgrenze

- Retro-RAG V1 verbleibt unverändert in **`retro_rag`**. Die alte Testdatenbank **`retro_rag_test`** bleibt ebenfalls unverändert.
- V2 erhält eine **eigene PostgreSQL-Datenbank**: `retro_rag_v2`.
- Ein **eigenes Schema** `rag_v2` enthält alle neuen Objekte. Für Tests ist nur `retro_rag_v2_test` zusätzlich erlaubt.
- Das SQL verwendet keine `DROP`-Befehle und keinerlei Verweise auf V1-Tabellen. Der erste Transaktionsblock prüft den Datenbanknamen, die PostgreSQL-Hauptversion 16 und das Nichtvorhandensein des Schemas `rag_v2`.
- Die Initialisierung ist **nicht wiederholbar**: Eine erneut aufgerufene `0001_init.sql` bricht ab. Weitere Änderungen erfolgen ausschließlich über `0002_...sql`, `0003_...sql` usw.
- Die Migration nutzt ausschließlich neue Tabellen und installiert die Extension `vector` nur in der Ziel-Datenbank. Das auf V1 vorhandene pgvector wird nicht berührt.
- `write_gate.writes_enabled` startet absichtlich mit `false`. **Das ist zunächst eine persistente Konfigurationssperre**: Worker/API müssen sie später aktiv prüfen; allein die Tabelle verhindert noch keine direkten SQL-Schreibzugriffe.

## Inhalt von `0001`

| Bereich | Tabellen | Besonderheiten |
|---|---|---|
| Hardware-Stammdaten | `component_type`, `article`, `article_revision`, `article_alias` | UUID; `model_key` **nicht** eindeutig |
| Inventar | `unit`, `system`, `storage_location`, `installation`, `storage_assignment`, `unit_condition_history` | UUID + lesbare Inventarnummer; Zustandsaudit; nur eine aktive Standortzuordnung über zwei Tabellen |
| Dokumente | `document`, `document_source`, `document_version` | stabile logische Identität, externe Quell-ID, eigener Version-Hash; Verfügbarkeit und Verarbeitung getrennt |
| Suche | `chunk`, `embedding_model`, `chunk_embedding` | versionsgebundene Chunks; PostgreSQL-FTS; variabler `vector`-Typ, Dimension gegen Modell validiert |
| Wissen | `reference_entity`, `knowledge_subject`, `property`, `property_component_type`, `fact`, `evidence`, `fact_evidence`, `compatibility_rule`, `compatibility_rule_evidence` | typisierte Werte; echte FK-Verknüpfung über `knowledge_subject`; freigegebene Fakten/Regeln brauchen Belege |
| Import und Review | `trusted_source`, `processing_job`, `processing_step`, `processing_artifact`, `review_batch`, `review_item`, `review_decision` | unabhängiger technischer Ablauf und Freigabe; Leases/Retries; externe Vertrauensfreigabe |
| Betrieb | `sync_run`, `document_error`, `query_log`, `write_gate`, `schema_migration` | historische Protokolle und kontrollierter Restore |

**Wichtige Implementierungsdetails:**

- Neue `document_version`-Datensätze haben vor der erfolgreichen Indexierung `state = NULL`; erst danach `active`/`superseded`/`archived`. Nur eine Version je Dokument kann `active` sein. Die Obergrenze der zusätzlich durchsuchbaren `superseded`-Versionen setzt zunächst die Lifecycle-Logik durch.
- `chunk` ist per `ON DELETE CASCADE` von `document_version` abhängig; `document_version` selbst wird jedoch durch Belege und Fremdschlüssel vor pauschalem Löschen geschützt.
- `source_unavailable` bleibt als historischer Belegstatus erhalten. Eine Retrieval-Aussage aus ausschließlich fehlenden Quellen darf künftig nicht einfach als bestätigt ausgegeben werden.
- Jede `unit` beschreibt ein **physisches Exemplar**. Die Menge ergibt sich aus der Zahl der Exemplare, nicht aus einem automatisch hochgezählten Dubletten-Datensatz.
- `unit.completeness = NULL` bedeutet vorläufig „noch nicht erfasst“. Die Konvention nennt bislang nur `complete`/`incomplete`; ob für die UI ein dritter expliziter Zustand nötig ist, sollte vor Phase 2 entschieden werden.
- Eine Eigenschaft ohne Eintrag in `property_component_type` ist momentan für alle Arten zulässig. Sind erlaubte Arten hinterlegt, prüft ein Trigger sie für Artikel/Revisionen.
- `compatibility_rule.conditions` ist bewusst ein JSON-Objekt ohne finale DSL. Ein deterministischer Evaluator wird **nicht** durch diese Migration implementiert.
- Auf `chunk_embedding` werden noch keine HNSW-Indizes erstellt. Diese benötigen zur gewählten Dimension passende partielle bzw. Ausdrucksindizes und werden nach den Retrieval-Tests nachgerüstet.

## Sicheres Vorgehen auf Poseidon

> Befehle sind Beispiele und wurden **nicht** auf Poseidon ausgeführt. `psql` und `pg_dump` müssen als berechtigter PostgreSQL-Benutzer gestartet werden. Mit `sudo -u postgres` geht das bei üblicher Debian-Konfiguration. **Keinen Befehl ungeprüft mit falschem Datenbanknamen ausführen.**

### 1. V1 sichern und referenzieren

```bash
mkdir -p "$HOME/retro-rag-db-backups"
chmod 700 "$HOME/retro-rag-db-backups"

sudo -u postgres pg_dump -Fc -d retro_rag \
  > "$HOME/retro-rag-db-backups/retro_rag_v1_before_v2_0001.dump"

sudo -u postgres pg_dump --schema-only -d retro_rag \
  | sha256sum > "$HOME/retro-rag-db-backups/retro_rag_v1_schema_before.sha256"
```

### 2. **Nur** neue Testdatenbank anlegen

```bash
sudo -u postgres createdb -T template0 -E UTF8 retro_rag_v2_test
sudo -u postgres ./db/migrate_0001.sh --database retro_rag_v2_test
sudo -u postgres ./db/migrate_0001.sh --database retro_rag_v2_test --apply
sudo -u postgres psql -X -v ON_ERROR_STOP=1 -d retro_rag_v2_test \
  -f db/checks/verify_0001.sql
sudo -u postgres psql -X -v ON_ERROR_STOP=1 -d retro_rag_v2_test \
  -f db/checks/smoke_0001_test.sql
```

`sudo -u postgres ./db/migrate_0001.sh` setzt voraus, dass der Benutzer `postgres` Lese- und Ausführungsrechte am Repository besitzt. Andernfalls das Verzeichnis geeignet freigeben oder das SQL mit `sudo -u postgres psql` ausführen. **Keine Datenbankzugangsdaten in Git speichern.**

### 3. Produktions-V2 anlegen, nochmals sichern und migrieren

Erst nach erfolgreichem Test:

```bash
sudo -u postgres createdb -T template0 -E UTF8 retro_rag_v2
sudo -u postgres pg_dump -Fc -d retro_rag_v2 \
  > "$HOME/retro-rag-db-backups/retro_rag_v2_before_0001.dump"

sudo -u postgres ./db/migrate_0001.sh --database retro_rag_v2
sudo -u postgres ./db/migrate_0001.sh --database retro_rag_v2 --apply
sudo -u postgres psql -X -v ON_ERROR_STOP=1 -d retro_rag_v2 \
  -f db/checks/verify_0001.sql
```

### 4. V1-Nachprüfung

```bash
sudo -u postgres pg_dump --schema-only -d retro_rag \
  | sha256sum > "$HOME/retro-rag-db-backups/retro_rag_v1_schema_after.sha256"

diff -u \
  "$HOME/retro-rag-db-backups/retro_rag_v1_schema_before.sha256" \
  "$HOME/retro-rag-db-backups/retro_rag_v1_schema_after.sha256"
```

Erwartung: `diff` bleibt leer. Das beweist eine unveränderte **Schemastruktur**; es ersetzt keine Datenintegritäts-/Backupprüfung. Die V1-Datenbank wird in keiner der Migrationsanweisungen als Schreibziel verwendet.

## Bewusst noch nicht Teil von `0001`

1. **Datenbankrollen und Grants:** `rag_importer`, `rag_reviewer`, `rag_inventory`, `rag_reader`, separate Migrationsrolle; optionale `rag_lifecycle`-Rolle. Die Rollen sind Cluster-Objekte und sollen erst nach gesondertem Rechteentwurf eingerichtet werden. Bis dahin kein V2-App-Login einsetzen und keine Tabellen für `PUBLIC` freigeben. Der Datenbankname allein ist keine Zugriffsbarriere; die spätere Rollen-Konfiguration muss V1-Zugriffe verhindern, ohne V1 zu verändern.
2. **Importvertrag v0:** Pydantic für `contract_version`, `source`, `document`, `chunks`, `fact_proposals`, `warnings`, inklusive Review/Validierung.
3. **Wissenskatalog** `schema/properties.yaml` und Anfangswerte für Komponentenarten.
4. **Release-Transaktionen:** atomar Index aktivieren, vorherige Version überführen, höchstens zwei suchbare Versionen; Source-Delete-/Restore-Schutz und Schreibsperren durch Worker.
5. **Workflow-Schutz:** tatsächliche Bestätigung durch FastAPI/Auth, keine LLM-Schreibrechte, begrenzte Grants und Auditierung; `write_gate` allein erfüllt das noch nicht.
6. **Vektorsuche:** Modell-Dimension und Distanzmetrik bei Queries erzwingen, ANN-Indizes entsprechend den gewählten Modellen erstellen.
7. **Verbesserte Historisierung:** Änderungen von bestätigten Fakten, Eigenschaftsdefinitionen und Berechtigungen im Anwendungsworkflow strikt nachhalten; die vorhandene Faktengültigkeit ersetzt keine vollständige Änderungsjournalisierung.

## Teststatus

- Die Dateien wurden in einer isolierten Arbeitsumgebung erstellt; kein Zugriff auf den laufenden PostgreSQL-Server Poseidon.
- Shell-Syntax und statische Sicherheitsaspekte können hier geprüft werden.
- **Eine echte PostgreSQL-16-/pgvector-Migration und die Laufzeittests konnten hier mangels `psql`/Server nicht ausgeführt werden.** Deshalb ist der Test auf `retro_rag_v2_test` vor jeder produktiven Anwendung verpflichtend.

## Historischer Migrationsleitfaden – nachträglicher Status 08.11.2026

Die oben stehenden Aussagen „Entwurf“, „noch nicht auf Poseidon ausgeführt“ und „keine echten PostgreSQL-Tests“ beziehen sich auf den ursprünglichen Planungsstand der Initialmigration 0001, **nicht** auf den heutigen Zustand. Auf `retro_rag_v2_test` sind inzwischen die Migrationen 0001 bis einschließlich 0004 angewendet; 0004 wurde durch `verify_0004.sql` und einen Realtest als `rag_v2_importer_login` bei geschlossenem Gate bestätigt. Reader, Importer und Migrator sind mit getrennten HBA-Regeln aktiviert. Die übrigen vier Loginrollen und die Integrationstests bei geöffnetem Gate bleiben offen. Details unter [`IMPORTER_WRITE_GATE.md`](IMPORTER_WRITE_GATE.md). Keine nachträgliche Veränderung bereits angewendeter Migrationsdateien.


## Nachtrag 09.11.2026: Migration 0005 angewendet

Die ursprünglichen Anleitungen oben sind historische Phase-0-Planungsanweisungen. Aktuell wurde auf Poseidon `0005_document_identity.sql` über `rag_v2_migrator_login` / `SET ROLE rag_v2_migrator` in `retro_rag_v2_test` mit `COMMIT` abgeschlossen. Vorher: Quelle/Dokument/Version/Review jeweils 0, Marker 1–4 vorhanden und Write-Gate gesperrt. Sicherung: `/home/nina/backups/retro-rag-v2/pre_migration_0005.dump`, 123 KB, Modus `0600`, Inhaltsverzeichnis mit `pg_restore --list` geprüft (kein Restore-Test). `verify_0005.sql` bestätigte Spalte, Index, Constraint und Importer-Berechtigungen. Nachkontrolle bestätigte Marker 5 und `writes_enabled=f`. Die vollständigen Ergebnisse und noch offenen Integrationstests stehen in [DOCUMENT_IDENTITY.md](DOCUMENT_IDENTITY.md) und [db/SCHEMA_CURRENT.md](../db/SCHEMA_CURRENT.md). Der reale SQL-Schema-Snapshot muss nach 0005 neu exportiert werden.
