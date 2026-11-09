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
