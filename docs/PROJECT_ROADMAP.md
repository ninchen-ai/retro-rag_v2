# Retro-RAG V2 – Projekt-Roadmap und offene Aufgaben

**Stand:** 21.11.2026 · **Integrationsbranch:** `integration/import-pipeline-2026-11-09`  
**Geltung:** Universelle Wissensplattform, bestehende Importpipeline und technische Abschlussarbeiten.  
**Statusregel:** `Erledigt` = nachgewiesen im genannten Scope; `Teilweise` = Grundlage vorhanden, Akzeptanzkriterien nicht vollständig; `Offen` = nächste Umsetzung/Abnahme ausstehend. Ein freigegebenes Architekturziel ist keine implementierte Funktion.

Diese Datei ist der **zentrale Aufgabenindex**. Detaillierte Architektur- und Testnachweise bleiben in den verlinkten Quelldokumenten. Die IDs `A-01` bis `A-15` entsprechen der gemeinsamen Planung; die Kapitel **A** und **B** bewahren diese IDs ausdrücklich. Technische Abschlussarbeiten erhalten `C-xx`, Importpipeline-Stufen `IP-xx`.

## Gesicherter Ausgangsstand

- Alle zwölf [Architekturziele 3.0](ARCHITECTURE_GOALS.md) sowie vier [Architekturentscheidungen](ARCHITECTURE_DECISIONS.md) sind **fachlich freigegeben**.
- Migration `0006` ist in der bestehenden **Testdatenbank** `retro_rag_v2_test` dauerhaft installiert: **43 Tabellen, 15 Entitätstypen, geschlossenes Write-Gate**, nach Testbereinigung jeweils null Themen, Beziehungen und Wissensvorschläge. Keine produktive Wissensfreigabe.
- Nachweise: [0006-Testprotokoll](UNIVERSAL_KNOWLEDGE_SCHEMA_0006.md), [Schema-Status](../db/SCHEMA_CURRENT.md), [real exportierter Snapshot](../db/schema/retro_rag_v2_test.sql); 24 reguläre Pytest-Tests, separat 10 rollback-only DB-Integrationstests, eigene 0006-Mehrverbindungstests, Rollen- und SQL-Prüfungen bestanden.
- Pre-0006-Dump auf Poseidon erfolgreich **innerhalb des bestehenden Clusters** in eine temporäre Datenbank wiederhergestellt (Version 5, 37 Tabellen, Gate geschlossen). Kein vollständiger Disaster-Recovery-Test eines neuen Clusters.
- Migration `0006` und die begleitenden Prüf-/Dokumentationsänderungen wurden über [PR #10](https://github.com/ninchen-ai/retro-rag_v2/pull/10) am **21.11.2026** nach `integration/import-pipeline-2026-11-09` gemergt (Merge-Commit `4c09576`). **Nicht** nach `main` übernommen; ältere PDF/OCR/WebDAV-Branches/PRs sind weiterhin getrennt.

## A. Offene Punkte des universellen Wissensmodells

| ID | Aufgabe | Priorität | Status | Nächster Schritt / Akzeptanzkriterium | Abhängigkeit |
|---|---|---|---|---|---|
| **A-01** | Universelle Entitätstypen | Hoch | **Teilweise** – `entity_type` mit Grundkatalog in 0006 | Typdefinitions-/Alias- und Identitätsregeln für neue Domänen spezifizieren, mehrdeutige Bezeichnungen und Dubletten testen | AZ-01, AZ-08; 0006 |
| **A-02** | Universelle Eigenschaften | Hoch | **Offen** – vorhandenes `property` ist auf bisherige Werttypen begrenzt | Boolesche Werte, Datum, Zeitstempel, Entitätsverweise, Typprüfung und Migrationsverträglichkeit spezifizieren/implementieren | A-01; **Kandidat für 0007** |
| **A-03** | Strukturierte Fakten | Hoch | **Offen** – bestehendes `fact` noch unverändert | Fachneutrale Faktenwerte inkl. Validierung, Status, Versionierung und Rückwärtskompatibilität nachweisbar unterstützen | A-02, A-05; **Kandidat für 0007** |
| **A-04** | Zeitliche Gültigkeit | Hoch | **Teilweise** – Beziehungen haben optionale Gültigkeitsfelder | Gültigkeitszeit, Erfassungszeit und Quellzeit für Fakten/Beziehungen unterscheiden; Zeitachsen/Änderungsfälle testen | A-03, A-06 |
| **A-05** | Provenienz und Nachweise | Hoch | **Teilweise** – bestehende `evidence` und neue Relation-Belege vorhanden | Quellenarten, Messungen, Fundstellen, Transformations-/Modell-/Regelversionen und Agentenläufe nachvollziehbar referenzieren; Belegqualität prüfen | A-03, A-10 |
| **A-06** | Universelle Beziehungen | Hoch | **Teilweise** – `entity_relation`, Belege und bestätigte Sicht in 0006 | Kontrollierter Relationstyp-Katalog, Richtungssemantik, Kontext und fachliche Freigabe-/Änderungsregeln; Fail-closed beibehalten | A-01, A-05, A-11 |
| **A-07** | Themen und Sammlungen | Mittel | **Teilweise** – Themenhierarchie/Zuordnungstabellen vorhanden, Zyklus-Parallelitätstest PASS | Dokument- und Objektzuordnung, Mehrfachzuordnung, Umbau- und Löschregeln definieren und testen | A-01, Dokumentidentität |
| **A-08** | Widersprüchliche Aussagen | Hoch | **Offen** | Konflikte erkennen, konkurrierende Fakten unverändert erhalten, unterschiedliche Kontexte/Gültigkeiten mit Belegen anzeigen und testen | A-03–A-06, A-15 |

## B. Offene Punkte der Wissensverarbeitung

| ID | Aufgabe | Priorität | Status | Nächster Schritt / Akzeptanzkriterium | Abhängigkeit |
|---|---|---|---|---|---|
| **A-09** | Selektive Extraktion | Hoch | **Offen** – fachlich für Regelmodell B entschieden | Autorisierte, versionierte Extraktionsprofile, Aktivierungsbedingungen und separate Jobs; Indexierung darf ohne Extraktion funktionieren | IP-E/F, A-02–A-05 |
| **A-10** | Wissensvorschläge | Hoch | **Teilweise** – `knowledge_proposal` vorhanden, geschützt und unveränderlich | Validiertes Payload-Schema, Provenienz, Idempotenz sowie Anbindung an `review_item`; jeder Agentenvorschlag zunächst unbestätigt | 0006, A-05, A-09 |
| **A-11** | Regelabhängige Freigabe | Hoch | **Offen** – fachlich Regelvariante B; automatisches Akzeptieren in 0006 gesperrt | Autorisierte versionierte Policies, deterministische Prüfungen, Quellen-/Konfliktprüfung, unabhängiger Entscheider, Review-Fallback und Audit; Negativ-/Manipulationstests | A-05, A-08, A-10; niemals vor Review-Sicherheit |
| **A-12** | Agentenarchitektur | Mittel | **Offen** – fachlich unbestätigter Vorschlagsbereich freigegeben | Begrenzte Agenten-API, Lauf-/Eingangsquellen-Provenienz, Ressourcen- und Laufzeitlimits; keine Selbstfreigabe oder Policy-Änderung | A-10, A-11 |
| **A-13** | Vorschlagslebenszyklus | Mittel | **Offen** | Duplikate, Wiedervorlagen, Ablehnung, Archivierung, Aufbewahrung und historisierte Entscheidungen mit Tests | A-10, A-11 |
| **A-14** | Universelles Retrieval | Hoch | **Teilweise** – SQL/pgvector- und Dokumentgrundlage existiert; sicherer Gesamtpfad fehlt | SQL, Volltext und Vektorsuche kombinieren; bestätigte Fakten, ungeprüfte Quellen und Vorschläge strikt getrennt markieren/filtern; Berechtigungs- und Halluzinationstests | A-03, A-06, A-10, A-11 |
| **A-15** | Kontextabhängige Bewertung | Mittel | **Offen** | Vergleichskriterien, Test- und Ergebnisbelege, Alternativen, Kontext und Unsicherheit prüfbar speichern/anzeigen | A-04, A-05, A-08, A-14 |

**Technische Reihenfolge:** Für `0007` zuerst einen **Entwurf** zu A-01 bis A-06 (vor allem Eigenschaften, Fakten und Belege) mit Rückwärtskompatibilität und Migrations-/Rollback-Tests vorlegen. **Keine** automatische Wissensfreigabe zusammen mit der Schemaerweiterung aktivieren. Danach Review/Policy und Extraktion getrennt entwickeln. A-07/A-08 sind eigenständige Abnahmen; die Zuordnung zu einer konkreten Migration ist noch zu entscheiden.

## C. Technische Abschlussarbeiten

| ID | Aufgabe | Status am 20.11.2026 | Restarbeit und Akzeptanzkriterium | Abhängigkeit/Nachweis |
|---|---|---|---|---|
| **C-01** | Architekturbranches konsolidieren | **Erledigt, integriert 21.11.2026** | Zwölf Ziele, vier Entscheidungen, README, Konventionen und Freeplane im selben Integrationsbranch über PR #10 nachgewiesen | `docs/ARCHITECTURE_*.md`, Mindmap |
| **C-02** | Reales Schema-Snapshot aktualisieren | **Erledigt** | Exportskript verlangt Version 6, geschlossenes Gate, 43 Tabellen und neue 0006-Objekte; Poseidon-Export unter Commit `64de205` gepusht und GitHub geprüft | `scripts/export_schema_v2.sh`, `db/schema/retro_rag_v2_test.sql` |
| **C-03** | Alte Statusdokumentation bereinigen | **Erledigt und integriert (21.11.2026)** | README und Schema-Status mit Roadmap abgeglichen, ältere Zwischenstände als historisch eingeordnet; erneute Prüfung nach Branchintegration empfohlen | README, `db/SCHEMA_CURRENT.md`, 0006-Protokoll |
| **C-04** | Technische Abnahme 0006 abschließen | **Erledigt im Scope Testdatenbank** | Migration, Integritäts-, Rollen-, Parallelitäts-, Regressionstests und Restore eines Pre-0006-Dumps dokumentiert; keine Produktivfreigabe behaupten | [0006-Abnahme](UNIVERSAL_KNOWLEDGE_SCHEMA_0006.md) |
| **C-05** | Branchintegration | **Erledigt für Integrationsbranch (21.11.2026)** | [PR #10](https://github.com/ninchen-ai/retro-rag_v2/pull/10) gemergt (`4c09576`); 17 geänderte Dateien, keine fehlenden Basiscommits. Testnachweise stammen vom Poseidon-Lauf 20.11.; keine erneute Live-Ausführung durch GitHub. `main` gesondert entscheiden | C-01–C-04, IP-xx |
| **C-06** | Vollständige Disaster-Recovery-Prüfung | **Offen** | Globale Rollen, HBA-/Konfiguration, Extensions, Borg-/Originalarchiv und Abhängigkeiten auf einem **neu aufgebauten Cluster** kontrolliert wiederherstellen; V1/Nextcloud schützen | Backupkonzept, Wartungsplanung |
| **C-07** | Migration `0007` spezifizieren | **Offen** | Entwurf zu fachneutralen Eigenschaften/Fakten/Belegen inkl. Migration, Rollen, Write-Gate, Rückwärtskompatibilität und Negativtests; erst nach Review anwenden | A-01–A-06, C-05 |
| **C-08** | Entwicklungs- und Abnahmestände verzahnen | **Offen** | PR- und Branchstatus zu PDF/OCR, WebDAV und OCR-Qualität mit der Integrationslinie abgleichen; Implementierung, Testabnahme und Merge getrennt markieren | IP-E bis IP-G |
| **C-09** | Security- und Betriebsnachprüfung | **Offen** | Direkter Container- und IPv6-Zugriff, weitere deaktivierte Rollen bei Aktivierung, Netzwerkadresskonflikte, reproduzierbare Dependency-Locks, Backup-/Monitoringprozesse gezielt prüfen | [Rollenarchitektur](PHASE0_ACCESS_ARCHITECTURE.md), [Konventionen](../conventions.md) |

## D. Fortschritt der siebenstufigen Importpipeline

**Bezeichnung aus der bisherigen Entwicklung beibehalten**; C1/C2 sind die Teilstufen von C, E/F/G werden in separaten Featurebranches entwickelt. Ein **grüner Bausteintest ist kein Nachweis einer Ende-zu-Ende-Integration**.

| ID | Pipeline-Stufe | Implementierungs-/Teststand | Offener Integrations-/Abnahmeschritt |
|---|---|---|---|
| **IP-A** | WebDAV Discovery & Staging | **Grundfunktion vorhanden**, Nextcloud-Discovery/Staging und Metadatenpfad entwickelt | Vollständige Discovery, Ausschlüsse, Größen-/Fehlergrenzen und echten Kontrollimport im Gesamtpfad verifizieren |
| **IP-B** | Dokumentidentität und Dubletten | **Migration 0005 und 4 echte DB-Integrationstests bestanden** | Review-Auflösung, Mehrquellenfälle und End-to-End-WebDAV-Übernahme abschließen |
| **IP-C1** | Atomare Versionsaktivierung | **6 DB-Integrationstests bestanden**, alter separater C1-Konkurrenztest im ursprünglichen Integrationsstand bestanden | An realen Processing-Worker anbinden; regulären Versionswechsel mit vollständigem Index prüfen |
| **IP-C2** | Archivierung und Transaktionssicherheit | **Atomare Archivierungsbausteine und Sicherungsprüfungen entwickelt** | Crash-, Retry- und Datenbank-/Archivkonsistenz im zusammengesetzten Apply nachweisen |
| **IP-D** | Importvertrag und Metadaten | **Im bestehenden Integrationsbranch konsolidiert**, Unit- und Ruff-Prüfungen dokumentiert | Metadatenvertrag an PDF-/OCR-, WebDAV- und Job-Worker-Eingängen durchgehend verifizieren |
| **IP-E** | PDF-Extraktion (Stage 3) | **Feature/PR vorhanden**; schreibfreier PyMuPDF-Adapter mit Seiten-/Chunk-Tests, nicht automatisch in diesem Branch integriert | Branch/PR prüfen, auf Poseidon gemeinsam testen, an Importjobs anbinden, Layoutqualität gesondert beurteilen |
| **IP-F** | OCR (Stage 4) | **Feature/PR vorhanden**; Tesseract-Seitenrouting technisch untersucht, Qualitätsoptimierung eigenständig offen | [Issue #8](https://github.com/ninchen-ai/retro-rag_v2/issues/8): Goldstandard, CER/WER und kritische Kennungen, weitere Seiten/Layouttypen, Review-Schwellen, sichere Integration |
| **IP-G** | Kontrollierter Einzeldatei-WebDAV-Apply | **Feature/PR vorhanden**, Fehler-/Crash-Schutz als Entwurf implementiert | [PR #9](https://github.com/ninchen-ai/retro-rag_v2/pull/9): Tests auf Poseidon, realer Einzeldatei-Apply auf Test-DB nach gesonderter Freigabe, Gate geschlossen nachkontrollieren |

**Ergänzende Pipeline-Abnahmen:** Processing-Jobs, persistente Extraktionsartefakte, Chunk-/Embedding-Erzeugung, Versionsaktivierung nach vollständiger Indexierung und Review-Auflösung sind zusammenhängend noch nicht Ende-zu-Ende abgenommen. Keine unkontrollierte Massenschreibfreigabe.

### Aktive Entwicklungslinien

- [PR #5 – Import-Pipeline konsolidieren](https://github.com/ninchen-ai/retro-rag_v2/pull/5) und [Konsolidierungsprotokoll](IMPORT_PIPELINE_CONSOLIDATION.md).
- [PR #6 – PDF-Extraktion](https://github.com/ninchen-ai/retro-rag_v2/pull/6), [PR #7 – OCR](https://github.com/ninchen-ai/retro-rag_v2/pull/7).
- [PR #9 – Kontrollierter Einzeldatei-WebDAV-Apply](https://github.com/ninchen-ai/retro-rag_v2/pull/9).
- [Issue #8 – OCR-Qualität](https://github.com/ninchen-ai/retro-rag_v2/issues/8).
- Die genannten Links sind **Arbeitsnachweise**, keine Behauptung, dass sämtliche PRs bereits gemergt oder deren Akzeptanzkriterien erledigt sind.

## Integrationsnachtrag PDF/OCR/WebDAV – 21.11.2026

**Branch:** `integration/pdf-ocr-webdav-2026-11-21` · [Draft PR #13](https://github.com/ninchen-ai/retro-rag_v2/pull/13).

- PDF-Extraktion, OCR Stage 4 und OCR-Qualität (`feat/ocr-quality-evaluation`) wurden zusammen mit `feat/controlled-single-webdav-apply` in den **separaten Staging-Branch** übernommen. Dies ist noch **kein Merge in die reguläre Integrationslinie**.
- Nach Ruff-Bereinigung bestätigte Poseidon: `python -m ruff check .` **All checks passed**, `python -m pytest -q -rs` **135 passed, 11 skipped**, `git diff --check` ohne Beanstandung; Staging-Commit `47f22aba`.
- Die vier Tests aus `tests/test_document_identity_integration.py` und die sechs Tests aus `tests/test_version_activation_integration.py` wurden anschließend als separate DB-Integrationsprüfungen über `rag_v2_migrator_login` gegen `retro_rag_v2_test` ausgeführt: **10 passed in 0.23s**. Die Fixtures verwenden transaktionales Rollback; ein nachfolgender unabhängiger Gate-/Datenzähler-Check steht noch aus.
- Der elfte übersprungene Test (`test_version_activation_concurrency.py`) benötigt **einen separaten isolierten Cluster mit Migrationsstand 0005** und ist nicht für die persistente V2-Testdatenbank bestimmt.
- **Unabhängige SQL-Nachkontrolle PASS (Poseidon, 21.11.2026):** `BEGIN READ ONLY` / `COMMIT` über `docker exec -i`: `MAX(schema_migration.version)=6`, `write_gate.writes_enabled=false`, Sperrgrund `Parallelitätstest erfolgreich; Freigabe ausstehend`; `document`, `document_source`, `document_version`, `processing_job`, `review_item`, `knowledge_proposal` jeweils **0**. Damit keine persistierten Fixtures aus den zehn Rollback-DB-Tests nachgewiesen.
- **Weiter offen:** vollständiger E2E-Pfad Nextcloud/WebDAV → PDF/OCR → Job/Artefakte → Chunks/Embeddings → kontrollierte Aktivierung; erst danach Freigabe von PR #13 für den regulären Integrationsbranch. Keine automatische `--apply`-Freigabe, kein Gate-Öffnen, keine Produktivfreigabe.
- Migration `0007` bleibt als gesonderter **nur dokumentierter Entwurf** in [Draft PR #14](https://github.com/ninchen-ai/retro-rag_v2/pull/14). Eine erfolgreiche Pipeline-Regression ist keine Abnahme für `0007`.

### Einzeldatei-Vorschau WebDAV → PDF/OCR (Entwicklungsstand 21.11.2026)

Auf dem **Staging-Branch** wurde der schreibfreie Adapter `src/retro_rag/importer/pdf_preview_cli.py` ergänzt, mit `tests/test_pdf_preview_cli.py`. Er verwendet eine explizite Nextcloud-`fileid`, einen vorab bestätigten SHA-256, den abgesicherten WebDAV-Download und den vorhandenen `read_pdf()`-Adapter. Das Original wird nur für die Dauer der Extraktion in einem privaten temporären Verzeichnis abgelegt und anschließend gelöscht; das Ergebnis enthält ausschließlich Metadaten, OCR-Seiten, Chunk-Zahl und Warnungen, keine DB-Schreiboperationen und keine Freigabe. `indexing_allowed` muss weiterhin `False` bleiben.

**Poseidon-Regressionsnachweis (21.11.2026):** Nach Fast-Forward auf `28d32e0` meldeten `python -m ruff check .` **All checks passed**, `python -m pytest -q -rs` **143 passed, 11 skipped** (gegenüber 135 + 8 Preview-Tests), `git diff --check` ohne Beanstandung. Die zehn Datenbank-Integrationstests wurden separat zuvor bestanden und unabhängig nachkontrolliert. **Echter WebDAV→PDF-Preview-Nachweis (Poseidon, 21.11.2026):** Nextcloud-Instanz `poseidon-nextcloud`, `fileid=172`, `cubx-103.pdf`, SHA-256 `f10dc04911aa75241adcb29731af62fc4ce4c5e5a21b0a69ff621778c784f82b`; 112 Seiten, 113 Chunks, OCR deaktiviert, kein extrahierbarer Text auf Seiten 111/112, OCR dort erforderlich. Zweiter Abruf und Vertrags-Hash stimmten überein, `indexing_allowed=false`, `fact_proposal_count=0`. **Noch offen:** gezielter OCR-Lauf und Goldstandardvergleich, persistente Job-/Chunk-/Embedding-Integration sowie isolierter C1-Parallelitätstest. Dies ist **kein** End-to-End-Importworker, kein persistenter Chunk-/Embedding-Pfad und kein neuer `--apply`-Weg.

### Echter OCR-Nachtrag – ASUS CUBX, 21.11.2026

- In der schreibfreien Nextcloud-Vorschau von `cubx-103.pdf` (`fileid=172`, SHA-256 `f10dc04911aa75241adcb29731af62fc4ce4c5e5a21b0a69ff621778c784f82b`) wurde `ocr_mode=auto`, `ocr_pages={111,112}`, `ocr_language=eng+deu`, `ocr_dpi=200` ausgeführt: 112 Seiten, 114 Chunks, `ocr_pages=[111]`, `ocr_failed_pages=[112]`, Meldung `OCR lieferte keinen Text` für Seite 112, `indexing_allowed=false`, keine Faktvorschläge.
- **Interpretation anhand des vorhandenen visuell geprüften Goldstandards:** Seite 111 ist eine bildbasierte Anzeige mit echtem OCR-Bedarf; Seite 112 ist eine **bestätigte weiße Leerseite ohne OCR-Bedarf**. Die Fehlermeldung auf Seite 112 resultiert aus der erzwungenen OCR und bedeutet nicht, dass relevanter Inhalt verloren ging.
- **Nächster Kontrolllauf:** Ausschließlich `ocr_pages={111}` erzwingen und Seite 112 nicht explizit bearbeiten; bei funktionierender Auto-Heuristik dürfte Seite 112 nicht in `ocr_failed_pages` erscheinen. Die technische OCR-Ausführung ist **keine Qualitätsfreigabe**: CER/WER und Fachbegriffe getrennt anhand des bestehenden OCR-Goldstandards prüfen. Persistente Job-/Chunk-/Embedding-Integration weiterhin offen.

## E. Empfohlene Reihenfolge und Freigabe-Gates

| Reihenfolge | Paket | Abschlussbedingung |
|---|---|---|
| **1** | C-03, C-08: Dokumentation/Branches abgleichen | Widerspruchsfreie aktuelle Statusseite; alte Zwischenstände deutlich historisch; Integrationsdiff nachvollziehbar |
| **2** | C-05: 0006-Branch integrieren – erledigt 21.11. | PR #10 gemergt; Gate im letzten Poseidon-Test geschlossen, keine neue DB-Schreibfreigabe |
| **3** | IP-E/F/G + IP-C1/C2/D: Importpfad verbinden | Echte PDF/OCR-/WebDAV-Datenflussprüfungen mit geeigneten Testdateien, kein ungeprüfter Massen-Apply |
| **4** | C-07 + A-01 bis A-06: Entwurf Migration 0007 | Fachmodell und DB-Migration als Entwurf, Prüfung von Rückwärtskompatibilität, Provenienz und Rollen |
| **5** | A-09 bis A-13: Extraktion, Vorschläge und Freigabe | Regelversionen, echte Reviews, unabhängige Freigabe, Negativtests, Audit; kein Selbstgenehmigen |
| **6** | A-07/A-08/A-14/A-15: Themen-/Konfliktlogik, Retrieval, Bewertung | Statusgetrennte Suche, Kontext- und Quellenbelege, robuste Regressionen |
| **7** | C-06/C-09: erweiterter Wiederanlauf/Betrieb | Neuaufbau-DR, HBA-/Rollen-/Monitoring- und Archivtests bestanden |

Diese Reihenfolge ist eine Empfehlung, **keine** Berechtigung, Migrationen anzuwenden, Write-Gates zu öffnen oder PRs ungeprüft zu mergen. Abhängigkeiten können Arbeiten parallel erlauben.

## Regeln für die Pflege der Roadmap

1. Nach jedem fachlich freigegebenen Architekturentscheid den betroffenen A-Punkt aktualisieren; die unveränderte Zielentscheidung zusätzlich im Architektur-ADR belassen.
2. Nach SQL-/Python-/Integrationstests Status nur mit konkretem Nachweis (Branch/Commit, Datenbank, Zeitpunkt, Ergebnis, verbleibende Grenzen) erhöhen.
3. **Implementiert**, **auf Poseidon getestet**, **im Integrationsbranch enthalten** und **produktiv freigegeben** sind unterschiedliche Zustände; nie gleichsetzen.
4. Offene PRs/Issues periodisch mit diesem Aufgabenindex abgleichen, erledigte Punkte mit Datum und Nachweis schließen, historische Befunde nicht heimlich umschreiben.
5. Das Write-Gate in `retro_rag_v2_test` bleibt ohne explizite Betreiberfreigabe **geschlossen**; die Datenbanken V1 und Nextcloud sind außerhalb des V2-Änderungsumfangs.
