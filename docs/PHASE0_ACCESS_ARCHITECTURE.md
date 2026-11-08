# Retro-RAG V2 – Rollen und Zugriff, Phase 0 (Stand 08.11.2026)

## Nachgewiesener Ist-Zustand auf Poseidon

- Docker-Container: `codeanalyse-postgres`, Image `pgvector/pgvector:pg16`.
- PostgreSQL `16.15`; pgvector `0.8.6`.
- Bestehende Datenbanken: `codeanalyse`, `nextcloud`, `postgres`, `retro_rag`, `retro_rag_test`.
- V2-Testdatenbank `retro_rag_v2_test` wurde neu angelegt, pgvector dort aktiviert.
- `0001_init.sql` **ausgeführt und geprüft**: 37 Tabellen, Migration 1, Schreibsperre `false`; Smoke-Test mit `ROLLBACK` bestanden.
- `0002_roles.sql` **ausgeführt und geprüft**: sieben `rag_v2_*`-NOLOGIN-Gruppen, Migration 2.
- Docker-Veröffentlichung: `127.0.0.1:5432` auf Poseidon.
- PostgreSQL im Container: `listen_addresses='*'`; HBA `/var/lib/postgresql/data/pg_hba.conf`.
- HBA: `local all all trust`, IPv4/IPv6-Loopback `trust`, sonst `scram-sha-256`.
- Datenbank-ACL: V1 `retro_rag` und `retro_rag_test` gewähren durch `PUBLIC` weiterhin `CONNECT`. **Keine Änderung an V1 vornehmen.**

## Zielarchitektur

| Berechtigungsgruppe | Vorbereitete Loginidentität | Zweck |
|---|---|---|
| `rag_v2_importer` | `rag_v2_importer_login` | Quellen, Chunks, Jobs, Vorschläge |
| `rag_v2_reviewer` | `rag_v2_reviewer_login` | Fakten-/Quellenreview |
| `rag_v2_inventory` | `rag_v2_inventory_login` | Bestätigte Inventaränderungen |
| `rag_v2_reader` | `rag_v2_reader_login` | Nur lesendes Retrieval |
| `rag_v2_lifecycle` | `rag_v2_lifecycle_login` | Dokumentstatus, Chunk-/Embedding-Löschung |
| `rag_v2_query_logger` | `rag_v2_query_logger_login` | Ausschließlich INSERT in query_log |
| `rag_v2_migrator` | `rag_v2_migrator_login` | Eigentümer der Objekte und Schema-Migrationen |

`0003_access.sql` erzeugt zunächst **nur deaktivierte Loginidentitäten**
(`NOLOGIN PASSWORD NULL`) und ordnet jeweils die passenden Gruppen zu.
Operative Gruppen dürfen per `INHERIT TRUE, SET FALSE` nicht in andere
Rollen wechseln; die Migration-Loginrolle erhält `SET TRUE` auf
`rag_v2_migrator`.

Die Migration überträgt Eigentum an Schema, Tabellen und Funktionen von
`0001` auf die Gruppe `rag_v2_migrator`. Das ist die Voraussetzung
für spätere DDL-Änderungen ohne Superuser. Bereits bestehende Gruppenrechte
aus `0002` bleiben erhalten. **Für neue Objekte müssen weitere Migrationen
ihre Rechte ausdrücklich vergeben**; pauschale Default-Grants sind
nicht vorgesehen.

## Wiederverwendung clusterweiter Rollen bei der späteren V2-Produktion

`0002_roles.sql` ist in der Testdatenbank bereits angewendet und erzeugt
Rollen auf Clusterebene. Ein zweiter unveränderter Aufruf in
`retro_rag_v2` würde an existierenden Rollen scheitern.
**Bereits angewendete Migrationsdateien werden nicht umgeschrieben.**

Deshalb enthält das Repository `db/bootstrap/0002_roles_existing_cluster.sql`:
Es darf ausschließlich in `retro_rag_v2` nach erfolgreicher `0001`
ausgeführt werden. Die sieben existierenden NOLOGIN-Gruppen werden auf
Sicherheit geprüft, dieselben Tabellenrechte wie aus `0002` vergeben
und die Versionsmarke 2 in **dieser** Datenbank protokolliert.
Dieses spezielle Bootstrap-SQL ist ein ausdrücklich dokumentierter
Alternativpfad, keine nachträgliche Änderung an `0002`.

`0003_access.sql` kann bestehende deaktivierte V2-Loginrollen ebenfalls
prüfen und erneut verwenden. **Vor dem Produktions-Bootstrap dürfen die
sieben Loginrollen noch nicht aktiviert worden sein.** Eine strikte
Trennung von V2-Test- und V2-Produktionsidentitäten ist vor produktivem
Betrieb gesondert umzusetzen; diese erste Version verwendet gemeinsame
Berechtigungsgruppen.

## Status Migration 0003

**Auf GitHub vorbereitet, noch NICHT auf Poseidon ausgeführt oder an PostgreSQL
getestet.** Daher auch noch nicht zur Übernahme nach `main` freigegeben.
Bereits angewendete Migrationen 0001/0002 bleiben unverändert.

## Ausführung ausschließlich in der V2-Testdatenbank

Voraussetzung: in `feature/phase0-database` arbeiten; aktuelles
Borg-/`pg_dump`-Backup vor Änderungen sichern. Zunächst kein Rollen-Login
und kein HBA-Neuladen.

```bash
cd ~/projects/retro-rag_v2
git branch --show-current
git pull --ff-only

docker exec codeanalyse-postgres \
  pg_dump -U codeanalyse -Fc -d retro_rag_v2_test \
  > "$HOME/retro_rag_v2_test_before_0003.dump"

docker exec codeanalyse-postgres \
  psql -X -U codeanalyse -d retro_rag_v2_test -c \
  "SELECT current_database(), max(version) FROM rag_v2.schema_migration;"

docker exec -i codeanalyse-postgres \
  psql -X -v ON_ERROR_STOP=1 -U codeanalyse -d retro_rag_v2_test \
  < db/migrations/0003_access.sql

docker exec -i codeanalyse-postgres \
  psql -X -v ON_ERROR_STOP=1 -U codeanalyse -d retro_rag_v2_test \
  < db/checks/verify_0003.sql
```

Erwartet: Version 3, alle Schema-/Objekteigentümer `rag_v2_migrator`,
sieben neue Rollen `NOLOGIN`, keine Superuserrechte, unverändert
`write_gate.writes_enabled = false`. Alle neuen Rollen sind clusterweit,
auch wenn die geänderten Objekte in V2 bleiben.

## Vor Aktivierung der Anmeldekonten – Pflicht

Die standardmäßige `PUBLIC CONNECT`-Berechtigung auf V1 darf
**nicht** durch globale `REVOKE`-Kommandos entfernt werden,
denn dies könnte V1-Clients beeinflussen.

Die expliziten V2-Logins brauchen stattdessen **vor ihrer Aktivierung**
gezielte `pg_hba.conf`-Regeln. Eine geprüfte Vorlage liegt unter
`deploy/postgresql/pg_hba_v2_example.conf`.

Regelprinzip: Für die sieben exakt benannten V2-Logins zuerst lokale
Socket-Verbindungen ablehnen; TCP nur zu V2-Datenbanken mit
`scram-sha-256` zulassen; Verbindungen zu allen anderen Datenbanken
vor den allgemeinen `trust`-/`scram`-Regeln explizit ablehnen.

Die Vorlage erlaubt zunächst ausschließlich Verbindungen über TCP-Loopback
**innerhalb des Containers**. Die tatsächlichen Docker-Netze für einen
späteren separaten V2-Dienst müssen erst ermittelt werden. Kein
`0.0.0.0/0`-Zugriff mit Passwort auf alle Datenbanken; die V2-Regeln
müssen vor den bestehenden generischen Einträgen stehen.

**Achtung:** Das Aktivieren/Ändern von `pg_hba.conf` ist ein eigener
administrativer Vorgang. Vorher die Datei sichern, Syntax und Trefferreihenfolge
prüfen, dann `SELECT pg_reload_conf();`, anschließend echte Verbindungs-
und Ablehnungstests durchführen. Diesen Schritt nicht automatisch vornehmen.

## Geheimnisse und Login-Aktivierung

Passwörter niemals ins Repository, in einen SQL-Migrationsparameter, die
Shell-History oder in ein GitHub-Issue schreiben. Nach überprüfter
HBA-Konfiguration können im interaktiven `psql` mit `\password ROLE`
Passwörter vergeben werden. Diese Anweisung fragt das Passwort verdeckt ab.
Danach kann eine Loginrolle kontrolliert mit `ALTER ROLE ... LOGIN`
aktiviert werden. Das betrifft ausschließlich die neuen V2-Rollen.

Beispiel *erst nach geprüftem HBA*, im interaktiven psql:

```sql
\password rag_v2_reader_login
ALTER ROLE rag_v2_reader_login LOGIN;
```

Gegenprobe für die Leserolle über TCP mit Passwort:
`psql -h 127.0.0.1 -U rag_v2_reader_login -d retro_rag_v2_test`
(innerhalb des Containers). Verbindungsversuche in
`retro_rag` und `retro_rag_test` müssen durch HBA scheitern.
Danach Funktionen und Tabellenrechte unter der echten Loginidentität
testen, nicht nur als Superuser.

## Grenzen der aktuellen Absicherung

- `PUBLIC CONNECT` auf V1 besteht unverändert; **noch keine vollständige
  V1-Isolation**, solange HBA für V2-Konten nicht implementiert ist.
- Docker-Host-Port ist Loopback, dennoch können andere Container über
  gemeinsame Docker-Netze direkt zugreifen.
- `write_gate` ist bislang ein persistentes Steuerflag, aber **keine
  flächendeckende Datenbank-Trigger-/RLS-Schreibsperre**; Anwendungen und
  Worker müssen die Freigabelogik technisch erzwingen.
- `rag_v2_migrator` ist durch Eigentümerschaft hochprivilegiert **innerhalb
  von V2**, jedoch kein Superuser und nicht für normale Anwendungen.
- Bestehende operative Rechte aus 0002 sind technisch granular, aber
  ersetzen weder Benutzerautorisierung noch Review-Freigabe im API-Layer.
- DDL für künftige neue Objekte muss mit der Eigentümergruppe ausgeführt
  werden (z. B. nach `SET ROLE rag_v2_migrator`), nicht als Superuser,
  damit Eigentümerschaft und explizite Grants konsistent bleiben.
- Kein automatisches Anwenden von SQL oder Netzwerkänderungen auf Poseidon
  über GitHub-Commits.

## Nächste Sicherheitsabnahmen

1. `0003_access.sql` in `retro_rag_v2_test` ausführen und `verify_0003.sql` bestehen.
2. Mindestens eine echte Migration als `rag_v2_migrator_login` mit
   separater Testdatei prüfen (nach Aktivierung, nur V2-Testdatenbank).
3. HBA-Regeln vor den bisherigen trust-Zeilen einordnen, zuerst mit
   V2-Testlogin testen; V1 und Nextcloud auf unveränderten Zugang prüfen.
4. Review- und Bestandsänderungen als echte Rollen testen.
5. Nur nach dieser Abnahme den Branch in `main` übernehmen.

## Durchführung: Reader-Authentifizierung (08.11.2026)

**Auf Poseidon vom Benutzer bestätigt; kein automatischer Zugriff durch GitHub:**

- `pg_hba.conf` im Container wurde unter `pg_hba.conf.pre-retro-v2` gesichert.
- Für `rag_v2_reader_login` wurden vor den allgemeinen `trust`-Regeln spezielle HBA-Einträge eingefügt: Unix-Socket `reject`; IPv4/IPv6-Loopback nur `retro_rag_v2_test` mit `scram-sha-256`; sonstiges IPv4/IPv6 `reject`.
- `pg_hba_file_rules` zeigte fünf Reader-Regeln ohne Fehler; `pg_reload_conf()` ergab `t`, erneute Prüfung ergab 0 Fehlerzeilen.
- Das Passwort wurde lokal mit `\\password rag_v2_reader_login` vergeben (nicht gespeichert); `ALTER ROLE rag_v2_reader_login LOGIN` war erfolgreich.
- Echter Verbindungsversuch per TCP IPv4 `127.0.0.1` mit Passwort auf `retro_rag_v2_test`: **erfolgreich**; `current_user = rag_v2_reader_login`.
- Dieselbe Rolle über IPv4-Loopback auf produktives `retro_rag`: **von pg_hba.conf ausdrücklich abgewiesen** (erwarteter Fehler).
- Effektive Rechte auf `rag_v2.document`: `SELECT = true`, `INSERT = false`, `UPDATE = false`, `DELETE = false`.

**Abgrenzung:** Bislang sind dies echte Login-Tests für den Reader **über TCP-IPv4-Loopback**. Noch nicht als echter Login getestet sind `retro_rag_test`, Unix-Socket, IPv6, Zugriffe über andere Docker-Netzwerkadressen und die sechs übrigen `*_login`-Rollen. Ein `has_database_privilege(..., 'CONNECT') = true` bei V1 bleibt wegen `PUBLIC` bestehen, auch wenn HBA die geprüfte Verbindung blockiert.

**Noch offen:** Die Repository-HBA-Vorlage beschreibt sieben Rollen, während auf Poseidon bisher nur die fünf Reader-Regeln aktiv eingebaut sind. Die weiteren Loginrollen bleiben deaktiviert; niemals die Vorlage unbesehen nochmals am Dateianfang einfügen. Bei Erweiterung vorher die bereits aktiven Regeln berücksichtigen und die exakte HBA-Reihenfolge testen.


## Zusätzliche Reader-Ablehnungstests (08.11.2026)

Vom Benutzer auf Poseidon ausgeführt und anhand der Terminalausgabe bestätigt:

- `psql -X -W -h 127.0.0.1 -U rag_v2_reader_login -d retro_rag_test`: `FATAL: pg_hba.conf rejects connection`. Neben der produktiven V1-Datenbank ist damit auch die **V1-Testdatenbank über IPv4-Loopback** für den Reader gesperrt.
- `psql -X -U rag_v2_reader_login -d retro_rag_v2_test` **ohne -h**: `FATAL: pg_hba.conf rejects connection for host "[local]"`. Die vorrangige `local ... reject`-Regel verhindert damit den Zugriff via Unix-Socket, obwohl für andere Benutzer weiterhin `local all all trust` gilt.
- Offene Gegenproben: direkte Docker-Netzwerkadresse, IPv6 und weitere sechs Loginrollen. Die allgemeinen Authentifizierungsregeln und V1-ACLs bleiben unverändert.

## Direkter Container-IP-Zugriff: Reader (08.11.2026)

Vom Benutzer ausgeführt: `docker exec -it codeanalyse-postgres psql -X -W -h 172.19.0.3 -U rag_v2_reader_login -d retro_rag_v2_test -c "SELECT current_user;"`.
Ergebnis: `FATAL: pg_hba.conf rejects connection for host "172.19.0.3"`.
Somit ist auch der direkte TCP-Zugriff **aus dem PostgreSQL-Container auf dessen eigene Adresse im Netzwerk `ai-network`** für den Reader abgewiesen worden.
Dies ist **kein** Nachweis eines Tests aus einem separaten Anwendungscontainer; dieser sowie IPv6 und die verbleibenden sechs Loginrollen sind noch offen. Die Konfiguration blieb unverändert.
