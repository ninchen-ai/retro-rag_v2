# Kontrollierter Einzeldatei-WebDAV-Apply und Fehlerfälle

Stand: 11.11.2026. Entwicklungsbranch: `feat/controlled-single-webdav-apply` (Basis: `integration/import-pipeline-2026-11-09`).

## Umfang und Sicherheitsgrenzen

- `--apply` ist nur mit **genau einer** `--source-key` (Nextcloud-`oc:fileid`) und einem zuvor verifizierten `--expected-sha256` möglich.
- Eine Datei-ID wird gegen die aktuelle WebDAV-Liste aufgelöst. Ein fehlender oder nicht eindeutiger Treffer ist ein harter Fehler.
- Der SHA-256 wird nach vollständigem Download, aber **vor** Archivierung und Datenbank-Staging geprüft.
- WebDAV-GET wird mit `If-Match` für einen vorhandenen ETag ausgeführt; HTTP 412, ETag-Wechsel, abgebrochene Verbindung, gekürzter oder zu großer Download schlagen fehl. Es gibt keinen automatischen Retry eines schreibenden Vorgangs.
- Der Download erfolgt in begrenzten Blöcken; die Gesamtdaten werden erst nach vollständigem Lesen zurückgegeben. Keine SQL-/Archivschreiboperation bei Downloadfehler.
- Originalarchiv: inhaltsadressierte temp-Datei, `fsync`, atomare Veröffentlichung über `os.link` (gleicher Dateisystempfad) und Verzeichnis-`fsync`. Bestehende Archivobjekte werden auf SHA-256 geprüft und nie überschrieben. Nach einem Prozessabsturz vor `os.link` kann eine `.pending-*`-Datei zurückbleiben, aber **kein teilweises endgültiges Archivobjekt**.
- Staging nutzt weiterhin `rag_v2.assert_import_write_gate()`, advisory locks und eine PostgreSQL-Transaktion. Ein SQL-Fehler rollt die DB-Änderungen zurück; eine bereits vollständig geschriebene Archivdatei kann als verwaistes, unveränderliches Artefakt verbleiben. Das ist kein verteilter DB/Dateisystem-Commit.
- Es gibt **keine** Versionenaktivierung, keinen Workerstart, keine Inventaränderung, kein Schreiben nach Nextcloud und keine V1-Schreiboperation.

## Testabnahme auf Poseidon (zunächst ohne Apply)

```bash
cd ~/projects/retro-rag_v2
git fetch origin
git switch --track origin/feat/controlled-single-webdav-apply
source .venv/bin/activate
python -m pip install -e '.[dev]'

python -m pytest -q tests/test_webdav_staging.py \
  tests/test_single_webdav_apply_failures.py \
  tests/test_single_apply_cli.py -rs
python -m ruff check src/retro_rag/importer/{webdav,staging,sync_cli}.py \
  tests/test_single_webdav_apply_failures.py tests/test_single_apply_cli.py
python -m pytest -q -rs
git diff --check
```

**Erfolg ist erst nach realer Testausgabe bestätigt.** Der bloße Commit der Tests zählt nicht als bestandener Test.

## Kontrollierter Ablauf mit genau einer Datei

1. PostgreSQL-Backup/Restore-Pfad prüfen; `retro_rag_v2_test` und Rolle `rag_v2_importer_login` verifizieren. Der aktuell dokumentierte Anfangszustand hat `writes_enabled=false` und leere Importtabellen. Der Istzustand ist unmittelbar vor dem Test erneut abzufragen.
2. WebDAV-Zugangsdaten ausschließlich über Umgebungsvariablen bzw. geschützte Sitzung setzen: `RETRO_V2_WEBDAV_URL`, `RETRO_V2_WEBDAV_USER`, `RETRO_V2_WEBDAV_APP_PASSWORD`, `RETRO_V2_NEXTCLOUD_INSTANCE_ID` und `RETRO_V2_DATABASE_DSN`. Nur das Test-DB-Importer-Login verwenden; keine Passwörter protokollieren.
3. **Gate geschlossen lassen**, zunächst lesend die Datei-ID ermitteln und anschließend nur diese Datei planen:

```bash
python -m retro_rag.importer.sync_cli --source-key '<NEXTCLOUD_FILEID>'
```

   Die Ausgabe enthält `sha256=<64 Hex-Zeichen>`. Datei, Hash und geplante Aktion dokumentieren.
4. Erst nach expliziter Betreiberfreigabe in einer separaten Migrator-Sitzung das **Test-Gate** zeitlich begrenzt öffnen. Niemals dem Importer Rechte zur Gate-Änderung geben. Während des offenen Gates keine anderen Importer-Prozesse starten.
5. Eine einzige Datei stagen (keine weiteren Importdateien):

```bash
python -m retro_rag.importer.sync_cli \
  --apply --source-key '<NEXTCLOUD_FILEID>' \
  --expected-sha256 '<64-STELLIGER-SHA256-AUS-PLANUNG>' \
  --archive-root '/ABSOLUTER/GEPRUEFTER/ARCHIVPFAD'
```

6. **Unmittelbar** mit dem Migrator das Gate wieder schließen, auch bei Fehlern. Abschlusskontrolle als separater lesender DB-Zugang: `SELECT writes_enabled, reason FROM rag_v2.write_gate;` sowie Zählung der fünf Tabellen `document`, `document_source`, `document_version`, `processing_job`, `review_item`. Archivhash prüfen. Ein zweiter identischer Apply soll `unchanged` zurückliefern und keine neue Version erzeugen. Bei Fehler niemals blind erneut freigeben: erst Datenbank und Archivzustand prüfen.

## Weitere Fehlerfälle und Grenzen

| Fall | Erwartung |
| --- | --- |
| Timeout/Verbindungsabbruch vor vollständigem GET | Keine Archiv-/DB-Schreiboperation |
| HTTP 412 oder geänderter ETag | Abbruch vor Staging |
| Datei zwischen Vorschau und Apply geändert | SHA-256-Abweichung; kein Staging |
| Zu großer/verkürzter Download | Abbruch; kein Staging |
| Prozessabsturz beim Archivschreiben | Kein teilweise veröffentlichtes Zielobjekt; möglicherweise `.pending-*` |
| Prozessabsturz nach Archivierung, vor DB-Commit | DB-Rollback; eventuell verwaiste vollständige Archivdatei |
| Prozessabsturz nach DB-Commit, vor CLI-Ausgabe | Commitstatus zunächst ungewiss; read-only DB-Abgleich und danach idempotenter Re-Apply |
| Gate geschlossen | `assert_import_write_gate()` lehnt Staging ab; kein Archivschreiben |
| Wiederholung gleicher Datei/gleicher Hash | `unchanged`, keine neue Version |
| Parallele Writer für gleiche Quelle | Bestehende advisory locks/DB-Sperren; tatsächliche DB-Parallelität separat prüfen |

**Abnahmestatus (11.11.2026):** Auf Poseidon wurden zweimal die 27 gezielt ausgewählten Unit-Tests erfolgreich ausgeführt (`27 passed in 0.13s` bzw. `27 passed in 0.12s`). Der erste Ruff-Lauf meldete acht Beanstandungen (Importreihenfolge, ungenutzter Import, SIM117); nach Korrektur meldete der zweite Ruff-Lauf ausschließlich `I001` wegen einer überzähligen Leerzeile nach den Imports in `webdav.py`. Diese letzte Stelle wurde mit Commit `69400e1` korrigiert, **aber noch nicht erneut auf Poseidon geprüft**. `git diff --check` lieferte beim zweiten Testlauf keine Ausgabe. Ein vollständiger Suite-Lauf, realer Nextcloud-/PostgreSQL-End-to-End-Apply, kontrollierte Gate-Freigabe, realer Crash-/Netzwerktest und unabhängige DB-Nachkontrolle sind weiterhin offen. Keine Produktionsfreigabe.

## Vollständige lokale Abnahme auf Poseidon – 11.11.2026

Betreiberseitig nach Fast-forward auf Commit `4d8962c`:

```text
43 passed, 11 skipped in 0.20s
All checks passed!
```

Die vollständige `python -m pytest -q -rs`-Suite lieferte **43 bestandene** und **11 übersprungene** Tests, **0 Fehltests**. `ruff check` der drei betroffenen Importer-Module und zweier neuer Testdateien war erfolgreich; `git diff --check` und `git status --short` ohne Ausgabe (sauberer Arbeitsbaum). Die zuvor offene Ruff-I001-Nachprüfung ist damit erledigt.

Die 11 auf diesem Branch **noch nicht ausgeführten** DB-Integrationstests entfallen auf vier Dokumentidentitäts-, sechs C1-Versionenaktivierungs- und einen isolierten C1-Konkurrenztest. Frühere Abnahmen auf `integration/import-pipeline-2026-11-09` gelten nicht als neue Feature-Branch-Abnahme.

Weiter offen: echter WebDAV-Read-only-Planungslauf, alle elf DB-Tests auf diesem Branch, kontrollierter Einzeldatei-Apply mit echtem Importer und expliziter Gate-Freigabe sowie Wiederanlauf-/Crash- und unabhängige Nachkontrolle. Das Gate wird durch diesen Nachtrag nicht verändert.

## Echter WebDAV-Einzelabruf und unabhängige Datenbankkontrolle – 11.11.2026

Betreiberseitig auf Poseidon bestätigt:

- WebDAV-Listing mit Nextcloud-`oc:fileid`, Größen und ETags erfolgreich.
- Exakt eine Datei ausgewählt: `test-mainboard.md`, `source_key=480`, `byte_size=371`, ETag `"64dc6d1675b067a81554c913a48685ea"`.
- Konditionaler Einzeldatei-GET über `WebDAV.download(..., max_bytes=1_000_000)` erfolgreich: 371 Bytes, SHA-256 `70e1b0ce4dc3d7cc3497763c4e907f1f3df65843cb3b5cef7c38bf8ee66efab6`.
- Unabhängige lesende DB-Kontrolle via `docker exec codeanalyse-postgres psql -X -U codeanalyse -d retro_rag_v2_test`:
  `writes_enabled=f`, Grund `Parallelitätstest erfolgreich; Freigabe ausstehend`.
  Tabellenzähler: `document=0`, `document_source=0`, `document_version=0`,
  `processing_job=0`, `review_item=0`.
- Das ist ein echter Read-only-WebDAV-Nachweis, **noch kein** `sync_cli --source-key`-Planungslauf mit dem Importer-Login, kein `--apply`, keine Gate-Freigabe und kein realer Crash-Test.

## Importer-Login und SQL-Vorplanung – 11.11.2026

Vom Betreiber auf Poseidon via `docker exec -it codeanalyse-postgres psql -X -W -h 127.0.0.1 -U rag_v2_importer_login -d retro_rag_v2_test` ausgeführt:

```text
BEGIN
current_user       = rag_v2_importer_login
current_database   = retro_rag_v2_test
planned_action     = new
COMMIT
```

Die `BEGIN READ ONLY`-Abfrage prüfte zunächst, ob die ausgewählte Nextcloud-Quelle mit `source_instance='poseidon-nextcloud'`, `source_key='480'` vorhanden ist und ob der zuvor verifizierte SHA-256 bereits bei einer anderen Quelle existiert. Beide Prüfungen waren negativ; die erwartete Aktion ist `new`. Keine DB-Änderung. **Ein erfolgreicher `plan_file()`-Aufruf mit der Anwendungsrolle ist damit noch nicht nachgewiesen.**

**Vor dem schreibenden End-to-End-Test:** Die aktuelle `sync_cli` setzt gleichzeitige Erreichbarkeit von Nextcloud-WebDAV und der V2-Datenbank in einem Prozess voraus. Der WebDAV-URL-Loopback `127.0.0.1:8080` wurde auf dem Host getestet; der Importer-Login hingegen im PostgreSQL-Container auf `127.0.0.1:5432` (gesonderte HBA-Regeln). Ein gemeinsamer, sicherer Netzwerkpfad der Anwendung ist noch zu ermitteln; keinesfalls Datenbank-HBA oder Docker-Portfreigaben für den Test pauschal öffnen. Backup, geprüftes Archivverzeichnis und isolierter Anwendungspfad müssen vor `--apply` nachgewiesen werden. Das Write-Gate bleibt geschlossen.

## Backup-/Netzwerk-Vorprüfung auf Poseidon – 11.11.2026

Betreiberseitig zurückgemeldet:

- `docker exec codeanalyse-postgres pg_dump -U codeanalyse -Fc -d retro_rag_v2_test > ~/backups/retro-rag-v2/pre-single-apply.dump` wurde ausgeführt. Der Pfad wurde mit `chmod 600` geschützt. **Erfolgreiche Backup-Erzeugung und Vollständigkeit noch nicht explizit anhand von Exitcode/Archivprüfung bestätigt.**
- Die Host-Prüfung `pg_restore -l ...` schlug mit `-bash: pg_restore: Kommando nicht gefunden` fehl: `pg_restore` ist **auf dem Host** nicht installiert. Die Archivprüfung wird deshalb mit `docker exec -i codeanalyse-postgres pg_restore -l` und vollständig lesendem `pg_restore -f /dev/null` über stdin fortgesetzt. Kein Restore durchgeführt.
- `df -h "$HOME"`: Root-Dateisystem `/dev/nvme0n1p2`, 221 GiB laut Anzeige, 176 GiB genutzt, 34 GiB frei, 85 % Auslastung.
- `findmnt -T ~/projects/retro-rag_v2`: `/` auf ext4, `rw,relatime,errors=remount-ro`.
- `ss -ltn`: Host-TCP-Port `127.0.0.1:5432` lauscht; Nextcloud-Frontend `:8080` auf `0.0.0.0` und `[::]`. **Listener-Nachweis ist kein Nachweis einer erfolgreichen Host-Anmeldung als `rag_v2_importer_login`** (HBA/Portforwarding). Deshalb vor der CLI eine echte rein lesende psycopg-Verbindung vom Host testen.
- Kein Write-Gate geöffnet, keine migrations- oder archivseitigen Änderungen bestätigt. Dauerhaften Archivpfad gesondert auswählen; System-NVMe bereits 85 % belegt.

## Abgleich mit Poseidons vorhandener Borg-Strategie (11.11.2026)

Die Host-Infrastruktur ist unter `ninchen-ai/homelab-ai-infrastructure` dokumentiert:
`docs/backup.md`, `scripts/backup/backup.sh`, `docs/storage.md` und
`docs/servers/poseidon.md`. Verbindlicher V2-Originalarchivpfad auf der
Toshiba-HDD: **`/data/retro-rag/v2/originals`** (bei Einrichtung als
`nina:nina`, 0700 bestätigt); daneben `staging/` und `quarantine/`.
Der Test-Apply darf nicht auf ein neues Archiv unter der bereits stark belegten
System-NVMe umgelenkt werden.

Das bestehende Borg-Backup arbeitet mit rotierenden, eigenständigen
BORG-W1…W4-/M1-/M2-Repositories und erstellt vor dem Borg-Lauf
`pg_dump -Fc` für `codeanalyse`, `nextcloud` und V1-`retro_rag`.
**Der tatsächlich versionierte Backup-Skriptstand enthält noch keinen Dump
von `retro_rag_v2_test` und keine eigene `borg create`-Quelle für
`/data/retro-rag/v2/originals`.** Die bloße Existenz des Archivs auf
`/data` bedeutet daher noch keine externe Sicherung. Die bisherige
Einzeldatei-Restore-Abnahme ist kein Nachweis für einen V2-DB-Restore.

Empfohlene separate Infrastrukturänderung mit eigener Prüfung:
1. `retro_rag_v2_test` als zusätzlichen konsistenten Custom-Format-Dump
   nach `/data/backup-staging/postgres/retro_rag_v2_test.dump` aufnehmen
   und wie vorhandene Dumps mit `pg_restore -l` validieren.
2. `/data/retro-rag/v2/originals` als eigene Quelle in `borg create`
   aufnehmen; `staging` und `quarantine` gesondert bewerten.
3. Vor Borg-Rotation den passenden Restore-Pfad in eine **separate**
   Testdatenbank prüfen und V2-Originale aus Borg bytegleich zurückholen.
4. Den neuen Umfang mit `--no-shutdown` auf einem eingelegten, geprüften
   Backupmedium testen; danach prüfen, dass das Medium ausgehängt ist.
5. Bei späterer produktiver Datenbank `retro_rag_v2` deren Backup
   getrennt von der Testdatenbank planen. **Nicht** V1 überschreiben.

Das bestehende Infrastruktur-Backupskript wird durch diese Dokumentation
**nicht** geändert. Vor dem kontrollierten `--apply` bleibt ein lokal
validierter, separater `pg_dump`-Sicherungsstand notwendig; eine
vollständige Borg-V2-Abnahme ist weiterhin offen. Gate bleibt geschlossen.

## Validierung des lokalen V2-Dumps und Originalarchivs – 11.11.2026

Aus der auf Poseidon vom Betreiber übermittelten Terminalausgabe:

- Backup `/home/nina/backups/retro-rag-v2/pre-single-apply.dump`: `-rw-------`, Eigentümer `nina:nina`, Größe **123K**, Zeitstempel 11.11.2026 13:20 (Host-Anzeige). `pg_restore -l` im PostgreSQL-Container: Custom-Format 1.15, gzip, **268 TOC-Einträge**, Quelle `retro_rag_v2_test`, `pg_dump` und PostgreSQL jeweils **16.15**.
- Vollständiges lesendes Durchlaufen mit `docker exec -i codeanalyse-postgres pg_restore -f /dev/null < "$BACKUP"` ergab **`BACKUP-LESETEST ERFOLGREICH`**. Dies ist **kein vollständiger Restore** in eine getrennte Testdatenbank.
- `findmnt -T /data/retro-rag/v2/originals`: **`/dev/sda1`, ext4, `rw,noatime`, Mountpoint `/data`**.
- `df -h`: 916G gesamt, 3,6G belegt, **866G frei**, 1 % Nutzung.
- `stat`: `nina:nina`, Modus **0700**; `test -w` ergab **`ARCHIV BESCHREIBBAR`**, ohne eine Testdatei anzulegen.
- Lokaler Vor-Apply-Dump und unveränderliches Originalarchiv sind damit für den **kontrollierten Einzeldatei-Test** vorbereitet. Die bestehende Borg-Rotation sichert **V2-DB und V2-Originalarchiv noch nicht nachweislich**, und ein echter V2-Restore bleibt ausständig.
- Weiter offen: echte `rag_v2_importer_login`-Verbindung **vom Host** (Docker-Port-Weiterleitung/HBA), `plan_file()`-Aufruf, Integrationstests des Feature-Branches und kontrollierter `--apply`. Schreibsperre bleibt geschlossen.

## Erfolgreicher Importer-Loopback-Test im PostgreSQL-Netz-Namespace (11.11.2026)

Auf Poseidon hat die Betreiberin mittels
`docker inspect -f '{{.State.Pid}}' codeanalyse-postgres`,
`sudo nsenter --target "$PG_PID" --net -- setpriv --reuid "$(id -u)" --regid "$(id -g)" --init-groups`
und der vorhandenen `.venv/bin/python` eine echte `psycopg`-Verbindung als
`rag_v2_importer_login` hergestellt. Ergebnis:

```text
('rag_v2_importer_login', 'retro_rag_v2_test', IPv4Address('127.0.0.1'))
```

Damit ist der notwendige PostgreSQL-Zugriff per TCP-Loopback **ohne HBA-Änderung** nachgewiesen. Die Anwendungs-Python-Umgebung lief als unprivilegierter Nutzer im Netzwerk-Namespace des Datenbankcontainers; die Datenbankaktion war ausschließlich ein `SELECT`. Kein `--apply`, keine Gate-Freigabe und keine DB-Änderungen.

**Noch offen:** Der konfigurierte WebDAV-Endpunkt `http://127.0.0.1:8080` zeigt in diesem Namespace nicht auf den Host-Loopback. Die gemeinsame Erreichbarkeit von WebDAV und PostgreSQL in der CLI ist daher **noch nicht** belegt. HTTP-Basic-Auth nicht ungeschützt auf eine Docker-Bridge-Adresse umstellen. Vor einem echten Import entweder einen abgesicherten End-to-End-Zugang nachweisen oder den WebDAV-Abruf auf dem Host und das transaktionale Staging in der DB-Netz-Namespace technisch sauber trennen.

**Hinweis:** Ein hartes Ausschalten der gesamten Maschine kann selbst nach `fsync` je nach Storage-/Controller-Cache zusätzliche Risiken haben. Das hier beschriebene Verfahren behandelt Anwendungskonflikte und Prozessabbrüche; ein Restore-Test bleibt notwendig.
