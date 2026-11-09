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
