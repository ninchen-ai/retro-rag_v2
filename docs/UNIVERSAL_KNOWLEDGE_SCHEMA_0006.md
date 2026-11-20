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

### Positive Migrator-Anmeldung und `SET ROLE` (Poseidon, 20.11.2026)

Mit `psql -X -W -h 127.0.0.1 -U rag_v2_migrator_login -d retro_rag_v2_test` wurde eine echte TCP-/SCRAM-Anmeldung nachgewiesen:
- Vor Rollenwechsel: `session_user = rag_v2_migrator_login`, `current_user = rag_v2_migrator_login`
- `SET ROLE rag_v2_migrator` erfolgreich; danach `session_user = rag_v2_migrator_login`, `current_user = rag_v2_migrator`
- `RESET ROLE` erfolgreich.

Alle drei aktivierten V2-Loginrollen (Reader, Importer, Migrator) wurden sowohl mit falschem Passwort abgewiesen als auch mit gültigem Passwort erfolgreich authentifiziert. HBA- und LOGIN-Prüfungen über IPv4-Loopback **PASS**. Andere Verbindungswege und isolierte Parallelitätstests sind weiterhin offen. Kein Apply von Migration `0006`.

### Persistente Anwendung auf `retro_rag_v2_test` (Poseidon, 20.11.2026)

Die Nutzerin hat den regulären Testdatenbank-Apply freigegeben und folgende Ergebnisse des vollständigen lokalen Ablaufs übermittelt:

- Vorprüfung bestand: Migration 5, 37 Tabellen, geschlossenes `write_gate`, keine `knowledge_proposal`-Tabelle.
- Vorherige Sicherung: `/home/nina/backups/retro-rag-v2/retro_rag_v2_test_pre0006_20261120_164032.dump`; Dateimodus `600`, Größe 123 KiB.
- SHA-256 der Sicherung: `6325f1563eb5f54436f914740cdd1c837f7b101cc6e8fc9b0ea97418931dedd0`
- `pg_dump -Fc` und Archivleseprüfung durch `pg_restore --file=/dev/null` erfolgreich; **kein vollständiger Wiederherstellungstest**.
- SQL-Migration `db/migrations/0006_universal_knowledge_core.sql` unter `SET ROLE rag_v2_migrator` auf der bestehenden Datenbank `retro_rag_v2_test` regulär ausgeführt; psql meldete **`COMMIT`**.
- Unmittelbar folgende, unabhängige Prüfung `db/checks/verify_0006.sql`: **`verify_0006: Struktur und zentrale Rechte PASS`**.
- Terminal meldete `MIGRATION 0006 UND STRUKTURPRÜFUNG ABGESCHLOSSEN`.

**Status:** Migration `0006` dauerhaft in der vorhandenen **V2-Testdatenbank** angewendet, nicht in V1 oder Nextcloud. Die unabhängige Post-Apply-Abfrage von Versionsmarker, 43 Tabellen, Gate und katalogisierten Entitätstypen sowie der Mehrverbindungstest sind noch durchzuführen. Das bisherige C1-Konkurrenztestskript `tests/test_version_activation_concurrency.py` ist ausdrücklich auf einen alten, separat isolierten Cluster begrenzt und darf **nicht** unverändert gegen diese Testdatenbank ausgeführt werden.

### Nachkontrolle des dauerhaft migrierten Testschemas und geplanter Konkurrenztest

Die nach dem Commit separat ausgeführten Abfragen ergaben:
- `MAX(schema_migration.version) = 6`
- **43** Basistabellen in `rag_v2`
- **15** Entitätstypen
- `writes_enabled=false`, Sperrgrund weiterhin `Parallelitätstest erfolgreich; Freigabe ausstehend`
- **0** Datensätze in `knowledge_proposal`

Damit ist das dauerhaft installierte Testschema unabhängig nachkontrolliert.

`tests/run_0006_concurrency.py` wurde als **noch nicht ausgeführter** Mehrverbindungstest ergänzt. Er verwendet echte Importer-/Migrator-Logins über SCRAM und mehrere unabhängige PostgreSQL-Sitzungen gegen die bestehende `retro_rag_v2_test`. Das Skript testet:
1. Gegensätzliche konkurrierende Umhängungen zweier ausschließlich testbezogener Themen und tatsächliches Warten (`pg_blocking_pids`).
2. Eine nicht committete Änderung des `write_gate` gegen einen gleichzeitig versuchten Import sowie dessen Ablehnung nach dem Rollback.
3. Zwei parallele Importversuche bei geschlossenem Gate.

Der Test legt zwei kurzlebige Themenfixtures mit UUID an, committet diese für Sitzungssichtbarkeit und entfernt sie im `finally`-Block. Er führt **kein committed Öffnen des Write-Gates** aus und prüft den wieder geschlossenen Zustand. Bei hartem Prozessabbruch können Topics zurückbleiben: Die UUIDs werden deshalb vor dem Test ausgegeben und sind gezielt zu bereinigen. Vor Ausführung das Skript lokal syntaktisch prüfen. Der bestehende C1-Konkurrenztest wird **nicht** für diese Datenbank umfunktioniert.

### Mehrverbindungstests für Migration `0006` – bestanden (Poseidon, 20.11.2026)

Der Test `tests/run_0006_concurrency.py` wurde nach `python -m py_compile` auf dem bestehenden Datenbankserver über `nsenter` (Netzwerk-Namespace des Containers `codeanalyse-postgres`) gegen `retro_rag_v2_test` ausgeführt. Verwendet wurden zwei unterschiedliche reale SCRAM-Loginidentitäten: `rag_v2_migrator_login` und `rag_v2_importer_login`. Passwortabfragen erfolgten interaktiv.

Übermittelte Ergebnisse:

- `PASS 0006: Topic-Zyklus verhindert; Blockierung beobachtet`
- `PASS 0006: Gate-Serialisierung und parallele Import-Ablehnung`
- `PASS 0006: Test-Fixures bereinigt, Write-Gate geschlossen`
- `PASS 0006: Mehrverbindungstests abgeschlossen`

Die Testthemen `8e38a16e-e92d-46a6-bf48-01b1e426d270` und `f8b7fe55-a33a-4ada-8b97-397d1745e1d2` wurden laut Skriptbereinigung entfernt. Der Test prüfte nach seiner eigenen Bereinigung die Themenanzahl und `writes_enabled = false`.

**Bewertung:** Gegenläufige Änderungen an der Themenhierarchie werden im getesteten Mehrverbindungsszenario serialisiert, Zyklen verhindert; ein parallel laufender Vorschlagsimport wird durch das Write-Gate blockiert und nach dessen Rollback abgewiesen. Keine dauerhafte Freigabe des Gates erfolgt. Damit ist dieser definierte Parallelitätstest **PASS**.

**Ausstehend für Abschlussabnahme:** unabhängige Bestandskontrolle nach dem Lauf, Regressionstests der vorhandenen Importpipeline sowie ggf. ein echter Restore-Test des Backups. Der Parallelitätstest beweist nicht alle denkbaren Interleavings oder die spätere Policy-Freigabelogik.

### Pytest-Regressionslauf und Absicherung älterer Integrationstests

Auf Poseidon wurde bei dauerhaft angewendeter Migration `0006` auf dem Branch `feat/universal-knowledge-schema-0006` der Befehl `python -m pytest -q -rs` ausgeführt. Ergebnis: **24 passed, 11 skipped, 0 failed** (0,21 s).

Skip-Gründe: 4 × `RETRO_V2_IDENTITY_TEST_DSN` fehlt; 6 × `RETRO_V2_C1_TEST_DSN` fehlt; 1 × `RETRO_V2_C1_ISOLATED_DSN` fehlt. Das sind keine fehlgeschlagenen Datenbanktests; die zehn rollback-only Integrationstests wurden **nicht ausgeführt**.

Prüfung des Codes ergab, dass die Fixtures in `tests/test_document_identity_integration.py` und `tests/test_version_activation_integration.py` zusätzlich den Schema-Endstand **genau 0005** erforderten. Für die bestehende migrierte Testdatenbank wurde dieser Prüfpunkt auf `0005 oder 0006` erweitert. Alle übrigen Schutzbedingungen – nur `retro_rag_v2_test`, dedizierter `rag_v2_migrator_login`, anfänglich geschlossenes Write-Gate, uncommitted Testdaten mit Rollback – bleiben erhalten. **Die zehn nach DSN-Vergabe möglichen Integrationstests sind noch nicht erneut ausgeführt.**

Der alte `tests/test_version_activation_concurrency.py` bleibt unverändert: Er verlangt ausdrücklich `cluster_name='retro-rag-v2-c1-isolated'` und darf **nicht** gegen die bestehende Testinstanz gestartet werden. Die neu hinzugefügten 0006-Konkurrenztests sind separat bestanden.

### Rollback-only Integrationstests auf dauerhaftem Schema 0006 bestanden (Poseidon, 20.11.2026)

Nach dem Aktualisieren des Branches auf `bad0747` wurden die vormals übersprungenen Integrationstests mit echten Migrator-Zugangsdaten über TCP im Netzwerk-Namespace von `codeanalyse-postgres` auf `retro_rag_v2_test` gestartet. Die beiden Umgebungsvariablen `RETRO_V2_IDENTITY_TEST_DSN` und `RETRO_V2_C1_TEST_DSN` wurden ausschließlich im Testprozess gesetzt; die Zugangsdaten wurden interaktiv abgefragt und nicht im Testprotokoll gespeichert.

Befehl (gekürzt): `pytest -q -rs tests/test_document_identity_integration.py tests/test_version_activation_integration.py`

**Übermittelte Ausgabe: `10 passed in 0.19s`**, davon 4 Dokumentidentitäts- und 6 C1-Versionsaktivierungs-Integrationstests. Keine Fehler und keine Skips in diesem gezielten Lauf.

Zusammen mit dem vorherigen regulären Pytest-Lauf (`24 passed, 11 skipped`) wurden somit **34 unterschiedliche Pytest-Testfälle erfolgreich ausgeführt**. Der weiterhin auf den alten separat isolierten Cluster begrenzte `test_version_activation_concurrency.py` wurde nicht ausgeführt. Der neue 0006-Mehrverbindungstest wurde separat bereits bestanden.

**Vorläufige Bewertung:** Die bisherige Importlogik (Dokumentidentität und Versionsaktivierung) funktioniert im getesteten Umfang unter Schema 0006. Abschlussabnahme bleibt von einer unabhängigen Bestandskontrolle und der Bewertung der Wiederherstellbarkeit des Backups abhängig.

### Unabhängige Abschlusskontrolle nach allen Tests (Poseidon, 20.11.2026)

Nach dem separaten erfolgreichen Lauf der 10 rollback-only Integrationstests wurde eine neue lesende SQL-Abfrage gegen die dauerhaft migrierte `retro_rag_v2_test` ausgeführt. Gemeldete Werte:

| Prüfung | Ergebnis |
|---|---|
| `MAX(schema_migration.version)` | `6` |
| Basistabellen im Schema `rag_v2` | `43` |
| `rag_v2.write_gate.writes_enabled` | `false` |
| `rag_v2.write_gate.reason` | `Parallelitätstest erfolgreich; Freigabe ausstehend` |
| `knowledge_topic` | 0 Datensätze |
| `entity_relation` | 0 Datensätze |
| `knowledge_proposal` | 0 Datensätze |

**Befund:** Persistentes Schema, Sperre und Bereinigung sind nach Regression und Mehrverbindungstest konsistent. Migration 0006 ist in der V2-Testdatenbank installiert, getestet und noch **nicht als produktiver Wissensfreigabeworkflow** zu betrachten. Der vollständige Restore-Test des Pre-0006-Archivs bleibt offen; bisher wurde nur die Lesbarkeit des Archivs überprüft.
