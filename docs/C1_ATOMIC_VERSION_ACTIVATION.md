# C1 – Atomare Aktivierung von Dokumentversionen

Stand: 09.11.2026. Entwicklungsbranch `feature/c1-atomic-version-activation`.
**Nur Code im GitHub-Branch vorbereitet. Noch keine Testausführung auf Poseidon, keine Migration,
kein Write-Gate geöffnet, keine V2-Daten verändert.**

## Ziel und Abgrenzung

`src/retro_rag/importer/activation.py` stellt `activate_version(conn, version_id,
superseded_days=30)` bereit. Die Staging-Pipeline bleibt unverändert: Ein neuer Import
erzeugt zunächst eine Version mit `state IS NULL`. Der spätere Verarbeitungs-Worker
muss Chunks, Embeddings und alle benötigten Jobschritte bereitstellen und
`processing_state='indexed'` sowie einen abgeschlossenen `document_import`-Job
setzen, **bevor** er die Aktivierungsfunktion aufruft.

Die Aktivierung verändert weder Quelloriginale noch Fakten/Review-Entscheidungen,
erzeugt keine Embeddings und ruft keine LLMs auf. Sie hat absichtlich keine
öffentliche CLI mit unkontrolliertem `--apply`.

## Sperren und Transaktion

1. Nur Testdatenbank `retro_rag_v2_test`, nur explizit offenes `write_gate`.
   Die Funktion `rag_v2.assert_import_write_gate()` hält ein `FOR SHARE`-Lock
   bis zum Transaktionsende.
2. `SELECT ... FOR UPDATE` auf `document` serialisiert konkurrierende
   Aktivierungen derselben logischen Dokument-ID. Die Zielversion wird **danach**
   erneut eingelesen und gesperrt.
3. Nur `available` und noch unveröffentlichte Versionen mit
   `processing_state='indexed'` und `archive_uri` dürfen wechseln.
4. Voraussetzungen: abgeschlossener `document_import`-Job, keine offenen/
   fehlgeschlagenen Schritte, abgeschlossener Archivschritt, mindestens ein Chunk,
   Embedding für jeden Chunk, kein offener `document_identity`-Review.
5. Die alte `active`-Version wird `superseded`, `superseded_at` und
   `archive_after` werden gesetzt. Danach erst wird die neue Version `active`.
   Die bestehende partielle Unique-Constraint erlaubt höchstens eine aktive Version.
6. Beide UPDATEs sind in **derselben** PostgreSQL-Transaktion. Bei Fehler
   führt die Exception zum Rollback des Aktivierungs-Savepoints bzw. der Transaktion;
   die bisherige Version bleibt unverändert.
7. Bereits aktive Zielversionen liefern `changed=False`; alte/archivierte/
   ersetzte Versionen werden nicht erneut aktiviert. Aktivierung älterer
   Versionsnummern gegenüber der aktuellen wird verweigert.

**Wichtige Grenze:** Das Write-Gate ist eine Anwendungsschranke, kein
universeller Trigger-Schutz vor beliebigen direkten SQL-Updates. Der spätere
Worker muss die gleiche Sperr-/Transaktionskonvention verwenden. Ein gegenwärtig
fehlender Verarbeitungs-Worker bedeutet, dass C1 derzeit nur mit synthetisch
vollständig indexierten Testdaten geprüft werden kann.

## Testplan

`tests/test_version_activation_integration.py` enthält sechs echte DB-Tests:

- Erfolgreiche Aktivierung, Vorgängerstatus und idempotenter Zweitaufruf.
- Unvollständige Verarbeitung belässt alte Version aktiv.
- Fehlendes Embedding verhindert Aktivierung.
- Ältere Versionsnummer kann neuere aktive nicht ersetzen.
- Künstlicher Fehler nach Aktivierung innerhalb eines Savepoints rollt
  beide Statusänderungen zurück.
- Offener Dokumentidentitätsreview blockiert Aktivierung.

Alle Tests benötigen `RETRO_V2_C1_TEST_DSN` mit dem dedizierten
`rag_v2_migrator_login`. Das Test-Fixture prüft auf Migrationsstand 5
und zunächst geschlossenes Gate, öffnet es nur **uncommitted in der äußeren
Transaktion** und führt am Ende zwingend `ROLLBACK` aus. Es benutzt keine
echten Originaldateien oder Nextcloud. Ohne DSN gibt es `skipped`, **nicht**
`passed`.

## Kontrollierte Ausführung auf Poseidon

Zunächst nur den Branch abrufen, ohne die Datenbank zu verändern:

```bash
cd ~/projects/retro-rag_v2
git status --short
git fetch origin
git switch feature/c1-atomic-version-activation
python -m pytest -q tests/test_markdown_import.py tests/test_webdav_staging.py tests/test_document_identity.py
```

Die echte PostgreSQL-Suite ist gesondert auszuführen. Weil die HBA-Policy
nur Container-Loopback zulässt, die bereits bewährte `nsenter`-Methode aus
`docs/DOCUMENT_IDENTITY_INTEGRATION_TESTS.md` verwenden, mit
`RETRO_V2_C1_TEST_DSN` statt `RETRO_V2_IDENTITY_TEST_DSN`:

```bash
read -r -s -p 'V2-Migrator-Passwort: ' PGPASSWORD; echo
export PGPASSWORD
export RETRO_V2_C1_TEST_DSN='host=127.0.0.1 port=5432 dbname=retro_rag_v2_test user=rag_v2_migrator_login'
container_pid="$(docker inspect -f '{{.State.Pid}}' codeanalyse-postgres)"
test "$container_pid" -gt 1 || { echo 'DB-Container nicht aktiv'; exit 1; }
sudo --preserve-env=PGPASSWORD,RETRO_V2_C1_TEST_DSN \
  nsenter --target "$container_pid" --net -- \
  setpriv --reuid "$(id -u)" --regid "$(id -g)" --init-groups \
  "$(pwd)/.venv/bin/python" -m pytest -q tests/test_version_activation_integration.py -rs
unset PGPASSWORD RETRO_V2_C1_TEST_DSN
```

Erwartung: **6 passed, 0 skipped**. Anschließend unabhängig als lesender
Adminzugang kontrollieren:

```sql
SELECT writes_enabled, reason FROM rag_v2.write_gate;
SELECT
 (SELECT count(*) FROM rag_v2.document) AS documents,
 (SELECT count(*) FROM rag_v2.document_version) AS versions,
 (SELECT count(*) FROM rag_v2.processing_job) AS jobs;
```

Vorherige Tabellenzähler und Gate-Status müssen mit den Werten **nach**
den Tests übereinstimmen. Kein Gate in einer eigenständig committeten
Transaktion öffnen.

## Weitere Abnahmegrenzen

- Konkurrenztest mit zwei separaten Verbindungen auf dieselbe Dokument-ID
  und echte Importer-Loginberechtigungen steht noch aus.
- Vollständigkeitskriterien und `processing_state` müssen beim späteren
  Worker-End-to-End-Test anhand realer Dokumente bestätigt werden.
- Kein Merge nach `main` vor erfolgreichem Test und Review.
- C2 (automatische Archivierung/Löschung) ist nicht Teil dieser Änderung.


## Abnahmenachtrag – PostgreSQL-Integrationstests am 09.11.2026

Betreiberseitig auf Poseidon bestätigt (dedizierter `rag_v2_migrator_login`,
`retro_rag_v2_test`, Python-venv im Netzwerk-Namespace des PostgreSQL-Containers):

```text
...... [100%]
6 passed in 0.16s
```

Anschließende **unabhängige** SQL-Kontrolle über `codeanalyse-postgres`:

```text
writes_enabled = f
reason = Parallelitätstest erfolgreich; Freigabe ausstehend
document = 0
document_version = 0
processing_job = 0
```

Damit sind die sechs C1-Testfälle und der Rollback der synthetischen Daten
bestätigt; die persistente Schreibsperre ist geschlossen geblieben.
**C1 ist noch nicht vollständig abgenommen:** Die tatsächliche Serialisierung
zweier unabhängig verbundener Aktivierer ist noch nicht nachgewiesen. Die
bestehende Test-Fixture öffnet das Gate nur innerhalb einer uncommitteten
äußeren Transaktion; ein zweiter Datenbank-Client kann dieses Gate nicht
als geöffnet lesen. Für einen belastbaren Konkurrenztest ist deshalb ein
separat isolierter Testaufbau erforderlich, ohne das Gate der bestehenden
V2-Testumgebung dauerhaft oder allgemein zu öffnen.


## Isolierter Konkurrenztest – vorbereitet, noch nicht ausgeführt

`tests/test_version_activation_concurrency.py` verwendet drei echte
Verbindungen: Aktivierer 1 hält nach Aktivierung von Version 2 seine
Dokument-Zeilensperre; Aktivierer 2 versucht gleichzeitig Version 3 zu
aktivieren. Eine dritte Verbindung fragt `pg_blocking_pids()` ab. Erst nach
nachgewiesener Blockierung committet Aktivierer 1. Erwartet werden
Version 1/2 `superseded`, Version 3 `active`, exakt eine aktive Version.

**Sicherheit:** Dieser Test committet absichtlich einen offenen Gate-Zustand
und synthetische Versionen – er darf **niemals** auf `codeanalyse-postgres`
oder einer anderen existierenden Datenbank laufen. Der Code verlangt zusätzlich
`cluster_name='retro-rag-v2-c1-isolated'` und den User `postgres`.
Nur ein separater Docker-Container ohne Netzanschluss ist zulässig.
Es wird ausschließlich dessen Schema kopiert, keine V2-Datensätze.

### Vorbereitung auf Poseidon

Voraussetzung: Arbeitsbranch `feature/c1-atomic-version-activation`,
Docker-Image `pgvector/pgvector:pg16` lokal verfügbar. Der neue Container
verwendet nur temporären RAM-Speicher und veröffentlicht **keinen** Port.
`docker stop` beendet ihn und entfernt den temporären Datenbestand.

```bash
cd ~/projects/retro-rag_v2
git fetch origin
git switch feature/c1-atomic-version-activation
git pull --ff-only

# Vorher nachprüfen, dass KEIN gleichnamiger Container existiert.
docker ps -a --filter name=retro-rag-v2-c1-isolated

docker run --rm -d \
  --name retro-rag-v2-c1-isolated \
  --network none \
  --tmpfs /var/lib/postgresql/data:rw,size=768m \
  -e POSTGRES_HOST_AUTH_METHOD=trust \
  pgvector/pgvector:pg16 \
  -c cluster_name=retro-rag-v2-c1-isolated

docker exec retro-rag-v2-c1-isolated pg_isready -U postgres
docker exec retro-rag-v2-c1-isolated \
  psql -X -U postgres -d postgres -v ON_ERROR_STOP=1 \
  -c 'CREATE DATABASE retro_rag_v2_test'
docker exec retro-rag-v2-c1-isolated \
  psql -X -U postgres -d retro_rag_v2_test -v ON_ERROR_STOP=1 \
  -c 'CREATE EXTENSION vector WITH SCHEMA public'

# Nur DDL/Schema aus dem bestehenden V2-Testcluster kopieren.
# Weder echte Dokumente noch eine Freigabe des bestehenden Gates übernehmen.
set -o pipefail
docker exec codeanalyse-postgres \
  pg_dump -U codeanalyse -d retro_rag_v2_test \
  --schema-only --schema=rag_v2 --no-owner --no-acl --format=custom \
  | docker exec -i retro-rag-v2-c1-isolated \
      pg_restore -U postgres -d retro_rag_v2_test \
      --no-owner --no-acl --exit-on-error

# Für die isolierte Kopie nur Migrationsmarker und geschlossenes Gate initialisieren.
docker exec retro-rag-v2-c1-isolated \
  psql -X -U postgres -d retro_rag_v2_test -v ON_ERROR_STOP=1 -c "
INSERT INTO rag_v2.schema_migration(version,description)
SELECT n, 'Isolierte C1-Schemakopie' FROM generate_series(1,5) AS n;
INSERT INTO rag_v2.write_gate(id,writes_enabled)
VALUES (true,false);
SELECT current_database(), current_setting('cluster_name');
SELECT writes_enabled FROM rag_v2.write_gate;"
```

**Wichtig:** Bei Fehlern in `pg_restore` oder beim SQL-Bootstrap abbrechen;
nicht auf den bestehenden PostgreSQL-Container ausweichen.

### Konkurrenztest ausführen

Wir verwenden erneut die bestehende Python-venv von Poseidon, aber ausschließlich
den Netzwerk-Namespace des **neuen** Testcontainers. Das Trust-Auth-Verfahren
ist durch `--network none` ausschließlich für dessen lokalen Namespace
erreichbar. Es wird kein Port zu Host oder LAN veröffentlicht.

```bash
isolated_pid="$(docker inspect -f '{{.State.Pid}}' retro-rag-v2-c1-isolated)"
test "$isolated_pid" -gt 1 || { echo 'Isolierter Container fehlt'; exit 1; }
export RETRO_V2_C1_ISOLATED_DSN='host=127.0.0.1 port=5432 dbname=retro_rag_v2_test user=postgres'
sudo --preserve-env=RETRO_V2_C1_ISOLATED_DSN \
  nsenter --target "$isolated_pid" --net -- \
  setpriv --reuid "$(id -u)" --regid "$(id -g)" --init-groups \
  "$(pwd)/.venv/bin/python" -m pytest -q \
  tests/test_version_activation_concurrency.py -rs
unset RETRO_V2_C1_ISOLATED_DSN
```

Erwartet: **1 passed, 0 skipped**. Zusätzlich muss die zweite Verbindung
in `pg_blocking_pids()` als tatsächlich blockiert beobachtet worden sein,
sonst schlägt der Test fehl.

### Isolation kontrollieren und aufräumen

```bash
docker exec codeanalyse-postgres \
  psql -X -U codeanalyse -d retro_rag_v2_test -v ON_ERROR_STOP=1 -c "
SELECT writes_enabled, reason FROM rag_v2.write_gate;
SELECT
 (SELECT count(*) FROM rag_v2.document) AS documents,
 (SELECT count(*) FROM rag_v2.document_version) AS versions,
 (SELECT count(*) FROM rag_v2.processing_job) AS jobs;"

docker stop retro-rag-v2-c1-isolated
```

Die bestehende V2-Testdatenbank muss unverändert sein und das Gate geschlossen.
**Status:** Repository-Testcode vorhanden, Ausführung und Abnahme auf Poseidon ausstehend.


## Abnahme – isolierter C1-Konkurrenztest am 09.11.2026

Die Betreiberin hat auf Poseidon den Test
`tests/test_version_activation_concurrency.py` mit der lokalen Python-venv
im Netzwerk-Namespace des separaten Containers
`retro-rag-v2-c1-isolated` ausgeführt. Vor dem Test wurden der isolierte
Clustername, die kopierte Schemaversion 5 und das geschlossene Gate geprüft.
Der Schematransfer aus `retro_rag_v2_test` per `pg_dump --schema-only`
und `pg_restore` endete mit Exit-Code 0.

**Bestätigte Terminalausgabe:**

```text
. [100%]
1 passed in 0.16s
```

Der Integrationstest erzwingt zwei unabhängige konkurrierende
Aktivierungen und beobachtet über eine dritte Verbindung einen
tatsächlichen Blockierer (`pg_blocking_pids()`). Nach Freigabe werden
die erwarteten drei Zustände geprüft: Version 1 und 2
`superseded`, Version 3 `active`, genau eine aktive Version.
Zusammen mit den sechs zuvor erfolgreich getesteten C1-Fällen sind
**7/7 C1-DB-Tests bestanden**. C1 ist hinsichtlich der vorgesehenen
atomaren Statuswechsel und des demonstrierten Konkurrenzfalls abgenommen;
ein späterer echter Import-Worker-End-to-End-Test bleibt offen.

**Noch erforderlich vor Abschluss der isolierten Testumgebung:**
Unabhängige Lesekontrolle des Write-Gates und der Tabellenzähler im
bestehenden Container `codeanalyse-postgres`, anschließend
`docker stop retro-rag-v2-c1-isolated`. Diese beiden Schritte sind
zum Zeitpunkt dieses Nachtrags noch nicht vom Betreiber bestätigt.


## Abschließende Betreiberkontrolle und Bereinigung (09.11.2026)

**Nach dem bestandenen Konkurrenztest unabhängig auf Poseidon geprüft:**

```text
writes_enabled | f
reason         | Parallelitätstest erfolgreich; Freigabe ausstehend

dokumente | versionen | jobs
----------+-----------+-----
0         | 0         | 0
```

Die Abfrage wurde ausdrücklich gegen den **bestehenden** Container
`codeanalyse-postgres` und die Datenbank `retro_rag_v2_test` durchgeführt,
nicht gegen die isolierte Testinstanz. Danach bestätigte der Betreiber:

```text
docker stop retro-rag-v2-c1-isolated
retro-rag-v2-c1-isolated
```

Der isolierte Container wurde mit `--rm` und temporärem `tmpfs`
gestartet. Der erfolgreiche Stop bestätigt die Beendigung des
Testcontainers; die Entfernung seiner temporären Daten folgt aus
dieser Containerkonfiguration. **C1 ist auf der Ebene der getesteten
atomaren Versionsaktivierung, Rollbacks und konkurrierenden Aktivierungen
abgenommen (7/7 DB-Tests).**

**Abgrenzung:** Ein vollständiger WebDAV-Import mit echtem `--apply`,
Produktivworker, realen Embeddings und ein Test der DB-/Dateisystem-
Konsistenz sind nicht Teil dieser C1-Abnahme. Die bestehende
Schreibfreigabe wurde nicht dauerhaft geöffnet. Kein Merge nach `main`
wurde durchgeführt.
