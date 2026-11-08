# Importer-Login und transaktionale Write-Gate-Prüfung

Stand 08.11.2026. Branch `fix/importer-write-gate`, aufbauend auf
`feat/import-webdav-staging`. **Keine automatische Anwendung auf Poseidon.**

## Ursache und Korrektur

`SELECT ... FOR SHARE` auf `rag_v2.write_gate` benötigt neben SELECT ein
UPDATE-Recht. `rag_v2_importer` besitzt zu Recht kein UPDATE auf diesem
Sicherheitsschalter. Migration `0004_import_write_gate.sql` erstellt
`rag_v2.assert_import_write_gate()` als `SECURITY DEFINER` mit Eigentümer
`rag_v2_migrator`. Die Funktion sperrt die Zeile mit `FOR SHARE` bis zum
Transaktionsende, verweigert bei geschlossenem Gate die Verarbeitung und
ist nur für `rag_v2_importer` ausführbar (kein PUBLIC EXECUTE).
Importer erhält **keine** UPDATE-, INSERT- oder DELETE-Rechte auf das Gate.

Die Funktion muss in derselben Datenbanktransaktion unmittelbar vor
Archivierung und Datenbank-DML aufgerufen werden. Sie ist eine
**Anwendungsschranke**, kein allgemeiner DB-Schreibschutz für beliebiges
Importer-SQL; eine umfassende Trigger-/RLS-Absicherung bleibt separat.

## Migration kontrolliert auf V2-Testdatenbank ausführen

Zunächst Branch auf Poseidon bewusst auschecken und Git-Status prüfen.
Die Migration ist für PostgreSQL 16 und Migration 0003 vorgesehen.
Sie muss als V2-Migrationsrolle laufen, **nicht als Importer**.
In der bestehenden Testumgebung ist das Migrator-Login noch deaktiviert;
daher zunächst den Zugang des dedizierten Migrators gemäß
`PHASE0_ACCESS_ARCHITECTURE.md` absichern und getrennt aktivieren.
Kein Superuser-DSN im Importprozess.

```bash
cd ~/projects/retro-rag_v2
git fetch origin
git switch fix/importer-write-gate
git status --short

# Migrationsdatei in den DB-Container kopieren:
docker cp db/migrations/0004_import_write_gate.sql \
  codeanalyse-postgres:/tmp/0004_import_write_gate.sql

# Dedizierten Migrator interaktiv anmelden (Passwort verdeckt):
docker exec -it codeanalyse-postgres \
  psql -X -W -h 127.0.0.1 -U rag_v2_migrator_login \
  -d retro_rag_v2_test -v ON_ERROR_STOP=1
```

In der interaktiven PostgreSQL-Sitzung:

```sql
SET ROLE rag_v2_migrator;
\i /tmp/0004_import_write_gate.sql
RESET ROLE;
```

Anschließend die Datei aus dem Container entfernen und den lesenden
Abnahmecheck ausführen (die bereits vorhandene administrative
Migrationsidentität darf ausschließlich für diesen Kontrollcheck
verwendet werden, niemals als Importer-DSN):

```bash
docker exec codeanalyse-postgres rm /tmp/0004_import_write_gate.sql
docker exec -i codeanalyse-postgres \
  psql -X -U codeanalyse -d retro_rag_v2_test \
  -v ON_ERROR_STOP=1 < db/checks/verify_0004.sql
```

## Importer-Login getrennt freischalten

1. Bereits vorhandene Reader-HBA-Regeln beibehalten. **Nicht** die gesamte
   Vorlage erneut einfügen. Neue Importer-Regeln müssen vor den allgemeinen
   Trust-Regeln stehen.
2. Für `rag_v2_importer_login`: Unix-Socket `reject`; für
   `retro_rag_v2_test` ausschließlich Loopback TCP IPv4/IPv6 mit
   `scram-sha-256`; alle anderen Adressen und Datenbanken `reject`.
   Keine pauschale Freigabe des kollidierenden `ai-network`-Netzes.
3. `pg_hba_file_rules` prüfen; Konfiguration neu laden und
   Verbindungsversuche (positiv und negativ) durchführen.
4. Erst danach am interaktiven administrativen Rollenverwaltungs-Zugang:
   `\password rag_v2_importer_login` und
   `ALTER ROLE rag_v2_importer_login LOGIN;`
   (Passwort niemals in Shell-History/Git/SQL-Dateien ablegen).
5. Als **echter** `rag_v2_importer_login` auf `retro_rag_v2_test`
   anmelden. `current_user`, `has_function_privilege` und
   `has_table_privilege` testen; V1-, Socket- und Container-IP-
   Verbindungen müssen abgewiesen werden.
6. Die erste Synchronisation nur ohne `--apply` ausführen.
   Bei geschlossenem Gate muss `--apply` vor jedem Archivschreiben
   scheitern. Die bewusste Gate-Freigabe ist eine **separate**
   Betreiberentscheidung nach Backup und Negativtests.

**Keine Aktivierung des Gates durch den Importer.**
Der Betreiber steuert `rag_v2.write_gate` über einen getrennten,
autorisierten Wartungsprozess.

## Abnahme

- `verify_0004.sql` erfolgreich, Sicherheitsfunktion gehört dem Migrator.
- Importer hat EXECUTE auf Funktion, nur SELECT auf Gate, keine Gate-DML.
- Fremde Rollen erhalten kein implizites PUBLIC EXECUTE.
- Geschlossenes Gate verhindert Import und Archivierung.
- Geöffnetes Gate erlaubt Staging in der V2-Testdatenbank mit echtem
  Importer-Login, ohne Daten in V1, Nextcloud oder Inventar zu verändern.
- Parallel laufendes Schließen des Gates wartet auf die laufende
  Importtransaktion; nach Commit/Rollback ist die Sperre wirksam.
- WebDAV-/Staging-Tests und Wiederholung unveränderter Datei erfolgreich.


## Betriebsnachweis auf Poseidon: Importer/Migrator und Migration 0004 (08.11.2026)

**Status: auf Poseidon ausgeführt und durch Terminalausgaben bestätigt.**
Die folgenden Angaben ergänzen historische Planungsstände weiter oben im Dokument;
ältere Formulierungen wie „noch nicht aktiviert“ sind keine Beschreibung des
aktuellen Zustands.

- PostgreSQL 16.15 im Container `codeanalyse-postgres`, Datenbank ausschließlich
  `retro_rag_v2_test`. Vor Migration 0004: `MAX(schema_migration.version)=3`;
  `write_gate.writes_enabled=false`, Grund
  „Initialisierung: Schreibfreigabe ausstehend“.
- `rag_v2_importer`, `rag_v2_migrator` sind weiterhin NOLOGIN-Gruppen.
  `rag_v2_importer_login` und `rag_v2_migrator_login` sind inzwischen
  mit **separaten, interaktiv vergebenen Passwörtern** aktiviert
  (`rolcanlogin=t`, `rolsuper=f`, keine CREATEDB-/CREATEROLE-Rechte laut
  vorangehender Rollenprüfung). Der Reader-Login war bereits zuvor aktiviert;
  die übrigen vier Loginrollen sind weiterhin deaktiviert.
- Vorherige HBA-Konfiguration wurde gesichert als
  `/var/lib/postgresql/data/pg_hba.conf.pre-importer-activation`
  (zusätzlich vorangehende Kopie `pg_hba.conf.pre-importer-v2`).
  Importer/Migrator-Regeln sind aktiv in Zeilen **125–129**:
  `local all ... reject`, TCP IPv4/IPv6 Loopback ausschließlich
  `retro_rag_v2_test` mit `scram-sha-256`, danach jeweils
  `host all ... reject` für IPv4/IPv6. Die Reader-Sonderregeln
  stehen unverändert in Zeilen 2–6; allgemeine `trust`-Regeln beginnen
  erst ab Zeile 131.
- `SELECT pg_reload_conf()` ergab `t` und
  `SELECT * FROM pg_hba_file_rules WHERE error IS NOT NULL` **0 Zeilen**.
- **Positive Real-Login-Tests:** Beide Rollen verbinden sich über
  `127.0.0.1` zur V2-Testdatenbank mit dem jeweils richtigen
  `current_user`.
- **Sechs erwartete HBA-Ablehnungen:** Für *beide* Logins wurden
  `retro_rag` über IPv4-Loopback, Unix-Socket auf V2-Test und
  direkte Container-IP `172.19.0.3` auf V2-Test mit
  `FATAL: pg_hba.conf rejects connection` abgewiesen.
  **Noch nicht getestet:** `retro_rag_test` für diese beiden Logins,
  IPv6-Realverbindungen sowie ein Zugriff aus einem separaten
  Anwendungscontainer. Das Docker-Netz `ai-network` wurde nicht geändert;
  dessen Subnetzkonflikt ist separat zu lösen.
- **Migration 0004:** Via `rag_v2_migrator_login`,
  `SET ROLE rag_v2_migrator` und
  `db/migrations/0004_import_write_gate.sql` erfolgreich angewendet;
  die Ausgabe enthielt `CREATE FUNCTION`, `GRANT`, `INSERT 0 1` und
  `COMMIT`. `db/checks/verify_0004.sql` lieferte
  `NOTICE: 0004: SECURITY DEFINER, EXECUTE, Gate-DML-Sperre geprüft`.
  Beim interaktiven Einfügen wurde `RESET ROLE;` einmal von `\\i`
  als überzähliges Argument interpretiert; die Migration war bereits
  committed, die psql-Sitzung wurde anschließend beendet.
- **Echter Berechtigungstest als Importer:**
  `has_function_privilege(..., 'EXECUTE')=t`,
  `has_table_privilege(..., 'rag_v2.write_gate', 'UPDATE')=f`;
  `SELECT rag_v2.assert_import_write_gate()` lieferte erwartungsgemäß
  `ERROR: V2-Schreibsperre ist geschlossen`.
  Damit ist die ursprüngliche `SELECT ... FOR SHARE`-/UPDATE-Kollision
  behoben **ohne** Gate-Schreibrecht für die Anwendung.
- **Python-Tests auf Poseidon:** `python -m pytest -q` mit
  **10 passed in 0.16s**, `git diff --check` ohne Befund (Branch
  `fix/importer-write-gate`). Ein vollständiger End-to-End-`--apply`-
  Test sowie ein Test des offenen Gates wurden **noch nicht** durchgeführt.

**Offene Abnahme:** kontrollierter Test bei explizit geöffnetem Gate,
transaktionale Konkurrenz zwischen Import und Gate-Schließung,
repräsentativer WebDAV-End-to-End-Test mit echtem Importer und
`--apply`, sowie gesonderte Negativtests für IPv6, V1-Testdatenbank und
separaten Container. Bis dahin Gate geschlossen lassen. Keine produktive
Freigabe, kein automatischer Vollimport und keine Änderung von V1-/Nextcloud-ACLs.
