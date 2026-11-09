# PostgreSQL-Integrationstests: Dokumentidentität (Punkt B)

**Stand 09.11.2026. Status: Testcode ins Repository aufgenommen; Ausführung auf Poseidon noch nicht nachgewiesen.**

## Zweck und Testfälle

Die Suite `tests/test_document_identity_integration.py` verwendet den tatsächlichen Python-Staging-Code gegen `retro_rag_v2_test` (PostgreSQL 16, Migration 0005):

1. Dieselbe `oc:fileid` in zwei unterschiedlichen Instanzen mit verschiedenen Bytes erzeugt zwei unterschiedliche logische Dokumente.
2. Derselbe SHA-256 unter zwei bisher unbekannten Quellen erzeugt einen `document_identity`-Review im Status `proposed`, ohne die Dokumente zusammenzuführen.
3. Das neue, ungeprüfte Dokument bekommt keinen `processing_job`.
4. Wiederholtes Staging beider unveränderter Quellen ergibt `unchanged`, ohne zusätzliche Dokumente, Quellen, Versionen, Reviews oder Jobs.

**Abgrenzung:** Kein echter WebDAV-Transfer und keine Dateischreibtests; `archive_original` wird gezielt durch einen Stub ersetzt, der eine Test-URI liefert. Es werden die echten SQL-Abfragen und Transaktionen von `stage_file()` verwendet, aber mit der **Migratorrolle**, nicht mit der Importer-Loginrolle. Die Rollen-/HBA-Isolation des Importers ist daher **nicht** Gegenstand dieser Suite. Die vier Tests laufen nicht über eine vollwertige Review-UI.

## Schutz und Voraussetzungen

- ausschließlich `retro_rag_v2_test`, nicht V1 oder Produktion;
- nur `rag_v2_migrator_login`, mit `SET LOCAL ROLE rag_v2_migrator`;
- Migration 0005 muss als letzter Stand registriert sein;
- das reale `write_gate` muss **vor** dem Test geschlossen sein;
- jeder Test eröffnet eine **äußere uncommittete Transaktion**, setzt darin `writes_enabled=true` und führt `stage_file()` in Savepoints aus. **Im `finally` wird ausnahmslos `ROLLBACK` ausgeführt**; auch die Gate-Aktualisierung wird niemals committed;
- andere Transaktionen sehen die vorübergehend geänderte Gate-Zeile nicht als `true`. Das Gate ist während des Tests zeilenweise gesperrt: konkurrierende Änderungen können bis zum Rollback warten;
- Test-Dateiidentitäten sind zufällige UUIDs; keine Nextcloud-, Archiv- oder externen Daten werden verändert.

Die Tests werden **nicht** automatisch mit dem Standard-`pytest`-Lauf gegen eine reale DB ausgeführt, wenn die dedizierte Umgebungsvariable fehlt: sie melden dann `skipped`. Ein `skip` ist **kein erfolgreicher Integrationstest**.

## Ausführung auf Poseidon

Vom Branch `feat/document-identity-review` aus:

```bash
cd ~/projects/retro-rag_v2
git status --short
git pull --ff-only

# Zugangsdaten nicht in Kommandozeilen-History oder Git speichern.
read -r -s -p 'V2-Migrator-Passwort: ' PGPASSWORD
echo
export PGPASSWORD
export RETRO_V2_IDENTITY_TEST_DSN='host=127.0.0.1 port=5432 dbname=retro_rag_v2_test user=rag_v2_migrator_login'

python -m pytest -q tests/test_document_identity_integration.py -rs

unset RETRO_V2_IDENTITY_TEST_DSN PGPASSWORD
```

Nur bei **`4 passed` und `0 skipped`** ist diese Suite abgenommen. Fehler, Skip oder Hänger nicht als Erfolg werten. Danach unbedingt lesend kontrollieren:

```bash
docker exec codeanalyse-postgres psql -X -U codeanalyse -d retro_rag_v2_test -v ON_ERROR_STOP=1 -c "
SELECT writes_enabled, reason FROM rag_v2.write_gate;
SELECT
 (SELECT count(*) FROM rag_v2.document) AS documents,
 (SELECT count(*) FROM rag_v2.document_source) AS sources,
 (SELECT count(*) FROM rag_v2.document_version) AS versions,
 (SELECT count(*) FROM rag_v2.review_item) AS reviews,
 (SELECT count(*) FROM rag_v2.processing_job) AS jobs;"
```

Erwartung für den bisherigen leeren Testbestand: `writes_enabled=f`, alle fünf Zähler = 0. Falls andere Daten zwischenzeitlich eingetragen wurden, statt pauschal `0` mit dem Zustand **vor Testbeginn** vergleichen.

## Ergebnismatrix

| Prüfung | Status | Beleg |
|---|---|---|
| Vorheriger Unit-Lauf | **bestanden** | Betreiber-Ausgabe: `17 passed in 0.18s` |
| Migration 0005 / `verify_0005.sql` | **bestanden** | Betreiber-Ausgabe: `COMMIT`, `NOTICE`, `DO` |
| Echte Instanztrennung (PostgreSQL) | **ausstehend** | keine Testlauf-Ausgabe |
| Hash-Kollision und Review (PostgreSQL) | **ausstehend** | keine Testlauf-Ausgabe |
| Kein Job für Review-Dokument (PostgreSQL) | **ausstehend** | keine Testlauf-Ausgabe |
| Wiederholbarkeit ohne Duplikate (PostgreSQL) | **ausstehend** | keine Testlauf-Ausgabe |
| Rollback-/Write-Gate-Nachkontrolle | **ausstehend** | keine Testlauf-Ausgabe |

Erst nach Vorliegen der Terminalausgaben werden die Ergebnisse auf `bestanden` oder `fehlgeschlagen` aktualisiert. Es wurde **kein** automatischer Merge oder produktiver Rollout vorgenommen.

## Erster Integrationsversuch auf Poseidon: HBA-Ablehnung (09.11.2026)

Aus der vom Betreiber übermittelten Ausgabe:

```text
python -m pytest -q tests/test_document_identity_integration.py -rs
EEEE [100%]
psycopg.OperationalError: FATAL: pg_hba.conf rejects connection
for host "172.19.0.1", user "rag_v2_migrator_login",
database "retro_rag_v2_test", no encryption
4 errors in 0.17s
```

**Ergebnis:** Die vier Tests scheiterten beim Fixture-Verbindungsaufbau und haben die fachlichen Assertions **nicht erreicht**. Sie dürfen weder als bestanden noch als fachlich fehlgeschlagen gewertet werden. Der Repository-Stand dokumentiert das Docker-Netz `ai-network` mit Gateway `172.19.0.1`, PostgreSQL-Container `172.19.0.3` und die bewusst auf Container-Loopback begrenzten HBA-Regeln. Der Host-Port `127.0.0.1:5432` bewirkt keine Loopback-Quelladresse *innerhalb* des Containers.

**Keine HBA-Freigabe für `172.19.0.1` oder `172.19.0.0/16` erteilen.** Die geplante Docker-Netzbereinigung und die V1-Isolation bleiben unverändert.

### Wiederholung mit echter Python-Laufzeit und Container-Netzwerk-Namespace

Der folgende Weg nutzt **dieselbe lokale Python-venv**, denselben Testcode und dieselbe PostgreSQL-Instanz. `nsenter --net` ändert nur den Netzwerk-Namespace des gestarteten Testprozesses. Der `setpriv`-Aufruf gibt die privilegierte Ausführung vor Python wieder auf; keine Installation im DB-Container, kein zusätzliches Docker-Netz und keine HBA-Änderung. Auf Poseidon sind `sudo`, `nsenter`, `setpriv` und die Berechtigung für diesen Vorgang erforderlich. Das Testpasswort bleibt als Umgebungsvariable und wird nicht in Kommandoargumente kopiert.

```bash
cd ~/projects/retro-rag_v2
git pull --ff-only
read -r -s -p 'V2-Migrator-Passwort: ' PGPASSWORD; echo
export PGPASSWORD
export RETRO_V2_IDENTITY_TEST_DSN='host=127.0.0.1 port=5432 dbname=retro_rag_v2_test user=rag_v2_migrator_login'
container_pid="$(docker inspect -f '{{.State.Pid}}' codeanalyse-postgres)"
test "$container_pid" -gt 1 || { echo 'DB-Container nicht aktiv'; exit 1; }
sudo --preserve-env=PGPASSWORD,RETRO_V2_IDENTITY_TEST_DSN \
  nsenter --target "$container_pid" --net -- \
  setpriv --reuid "$(id -u)" --regid "$(id -g)" --init-groups \
  "$(pwd)/.venv/bin/python" -m pytest -q tests/test_document_identity_integration.py -rs
unset PGPASSWORD RETRO_V2_IDENTITY_TEST_DSN
```

**Vorsicht:** Nicht `docker exec` für Python voraussetzen; die PostgreSQL-Image-Laufzeit enthält nicht notwendigerweise Projekt-venv und Python-Abhängigkeiten. Den Netzwerk-Namespace nicht für andere Prozesse/Anwendungen unkontrolliert verwenden. Falls `sudo --preserve-env` lokal untersagt ist, nicht durch ein offenes HBA-Netz ersetzen.

Nach dem Test die im Abschnitt „Ausführung auf Poseidon“ dokumentierte lesende Kontrolle von `write_gate` und Tabellenzählern durchführen. Erst **4 passed**, **0 skipped** und ein nachweislich weiterhin geschlossenes Gate erfüllen die Abnahme.
