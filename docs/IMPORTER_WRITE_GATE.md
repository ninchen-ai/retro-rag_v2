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
