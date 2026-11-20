# Migration 0006 – technischer Entwurf (universeller Wissenskern)

**Status:** ENTWURF, nicht auf Poseidon angewendet; fachliche Ziele 3.0 und Modell 3.1 sind Grundlage.
**Branch:** `feat/universal-knowledge-schema-0006`, Basis `integration/import-pipeline-2026-11-09`.
**Quelle der Wahrheit:** `db/migrations/0001_init.sql` bis `0005_document_identity.sql`; vorhandene 37 Tabellen.
**Geltung:** ausschließlich `retro_rag_v2_test` bzw. spätere ausdrücklich freigegebene V2-DB. V1 und Nextcloud bleiben unberührt.

## Umfang
- Sechs neue Tabellen: `entity_type`, `knowledge_topic`, `knowledge_topic_assignment`, `entity_relation`, `entity_relation_evidence`, `knowledge_proposal`.
- Ersetzt den hart codierten CHECK auf `reference_entity.entity_type` durch einen FK auf einen vorbefüllten, erweiterbaren Typkatalog. Alte Werte bleiben erhalten.
- Neue universelle Beziehungen erhalten `status`, optionalen Gültigkeitszeitraum, Kontext und einen deferred Belegpflicht-Trigger.
- Die neue Sicht `accepted_entity_relation` zeigt nur bestätigte Beziehungen.
- Themen stehen ausdrücklich neben `knowledge_subject` (dieses bleibt Identitätsanker).
- Vorschläge sind unveränderliche Eingangsdatensätze. Herkunft und Eingangsquellen werden gespeichert. Kein `accepted`-Status in der Vorschlagstabelle, keine automatische Veröffentlichung.
- `fact`, `property`, `evidence`, `review_item` sowie die Hardware- und Dokumenttabellen bleiben in 0006 unverändert.

## Bewusste Grenzen
- Kein freigegebenes universelles Relationstyp-Vokabular; `relation_type` wird derzeit nur syntaktisch geprüft. Vor produktiven Freigaben muss ein kontrollierter Katalog/Policy eingebunden werden.
- Die bestehende allgemeine Reader-Rolle hat SELECT auf bestehende Faktentabellen, auch auf Datensätze mit `status='proposed'`. Ein späterer sicherer Abfragepfad muss auch dort den bestätigten Status strikt filtern.
- Die Prüfung der Belegpflicht stellt Existenz, nicht die Qualität oder Unabhängigkeit des Belegs sicher.
- `knowledge_proposal` ist noch nicht per FK mit `review_item` verknüpft. Freigabeprozess, Rule-Versionen, vollständige Auditierung und Ablaufsteuerung sind Folgeschritte.
- Das `provenance`-JSON ist in 0006 strukturell, nicht semantisch validiert. Produktionsfreigabe benötigt ein konkretes Schema.
- Der Gate-Trigger verhindert Proposal-INSERT bei geschlossenem Gate. Rollen, die das Gate über ihre Berechtigungen umgehen könnten, dürfen nicht für Agenten eingesetzt werden.
- Die topic-Zyklusprüfung benötigt Transaktionstests einschließlich Parallelität. Advisory Lock ist Teil der Strategie.
- Fail-closed: Ein Trigger sperrt den Status `accepted` für universelle Beziehungen vollständig, bis eine versionierte, kontrollierte Freigabeimplementierung vorliegt. Künftige Freigabefunktionen müssen das sauber und unter geringsten Privilegien ersetzen.

## Vor Anwendung
1. Branchdiff und DDL fachlich/technisch prüfen.
2. Aktuellen realen Schema-Snapshot der V2-Test-DB gegen den Migrationsstand 5 abgleichen.
3. Validiertes Backup; Restore-Test separat einplanen.
4. Rolle `rag_v2_migrator` und DB-Schutzabfragen prüfen.
5. Erst mit expliziter Ausführungsfreigabe die Migration auf `retro_rag_v2_test` testen.

## Prüfartefakte
- `db/checks/verify_0006.sql`: strukturelle und zentrale Rechte-Prüfungen (lesend).
- `db/checks/test_0006_integrity.sql`: Rollback-basierte Negativtests für Zyklus und geschlossenes Gate.
- Darüber hinaus sind erforderlich: Tests für Belegpflicht und Historisierung von Beziehungen, Parallelität, Zugriffsrollen, bestehende 0001–0005-Invarianten, die Importpipeline und Restore-/Rollback-Szenarien.

**Wichtig:** Ein Commit dieser Dateien ist ausdrücklich kein Nachweis bestandener Integrationstests.

## Transaktionale PostgreSQL-Abnahme vom 20.11.2026

- Auf Poseidon wurde 0006 zusammen mit `verify_0006.sql` und `test_0006_integrity.sql` in einer einzigen Transaktion mit entferntem Abschluss-`COMMIT` ausgeführt.
- Beide Prüfskripte meldeten `PASS`; der Lauf endete mit `ROLLBACK`.
- Nachkontrolle: Migrationsstand 5, 37 Tabellen, `writes_enabled=false`.
- Dieser Nachweis deckt **nicht** echte Login-/HBA-Verbindungen, gleichzeitige Schreibvorgänge oder dauerhafte Anwendung ab.

Neu: `db/checks/test_0006_role_boundaries.sql` prüft die Rechte mit `SET ROLE` für Importer, Reader und Reviewer in derselben äußeren Testtransaktion. Diese Prüfung ist **noch nicht auf Poseidon ausgeführt**. Sie simuliert Rollenrechte, ersetzt aber keine Tests mit echten Loginidentitäten.

### Erweiterter Rollentest (Poseidon, 20.11.2026)

Auf dem Branch `feat/universal-knowledge-schema-0006` (lokaler Stand vor dieser Dokumentation: `7fe43ef`) wurden Migration `0006` ohne terminales `COMMIT`, `verify_0006.sql`, `test_0006_integrity.sql` und `test_0006_role_boundaries.sql` in **einer** PostgreSQL-Transaktion ausgeführt.

Übermittelte psql-Ausgabe:
- `verify_0006: Struktur und zentrale Rechte PASS`
- `0006 Integritaetstests PASS (noch ROLLBACK erforderlich)`
- `0006 role: importer PASS`
- `0006 role: reader PASS`
- `0006 role: reviewer PASS`
- `0006 Rollengrenzen PASS (noch ROLLBACK erforderlich)`
- abschließend `ROLLBACK`, keine Fehlermeldung im übermittelten Testlauf.

**Aussagekraft:** DDL, interne Prüfungen und transaktionale Rechtewechsel per `SET ROLE` bestanden. Ein Nachcheck der persistenten Tabellenanzahl/Migrationsmarker **nach diesem erweiterten Lauf**, unabhängige Login-/HBA-Tests sowie Konkurrenz-/Restore-Tests sind noch offen. Kein dauerhafter Apply von `0006` nachgewiesen.

### Unabhängige Rollback-Nachkontrolle (Poseidon)

Nach dem erweiterten transaktionalen Test wurde über eine **neue psql-Verbindung** nachgeprüft:
- `MAX(rag_v2.schema_migration.version) = 5`
- `information_schema.tables` für Basistabellen in `rag_v2`: **37**
- `rag_v2.write_gate.writes_enabled = false` (Grund weiterhin `Parallelitätstest erfolgreich; Freigabe ausstehend`)
- `to_regclass('rag_v2.knowledge_proposal') IS NULL`

Alle vier Sollwerte sind erfüllt. Der vollständige Rollback der letzten Testtransaktion ist damit unabhängig nachkontrolliert. Authentifizierungs-/HBA- und Parallelitätstests bleiben ausstehend.

### Vorprüfung Loginrollen und HBA-Konfiguration (Poseidon, 20.11.2026)

Über `pg_auth_members` mit `pg_has_role(..., 'USAGE'/'SET')` wurde bestätigt:
- Alle sieben `rag_v2_*_login`-Rollen erben jeweils die vorgesehene technische Gruppe.
- Nur `rag_v2_migrator_login` darf `SET ROLE` in seine technische Gruppe ausführen, die übrigen sechs Mitgliedschaften nicht.
- `rag_v2_importer_login`, `rag_v2_reader_login` und `rag_v2_migrator_login` sind laut `pg_roles` LOGIN; `rag_v2_reviewer_login` ist NOLOGIN.

Die Ansicht `pg_hba_file_rules` zeigte vorgelagerte `reject`-Regeln für lokale Unix-Sockets sowie `scram-sha-256` für loopback-TCP (`retro_rag_v2_test`) und weitere `reject`-Regeln für die Reader-/Importer-/Migrator-Loginrollen. Zusätzlich bestehen allgemeinere `trust`-Regeln für `local all all` und Loopback-TCP für `all/all`. Diese können für andere Rollen und Datenbanken passwortfreie Authentifizierung ermöglichen. **Sicherheitsbefund außerhalb von 0006**: globale Trust-Härtung nur nach Abhängigkeitsprüfung für bestehende Datenbanken/Dienste. Nicht ungeprüft ändern.

**Noch nicht verifiziert:** tatsächliche Regelpriorität mittels `rule_number` (statt nur `line_number`), vom Server zuletzt geladene Konfiguration und erfolgreicher/abgewiesener tatsächlicher Login über TCP. `pg_hba_file_rules` reflektiert die aktuellen Dateien, nicht notwendigerweise die zuletzt geladenen Einstellungen. Die HBA-Ausgabe wurde deshalb nicht als bestandener Authentifizierungstest bewertet.

### HBA-Regelreihenfolge und Reader-SCRAM-Negativtest (Poseidon, 20.11.2026)

Die Ansicht `pg_hba_file_rules` wurde nach `rule_number` gelesen; alle **17 Zeilen haben `error IS NULL`**. Wesentliche erste Treffer:
- Reader: Regel 1 `local all rag_v2_reader_login reject`; Regeln 2 und 3 `retro_rag_v2_test` über `127.0.0.1/32` bzw. `::1/128` mit `scram-sha-256`; Regeln 4/5 andere Hosts `reject`.
- Importer/Migrator: Regel 6 lokale Sockets `reject`; Regeln 7/8 TCP-Loopback auf `retro_rag_v2_test` mit `scram-sha-256`; Regeln 9/10 alle übrigen Hosts `reject`.
- Erst Regeln 11–13: allgemeines `trust` für lokalen Socket / IPv4-/IPv6-Loopback. Diese bleiben für andere Rollen eine gesonderte Sicherheitsfrage.
- `pg_conf_load_time()` lieferte `2026-11-20 14:01:53.912068+00`. Die Datei-Ansicht allein beweist nicht, wann die letzten HBA-Dateiänderungen geladen wurden.

**Tatsächlich ausgeführter Negativtest:** TCP im PostgreSQL-Container nach `127.0.0.1:5432` als `rag_v2_reader_login` auf `retro_rag_v2_test`, absichtlich falsches Passwort, Ergebnis `FATAL: password authentication failed for user "rag_v2_reader_login"`. Das ist ein bestandener *Negativtest* der Reader-Authentifizierung und kein Nachweis einer erfolgreichen Anmeldung mit gültigem Passwort.

**Ausstehend:** Importer-/Migrator-Negativtests, positive Anmeldung mit gültigen Zugangsdaten (ohne Offenlegung), IPv6- und Socket-Tests nach Bedarf sowie Parallelität in einer isolierten persistenten Testdatenbank.

### Importer-/Migrator-SCRAM-Negativtests (Poseidon, 20.11.2026)

Auf der vorhandenen V2-Testdatenbank über TCP `127.0.0.1:5432` wurden beide aktivierten Rollen mit bewusst falschem Passwort getestet:
- `rag_v2_importer_login`: `FATAL: password authentication failed for user "rag_v2_importer_login"`
- `rag_v2_migrator_login`: `FATAL: password authentication failed for user "rag_v2_migrator_login"`

Beide **Negativtests bestanden**. Gemeinsam mit dem bereits dokumentierten Reader-Test liegen damit drei tatsächliche Passwort-Ablehnungen vor. Die Bedeutung ist begrenzt auf diesen Verbindungsweg und die getestete Datenbank; positive Logins mit gültigem Passwort und parallele Datenbanksitzungen sind weiterhin offen. Weder Rollen noch HBA-Regeln wurden für diese Tests verändert.

### Positive TCP-Logins Reader/Importer (Poseidon, 20.11.2026)

Zusätzlich zu den fehlgeschlagenen Passwort-Negativtests wurden beide Rollen mit interaktiver Passworteingabe über `psql -X -W -h 127.0.0.1` und echte TCP-Verbindungen zur `retro_rag_v2_test` erfolgreich authentifiziert:

| Rolle | `session_user` | `current_user` | `current_database()` | `inet_client_addr()` |
|---|---|---|---|---|
| `rag_v2_reader_login` | `rag_v2_reader_login` | `rag_v2_reader_login` | `retro_rag_v2_test` | `127.0.0.1` |
| `rag_v2_importer_login` | `rag_v2_importer_login` | `rag_v2_importer_login` | `retro_rag_v2_test` | `127.0.0.1` |

**Ergebnis:** positive Authentifizierung für Reader und Importer nachgewiesen. Keine Passwörter protokolliert. Der Migrator ist nur negativ getestet; eine positive Migrator-Anmeldung und isolierte konkurrierende Transaktionen bleiben offen. Diese Logins beweisen keine weiteren Rechte an Schemaobjekten über die bereits transaktional getesteten `SET ROLE`-Grenzen hinaus. `0006` wurde weiterhin nicht dauerhaft angewendet.
