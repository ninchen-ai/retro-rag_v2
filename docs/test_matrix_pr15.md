# Testmatrix – PR #15 (Importpipeline, Retro-RAG V2)

**Status:** Fachlich freigegeben am 22.11.2026 – Abnahmeumfang eingefroren; technische Abnahme ausstehend  
**Geltungsbereich:** Extraktionsworker von PR #15 auf Poseidon (nicht vollständige End-to-End-Indexierung)  
**Umgebung:** Poseidon, PostgreSQL 16; DB-Schreibtests ausschließlich in einem separat geprüften, wegwerfbaren isolierten PostgreSQL-Testcluster. Keine produktive Freigabe oder systemd-Timer-Aktivierung.

## Regeln für diese Matrix

1. Der Abnahmeumfang ist seit der fachlichen Freigabe vom **22.11.2026 eingefroren**. Es gelten ausschließlich die 13 aktiven IDs in den Abschnitten A–E (11 × M, 2 × S).
2. Abnahme bedeutet: vorhandene Tests ausführen, Ergebnisse auswerten und dokumentieren. **Keine neuen Tests schreiben, bestehende Tests nicht ändern oder löschen.**
3. Erkannte Testlücken und unvollständige Abdeckung werden als Abweichung oder unter „Vorschläge“ dokumentiert. Ohne ausdrückliche neue Entscheidung keine Umsetzung.
4. Neue Szenarien oder Prioritätsänderungen erfordern eine bewusste Freigabe mit Datum und Begründung im Änderungsprotokoll.
5. Abnahme abgeschlossen: Alle M-IDs sind nachweislich grün, oder **jede** nicht grüne M-ID ist als Abweichung dokumentiert und zur Entscheidung vorgelegt. Eine dokumentierte Abweichung gilt nicht automatisch als technische Erfüllung.
6. Die Zuordnung zu einem vorhandenen Test stellt **keinen** Laufnachweis dar. Alle Status bleiben bis zur Ausführung/Auswertung `offen`. Umfang und Ergebnis eines nur teilweise passenden Tests sind im Protokoll ausdrücklich abzugrenzen.
7. Die Prüfung auf Poseidon darf niemals Schreibtests gegen die dauerhafte Datenbank `codeanalyse-postgres` oder Produktivdaten durchführen. Vor isolierten DB-Tests Zielcluster, Migrationen, leere Jobqueue, Gate und Rollen prüfen; bei nicht sauberem Abbruch Wegwerfcluster verwerfen. Das Write-Gate außerhalb des isolierten Testclusters bleibt geschlossen.

**Priorität:** **M** = muss, **S** = sollte, **O** = optional  
**Status:** `offen` / `grün` / `rot` / `entfällt`  
**Abdeckung (nur Bestandsvergleich):** direkt / teilweise / ohne direkten Nachweis

## A. Mehrworker (Gleichzeitigkeit)

| ID | Szenario | Erwartetes Verhalten | Prio | Status | Zuordnung (Testdatei/Test; Abdeckung) |
| -- | -- | -- | -- | -- | -- |
| A1 | Zwei Worker starten gleichzeitig, ein Job in der Queue | Genau ein Worker übernimmt den Job | M | offen | `tests/test_import_worker_isolated_integration.py::test_concurrent_workers_expiry_and_retry_exhaustion` – direkt (konkurrierende Claims) |
| A2 | Zwei Worker, mehrere Jobs | Jeder Job wird genau einmal verarbeitet, keine Doppelverarbeitung | M | offen | Kein direkter Mehrjob-Test; `test_concurrent_workers_expiry_and_retry_exhaustion` prüft nur einen Job – teilweise |
| A4 | Ein Worker schlägt bei einem Job fehl, der andere läuft weiter | Fehlerisolierung: andere Jobs bleiben unberührt | S | offen | `tests/test_import_worker.py::test_worker_failure_is_isolated_and_reported` – teilweise (Fehlerbehandlung ohne parallelen zweiten Worker) |

## B. Crash und Wiederanlauf

| ID | Szenario | Erwartetes Verhalten | Prio | Status | Zuordnung (Testdatei/Test; Abdeckung) |
| -- | -- | -- | -- | -- | -- |
| B1 | Worker wird mitten in einem Schritt (z. B. Extraktion) abgebrochen | Job bleibt in konsistentem Zustand, kein halb aktivierter Index | M | offen | `tests/test_import_worker_isolated_acceptance.py::test_killed_backend_rolls_back_chunks_and_recovery` – direkt für DB-Transaktionsabbruch und Rollback; kein vollständiger OS-Prozess-Crash |
| B2 | Neustart nach Abbruch | Fertige Schritte werden wiederverwendet, offener Schritt läuft neu | M | offen | `test_killed_backend_rolls_back_chunks_and_recovery` und `test_concurrent_workers_expiry_and_retry_exhaustion` – teilweise (Reclaim/erneute Persistierung, nicht allgemeine Wiederverwendung aller fertigen Schritte) |
| B4 | Zwischenergebnis ist ungültig oder beschädigt | Schritt wird neu ausgeführt, kein Weiterverarbeiten mit defekten Daten | S | offen | `tests/test_import_worker.py::test_verified_original_rejects_modified_archive` und `job_pipeline.py::validate_prepared_content` – teilweise (Ablehnung, erneute Schrittausführung nicht belegt) |

## C. Lease (zeitlich begrenzte Job-Sperre)

| ID | Szenario | Erwartetes Verhalten | Prio | Status | Zuordnung (Testdatei/Test; Abdeckung) |
| -- | -- | -- | -- | -- | -- |
| C1 | Worker hält gültige Lease | Kein anderer Worker kann den Job übernehmen | M | offen | `tests/test_import_worker_isolated_integration.py::test_concurrent_workers_expiry_and_retry_exhaustion` – direkt |
| C2 | Lease läuft ab (Worker tot) | Anderer Worker kann den Job übernehmen | M | offen | `tests/test_import_worker_isolated_integration.py::test_concurrent_workers_expiry_and_retry_exhaustion` – direkt (simulierter Ablauf) |
| C3 | Alter Worker meldet sich nach Ablauf zurück und will schreiben | Seine Schreibzugriffe werden abgewiesen (kein „Zombie-Worker“) | M | offen | `src/retro_rag/importer/job_pipeline.py::_persist_contract_rows` prüft Owner und Lease beim Schreiben – teilweise, expliziter Zombie-Worker-Test fehlt |

## D. RBAC (getrennte DB-Rollen)

| ID | Szenario | Erwartetes Verhalten | Prio | Status | Zuordnung (Testdatei/Test; Abdeckung) |
| -- | -- | -- | -- | -- | -- |
| D1 | Worker-Rolle führt erlaubte Operationen aus | Funktioniert | M | offen | `tests/test_import_worker_isolated_acceptance.py::test_importer_rbac_and_no_premature_activation` – direkt (Importer-Persistierung) |
| D2 | Worker-Rolle versucht verbotene Operation (z. B. Fakten freigeben, Tabellen ändern) | Wird von der Datenbank abgelehnt | M | offen | `tests/test_import_worker_isolated_acceptance.py::test_importer_rbac_and_no_premature_activation` – teilweise (Gate-Update und Fakt-Insert abgewiesen, keine vollständige Rechteprüfung) |

## E. Regression (Bestand darf nicht kaputtgehen)

| ID | Szenario | Erwartetes Verhalten | Prio | Status | Zuordnung (Testdatei/Test; Abdeckung) |
| -- | -- | -- | -- | -- | -- |
| E1 | Gesamte vorhandene Testsuite | Alles grün, oder jede Abweichung dokumentiert | M | offen | `python -m pytest -q -rs` auf aktuellem PR-Commit – ausstehend; isolierte opt-in DB-Tests separat und seriell |
| E2 | Dry-Run ohne `--apply` | Keine Änderungen in DB und Archiv | M | offen | `src/retro_rag/importer/worker.py::main` – teilweise (früher CLI-Abbruch ohne Jobclaim; vollständige Unverändertheitsprüfung ausstehend) |

## Zusätzlicher Sicherheitsnachweis aus vorhandenen Tests (keine neue Matrix-ID)

`tests/test_import_worker_isolated_acceptance.py::test_importer_rbac_and_no_premature_activation` prüft außerdem, dass die Aktivierung einer noch nicht vollständig indexierten Dokumentversion abgewiesen wird. Dieser Nachweis wird zusammen mit **D1/D2** dokumentiert; er ersetzt nicht das zurückgestellte Crash-Szenario B3.

## Zurückgestellte Szenarien – ausdrücklich nicht Teil der PR-#15-Abnahme

Die ursprünglichen IDs bleiben zur Nachvollziehbarkeit erhalten, sind aber **nicht** in der eingefrorenen Menge der aktiven Abnahmetests.

| ID | Ursprüngliches Szenario | Ursprüngliche Prio | Behandlung / Begründung |
| -- | -- | -- | -- |
| A3 | Zwei Worker, derselbe Dokumenthash wird gleichzeitig eingeliefert | M | Allgemeine Import-/Identitätsabnahme: parallele WebDAV-Anlieferung und Version-Deduplizierung liegen vor dem Extraktionsworker |
| B3 | Abbruch während der Versionsaktivierung | M | Allgemeine Indexierungs-/Aktivierungsabnahme: PR #15 aktiviert keine Version |
| B5 | Dieselbe Datei wird nach erfolgreichem Lauf erneut eingespielt | M | Allgemeine Import-/Identitätsabnahme: vollständige erneute Datei-Einspielung, nicht nur erneuter Worker-Claim |
| C4 | Worker verlängert Lease rechtzeitig | S | Separate Architekturentscheidung: derzeit feste 60-Minuten-Lease, keine Heartbeat-/Verlängerungsfunktion |
| D3 | Lese-Rolle (Suche) versucht zu schreiben | M | Allgemeine RBAC-Regression; ggf. vorhandene rollenbezogene Tests außerhalb PR #15 gesondert prüfen |
| D4 | Review-Rolle versucht, Verarbeitungsjobs zu ändern | S | Allgemeine RBAC-Regression; ggf. vorhandene rollenbezogene Tests außerhalb PR #15 gesondert prüfen |
| E3 | Dokument wird in anderen Nextcloud-Ordner verschoben | S | Allgemeine WebDAV-/Dokumentidentitätsabnahme; kein Worker-Szenario |

## Abnahmeprotokoll

| Feld | Wert |
| -- | -- |
| Fachliche Freigabe der Matrix | 22.11.2026 |
| Datum der technischen Abnahme | |
| Getesteter Commit-Hash | |
| Umgebung | Poseidon; isolierter Wegwerfcluster für schreibende DB-Tests |
| Ergebnis gesamt | offen – noch keine vollständige Abnahme |
| Abweichungen | noch auszuwerten |
| Sicherheitskontrollen (Cluster/Gate/Rollen) | noch nachzuweisen |

## Vorschläge (Testlücken, nicht Teil der Abnahme)

*Nur dokumentieren, nicht eigenmächtig Tests schreiben oder bestehende ändern. Änderungen am eingefrorenen Umfang benötigen eine neue ausdrückliche Freigabe.*

- **A2:** Bestehender Mehrworker-Test prüft nur einen Job, nicht mehrere parallele Jobs.
- **A4:** Fehlerisolierung wird ohne tatsächlichen zweiten gleichzeitig arbeitenden Worker getestet.
- **B1:** DB-Backend-Abbruch ist geprüft; vollständiger Worker-Prozess-Abbruch bleibt als Abgrenzung dokumentiert.
- **B2:** Reclaim nach Crash ist belegt; Wiederverwendung bereits fertiger Verarbeitungsschritte nicht vollständig nachgewiesen.
- **B4:** Beschädigte Originale/Zwischenergebnisse werden abgewiesen; automatisches Neuausführen des betroffenen Schritts nicht nachgewiesen.
- **C3:** Schreibschutz gegen abgelaufene oder fremde Lease ist implementiert; explizites Zombie-Worker-Szenario fehlt.
- **D2:** Geprüfte verbotene Operationen beschränken sich auf Gate-Update und Fakt-Insert.
- **E2:** Ein überprüfender Vorher-/Nachher-Nachweis für DB und Archiv ist noch zu protokollieren.
- **C4 (zurückgestellt):** Für längere Extraktions-/OCR-Läufe klären, ob Heartbeat, Lease-Verlängerung oder eine anders begrenzte Verarbeitungsdauer nötig ist.
- Ausstehende Nachweise sind bis zur Durchführung **nicht** als grün zu bewerten. Fehlende Tests werden in dieser Abnahme ausschließlich als Abweichungen dokumentiert.

## Änderungsprotokoll

| Datum | Änderung | Begründung |
| -- | -- | -- |
| 22.11.2026 | Erstfassung (Entwurf) | Vorläufige Testmatrix mit 20 Szenarien |
| 22.11.2026 | Fachlich freigegebene Kürzung auf 11 M- und 2 S-IDs; vorhandene Testzuordnungen ergänzt; sieben IDs zurückgestellt | PR #15 umfasst nur den wiederaufnehmbaren Extraktionsworker, nicht die vollständige Import-, Embedding- und Aktivierungspipeline. Keine Tests hinzugefügt oder verändert |
