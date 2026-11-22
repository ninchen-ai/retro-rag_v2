# Testmatrix – OCR-Qualitätsbewertung (Retro-RAG V2)

**Status:** Entwurf – fachliche Freigabe ausstehend; keine technische Abnahme erfolgt  
**Stand:** 22.11.2026  
**Branch:** `feat/ocr-quality-evaluation`  
**Grundlage:** `docs/ocr-quality-plan.md`, `docs/OCR_QUALITY_EVALUATION.md`, `conventions.md` sowie `docs/PROJECT_ROADMAP.md` auf `integration/pdf-ocr-webdav-2026-11-21` (historischer Stand 21./22.11.2026)  
**Umgebung für spätere Versuche:** Poseidon, ausschließlich isolierte lokale Dateien

## 1. Geltungsbereich und Regeln

Diese Matrix ist **eigenständig**. Die fachlich eingefrorene PR-#15-Abnahme unter `docs/test_matrix_pr15.md` auf `feat/resumable-import-worker-2026-11-22` umfasst den Extraktionsworker und bleibt **unberührt**.

1. Die vorliegende Matrix ist zunächst **nur ein Vorschlag**. Ihre IDs, der konkrete Korpus, Messmethoden und Schwellenwerte werden erst durch ausdrückliche Freigabe verbindlich eingefroren.
2. Bis zu dieser Freigabe **keine** konkreten Testseiten festlegen, keine Referenztexte erstellen und **keine** OCR- oder Layout-Evaluationsläufe durchführen.
3. Keine bestehende Datei, Funktion, Variable oder bestehenden Tests verändern; keine neuen Tests eigenmächtig schreiben.
4. Evaluation ausschließlich gegen lokale Kopien/Dateien: **keine Datenbank, kein Worker, kein `--apply`, kein Index, keine Änderungen an Nextcloud, Archiv, Originalen oder Write-Gate**.
5. Die Matrix unterscheidet **vorhandene technische Testabdeckung** von **fachlicher Messung am freigegebenen Korpus**. Ein bestandener Unit-Test ist keine bestandene OCR-Qualitätsmessung.
6. Ergebnisse und abweichende Befunde je ID dokumentieren. Noch fehlende oder nur teilweise vorhandene Abdeckung wird nicht automatisch grün.
7. Keine PDF-Originale, OCR-Rohtexte, vollständigen Referenztexte, private Quellkennungen, Quellhashes oder Berichte mit solchen Angaben in Git committen. Nur anonymisierte, aggregierte Abnahmeprotokolle dürfen ins Repository.
8. Eine Qualitätsabnahme berechtigt **nicht** zur Indexierung, Faktenfreigabe oder Produktionsschaltung.

**Priorität:** M = muss, S = sollte, O = optional.  
**Status:** `offen`, `grün`, `rot`, `entfällt`; **alle neuen Abnahme-IDs beginnen mit `offen`**.  
**Vorhandene Abdeckung:** direkt = vorhandener Test für einen technischen Teilaspekt; teilweise = nur angrenzende Prüfung; keine = kein belegter Test. Das ersetzt keinen Laufnachweis der neuen Matrix.

**Matrixumfang (Entwurf): 29 IDs – 23 × M, 3 × S, 3 × O.** Die von der Roadmap motivierten zusätzlichen IDs B9, B10, E4 und E5 wurden mit Zustimmung vom 22.11.2026 ergänzt; die Matrix und ihre Schwellenwerte sind damit **noch nicht fachlich eingefroren oder zur Ausführung freigegeben**.

## 2. Freigaben vor der Ausführung

| Freigabepunkt | Entscheidung | Status |
| --- | --- | --- |
| Zehn Kategorien OQ-01 bis OQ-10 als Korpusrahmen | Noch nicht fachlich freigegeben | offen |
| Konkrete zehn Originalseiten und Seiten-/Renderidentitäten | Erst nach Freigabe auswählen | offen |
| Manuelle Transkription, zweiter visueller Abgleich und eingefrorene Referenz | Noch nicht freigegeben/erstellt | offen |
| Gemeinsame Textnormalisierung, Block-/Zellreferenzregeln | Zur Freigabe | offen |
| Grenzwerte und kritische Fehlertoleranz aus Qualitätsplan Abschnitt 8 | Zur Freigabe | offen |
| A–D: PyMuPDF/Tesseract-Sprach- und DPI-Vergleich | Zur Freigabe | offen |
| E: DocLayout-YOLO-gestützte Regionen-OCR | Gesonderte optionale Freigabe | offen |
| F: lokales Vision-LLM als selektiver, regelbasierter Zweitkandidat | Gesonderte optionale Freigabe für Ausführung; kein automatischer Ersatz oder Übernahme | offen |
| Verpflichtende VLM-Schutzbewertung E5 | Vor einer etwaigen VLM-Nutzung anhand historischer Befunde und ggf. gesondert freigegebener Realversuche prüfen; ohne Freigabe keine VLM-Ausführung | offen |

**Hinweis:** Die historischen Goldstandard-Seiten und der CUBX-Ausschnitt sind **noch nicht** als konkrete Seiten des neuen Korpus ausgewählt. Frühere visuelle Klassifikationen sind kein Ersatz für vollständige, freigegebene Ground-Truth-Transkriptionen.

## 3. Testkorpus – ausschließlich Seitenanforderungen

| Platz | Kategorie | Bereitzustellende Seite (noch nicht ausgewählt) |
| --- | --- | --- |
| OQ-01 | Sauberer Scan | Gut lesbarer einspaltiger Fließtext |
| OQ-02 | Sauberer Scan | Technisches Datenblatt mit Überschriften |
| OQ-03 | Schlechter Scan | Rauschen, Kontrast- oder Kompressionsprobleme |
| OQ-04 | Schlechter Scan | Schräglage, Unschärfe oder ungleichmäßige Beleuchtung |
| OQ-05 | Zweispaltig | Zwei Textspalten mit visuell klarer Reihenfolge |
| OQ-06 | Einfache Tabelle | Technische Werte in eindeutig zuordenbaren Zeilen und Spalten |
| OQ-07 | Komplexe Tabelle | Verbundene Zellen oder Pin-/Registermatrix |
| OQ-08 | Kleine Schrift | Fußnoten oder dicht beschriftete Bereiche |
| OQ-09 | Modellnummern | Zahlreiche ähnliche Chip-/Produkt-/Teilenummern |
| OQ-10 | Zahlen und Einheiten | Dezimalwerte, Spannungen, Frequenzen, Größen |

Leerseiten- und OCR-Routingprüfung als **separaten** Kontrollfall dokumentieren; nicht in CER/WER-Nenner für texttragende Seiten aufnehmen.

## 4. A – Isolation, Quellen und Referenzqualität

| ID | Szenario | Akzeptanzkriterium | Prio | Status | Vorhandene Abdeckung / Grenze |
| --- | --- | --- | --- | --- | --- |
| A1 | Isolierter Betrieb | Keine DB-/Worker-/Nextcloud-Schreibzugriffe, keine Quelldateiänderung; lokales Ausgabeverzeichnis | M | offen | Technische Read-only-Tests teilweise vorhanden; neue Umgebung nicht ausgeführt |
| A2 | Exakte Quell-/Renderidentität | Identischer PDF-Inhalt/Seite/Region mit SHA- und Render-/Modellparametern; kein Vergleich unterschiedlicher Ausschnitte | M | offen | `tests/test_pdf_goldstandard.py`, `tests/test_pdf_column_order_v2.py` – teilweise |
| A3 | Unabhängiger Referenztext | Manuell vom sichtbaren Original erstellt, zweitgeprüft und vor der Messung eingefroren | M | offen | `tests/test_pdf_goldstandard.py::test_unreviewed_template_must_not_infer_ground_truth` – teilweise, keine fertigen Volltranskriptionen |
| A4 | Ungeprüfte Referenz abweisen | Ungeprüfte/unvollständige Referenz liefert keine Gütezahlen und keine Freigabe | M | offen | `tests/test_ocr_evaluation.py::test_unreviewed_does_not_get_a_score` – direkt für technischen Schutz |
| A5 | Korpusabdeckung dokumentieren | Alle zehn freigegebenen Seitenplätze belegt oder Abweichung begründet; Kategorien nachvollziehbar | M | offen | Keine fachliche Korpusabnahme vorhanden |

## 5. B – OCR-Routing und Textqualität

| ID | Szenario | Akzeptanzkriterium | Prio | Status | Vorhandene Abdeckung / Grenze |
| --- | --- | --- | --- | --- | --- |
| B1 | Native Extraktion vs. OCR-Auslösung | Textseiten erhalten native Ausgabe; echte Scan-Kandidaten/erzwungene geprüfte Seiten werden korrekt unterschieden | M | offen | `tests/test_pdf_ocr.py::test_no_ocr_by_default`, `test_auto_preserves_native_text`, `test_auto_ocr_scan_and_status` – technische Abdeckung |
| B2 | Leerseite / OCR-Warnungen | Visuell leere Seite zählt nicht als verlorener Text; OCR-Fehler bei nichtleeren Seiten werden getrennt markiert | M | offen | `tests/test_pdf_ocr.py::test_ocr_failure_preserves_original`, `test_read_pdf_keeps_gate_closed_and_tracks_ocr` – teilweise; historische CUBX-S.112-Warnung kein Qualitätsverlust |
| B3 | CER/WER je Seite und Variante | Auf freigegebenen Ganzseitenreferenzen berechnen und einzeln sowie nach Kategorie berichten | M | offen | `tests/test_ocr_evaluation.py::test_normalization_and_distance`, `test_perfect_match`, `test_insertions_can_exceed_one_hundred_percent` – Rechenlogik, **keine echte Ganzseitenabnahme** |
| B4 | Sprachvergleich `eng` / `eng+deu` | Gleiche Originalregion, DPI, Referenz und OCR-Parameter bis auf Sprache; Ergebnisunterschiede belegt | M | offen | Historischer CUBX-PNG-Ausschnitt: CER 2,32 % vs. 2,51 %, WER 15,00 % vs. 16,25 %; provisorische Referenz, **kein** formaler Pass |
| B5 | DPI-Vergleich 200 / 300 | Vergleich auf identischer Quelle/Referenz und kontrollierten Einstellungen; Laufzeit protokolliert | S | offen | Kein freigegebener Realvergleich belegt |
| B6 | Modellnummern exakt | Jede freigegebene Referenzkennung exakt prüfen, Fehl-/Verwechslungen einzeln berichten | M | offen | `tests/test_ocr_evaluation.py::test_wrong_hardware_number_is_detected` und `critical_term_recall` – teilweise; vorgeschlagen ≥ 99 % |
| B7 | Zahlen und Wert-Einheit-Paare | Vorzeichen, Dezimalstellen, Kennungen, Einheiten und Wertepaare separat zählen; kritische Fehler ausweisen | M | offen | Noch keine vollständige eigenständige fachliche Bewertungsstrecke; vorgeschlagen ≥ 99 % |
| B8 | Erfundene technische Angaben | Zusätzlich im OCR-/Vision-Ergebnis auftauchende unbelegte technische Kennungen und Werte explizit bewerten | M | offen | `critical_term_recall` erfasst fehlende Begriffe, **nicht** erfundene; vorgeschlagen 0 kritische Fälle |
| B9 | PSM 6/7/11 unter gleichen Bedingungen | Für jeweils geeignete, freigegebene Bildregionen identische Quelle, Zuschnitt, DPI, Sprache und Referenz; nur PSM variieren; CER/WER und kritische Zeichen vergleichen | M | offen | Roadmap: 12 Kandidaten aus drei Regionen mit PSM 6/11; zusätzlich PSM-7-Einzelzeilenversuch und Regression 153 passed/11 skipped. Technisch dokumentiert, **kein** regionsgleicher Ground-Truth-Qualitätsnachweis |
| B10 | Ganze Seite gegenüber Regions-OCR | Den Textumfang vorab genau angleichen: Ganzseitenergebnis auf dieselben Referenzregionen abbilden, gesondert Vollständigkeit/Regionenabdeckung bewerten; keine Ganzseiten-CER gegen einzelne Crop-Referenz | M | offen | Roadmap: CUBX S. 111 als Ganzseite sowie regionale 200/300-DPI-/PSM-Experimente; historische Kandidaten vorhanden, ein fairer quantitativer Vergleich fehlt |

## 6. C – Layout und Struktur

| ID | Szenario | Akzeptanzkriterium | Prio | Status | Vorhandene Abdeckung / Grenze |
| --- | --- | --- | --- | --- | --- |
| C1 | Zweispaltige Lesereihenfolge | Reihenfolge der vorab referenzierten Textblöcke/Übergänge nachweisbar korrekt | M | offen | `tests/test_pdf_column_order_v2.py` (Erhalt/Geometrie), reale USB-601/606-Vorschläge `REVIEW_REQUIRED`; vorgeschlagen ≥ 95 % |
| C2 | Einfache Tabellenstruktur | Zelltexte plus Zeilen-/Spaltenbeziehungen mit geprüfter Referenz vergleichen | M | offen | PyMuPDF-Tabellenkandidaten sind **keine** validierte Zellstruktur; vorgeschlagen ≥ 95 % |
| C3 | Komplexe Pin-/Registermatrix | Jede freigegebene Pin-/Signal- bzw. Register-/Wert-Zuordnung nachweisbar; keine Faktenfreigabe bei Mehrdeutigkeit | M | offen | Historische Matrox-G200-Pinmatrix bleibt unbestätigt; keine vollständige Zellabnahme |
| C4 | DocLayout-YOLO nur als Vorschlag | Klassenkonflikte und unzugeordnete Inhalte bleiben erhalten und führen zu Review, nicht zur automatischen Auswahl | S | offen | `tests/test_pdf_layout_conflicts_v2.py`, `tests/test_doclayout_batch_benchmark.py`; historische 16 Konflikttests grün, keine fachliche Freigabe |

## 7. D – Vergleichbarkeit, Messung und Ergebnisentscheidung

| ID | Szenario | Akzeptanzkriterium | Prio | Status | Vorhandene Abdeckung / Grenze |
| --- | --- | --- | --- | --- | --- |
| D1 | Messvarianten vergleichbar | A–D für dieselbe freigegebene Quelle; E/F nur nach Einzelentscheidung; fehlende Varianten als `nicht getestet` kennzeichnen | M | offen | Technische Einzeladapter vorhanden; kein freigegebener Variantenvergleich am Gesamtkorpus |
| D2 | Laufzeit auf gleicher Grundlage | OCR-Zeit/Seite, reine Layout-Inferenz und gesamte Pipeline getrennt ausweisen, Host/Modelle/Startbedingungen dokumentieren | M | offen | Historische YOLO-Inferenz 0,7220–1,8840 s; isolierter PDF-E2E 21,46 s **nicht** unmittelbar vergleichbar |
| D3 | Qualitätsgrenzen anwenden | Sämtliche vorgeschlagenen, **erst noch freizugebenden** Grenzwerte je Seite/Kategorie auswerten; kritische Fehler nicht wegmitteln | M | offen | Keine Grenzwerte im OCR-Tool als Indexierungsfreigabe implementiert |
| D4 | Manuelle Nachprüfung und Empfehlung | Begründete Entscheidung zu Standard-OCR, regionalem Routing, zusätzlicher Layoutanalyse und Review-Bedarf | M | offen | Bisherige Versuchsergebnisse nur Baseline |
| D5 | Reproduzierbarkeit/Provenienz | Quell-/Seitenidentität, Referenzversion, Engine-/Modellversion, Sprache, DPI, Parameter und Ergebnis dokumentiert | M | offen | `tests/test_ocr_evaluation.py::test_reviewed_case_provenance`, Goldstandard-/Layout-Tests – teilweise |

## 8. E – Optionale, gesondert freizugebende Vergleiche

| ID | Szenario | Akzeptanzkriterium | Prio | Status | Vorhandene Abdeckung / Grenze |
| --- | --- | --- | --- | --- | --- |
| E1 | DocLayout-gestützte Regions-OCR | Eindeutige Region zu exakt gleicher Referenz; Textgenauigkeit und Struktur separat vergleichen | O | offen | YOLO/Geometrie experimentell erprobt, keine freigegebene integrierte Regions-OCR |
| E2 | Selektiver, regelbasierter Vision-LLM-Zweitkandidat | Erst Standardextraktion/Tesseract; VLM ausschließlich bei vordefinierten auffälligen Regionen und nach gesonderter Freigabe. Tesseract- und VLM-Transkripte parallel als unbestätigte Kandidaten mit Region, Modell, Prompt, Abweichungen und Reviewbedarf erhalten; **kein automatisches Überschreiben, Indexieren oder Faktenfreigeben** | O | offen | Roadmap: Qwen3-VL 2B und Gemma 3 12B nur als isolierte Einzelversuche. Triggerregeln, Review und produktive Integration nicht freigegeben |
| E3 | Ressourcen und Nutzen | Qualitätsgewinn gegen CPU-/GPU-/RAM- und Laufzeitkosten dokumentieren | O | offen | Keine vergleichbaren, vollständig gemessenen End-to-End-Varianten vorhanden |
| E4 | Qwen3-VL 2B gegen Gemma 3 12B | Nach gesonderter VLM-Ausführungsfreigabe dieselben ungesehenen, unabhängig referenzierten Bildregionen und neutrale Transkriptionsprompts vergleichen; Wiederholungen, CER/WER, Kennungen, Fehler und Ressourcen pro Modell dokumentieren | S | offen | Roadmap: Qwen 2/3, Gemma 3/3 visuell richtige Titel-/Sloganzeilen, Gemma bei zehn Badges mit Fehler `3D Games Banned` statt `3D Games Bundled`; kleine, **nicht statistisch belastbare** Stichproben |
| E5 | VLM-Halluzinationen, Prompt-Einfluss und Reviewbarriere | An historischen Befunden sowie – nur falls gesondert freigegeben – neuen Blind-/Wiederholungsversuchen unbelegte Ergänzungen, falsch begründete Kandidaten, Prompt-Leakage und Tesseract/VLM-Konflikte erfassen. Kriterien/Entscheidung zur menschlichen Prüfung dokumentieren; keine Selbstbestätigung, kein automatisches Überschreiben oder Fakten-/Indexfreigabe | M | offen | Roadmap: Qwen rationalisierte einen falschen Unterstrich mit unbelegten Aussagen; Gemma verwechselte `Bundled` und `Banned`. Schutzbewertung ist verpflichtend, **auch wenn E2/E4 nicht zur Ausführung freigegeben werden** |

## 9. Vorgeschlagene Schwellenwerte – alle **zur Freigabe**

| Kennzahl | Saubere Scans | Schwierige Scans / allgemeiner Fall | Begründung |
| --- | --- | --- | --- |
| CER | ≤ 3 % | ≤ 10 % | Unterschiedliche Bildqualität |
| WER | ≤ 10 % | ≤ 25 % | Wortfehler beeinflussen die Suche |
| Modellnummern | ≥ 99 % | ≥ 99 % | Ein Zeichen kann eine andere Hardware identifizieren |
| Zahlen / Wert-Einheit-Paare | ≥ 99 % | ≥ 99 % | Technische Aussagen brauchen exakte Werte |
| Block-Lesereihenfolge | — | ≥ 95 % korrekt | Zusammenhänge erhalten |
| Tabellen-Zellzuordnung | — | ≥ 95 % korrekt | Struktur wichtiger als reiner Text |
| Unbelegte kritische technische Angaben | — | 0 tolerierte | Keine Halluzinationsfreigabe |
| Laufzeit | — | zunächst nur messen | Keine belastbare Schwelle vorhanden |

**Keine nachträgliche formale Bewertung historischer Versuche nach diesen Entwurfsgrenzen.** Der maskierte CUBX-Ausschnitt mit provisorischer Referenz ist keine bereits freigegebene Kategorie „sauberer Scan“. Werte von 99 % bei wenigen Vorkommen müssen mit absoluten Treffer-/Fehlerzahlen ergänzt werden.

## 10. Historische Nachweise (kein neuer Matrix-Pass)

| Nachweis | Bisher dokumentiertes Ergebnis | Bedeutung |
| --- | --- | --- |
| PDF-Vollanalyse | 29 PDFs / 5.064 Seiten, keine technischen Seitenfehler | Technische Analyse erfolgreich, **keine** Textqualitätsabnahme |
| Visuelle Goldstandard-Klassifikation | 7/14 Seiten geprüft | Bildtext, Leerseite und Layoutprobleme identifiziert; vollständige OCR-Referenzen fehlen |
| OCR-Ausführung CUBX S. 111 | 1.723 Zeichen, keine OCR-Laufzeitwarnung | Erkennung technisch möglich; Genauigkeit ungeprüft |
| OCR-Messwerkzeug | 8 Unit-Tests bestanden; Ruff erfolgreich | Rechen-/Review-Schutzlogik synthetisch geprüft |
| CUBX-PNG-Ausschnitt | `eng`: CER 2,32 %, WER 15,00 %; `eng+deu`: CER 2,51 %, WER 16,25 % | Reproduziert und bytegleich, **provisorische Referenz** |
| DocLayout-YOLO-CPU | USB S. 601: 1,8840 s; S. 606: 0,7302 s; Matrox S. 522: 0,7220 s | Ausschließlich Modellinferenzzeiten, keine OCR-Gesamtdauer |
| PR-#13-PDF-E2E | 112 Seiten, 114 Chunks, 114 echte Embeddings; 1 Test in 21,46 s bestanden | Isolierte technische Verkettung, **keine** CER-/WER-Qualitätsfreigabe |
| CUBX S. 112 | Weiße Leerseite; erzwungene OCR meldete „OCR lieferte keinen Text“ | Erwarteter Leerseiten-Sonderfall, kein belegter Verlust |
| Regions-/PSM-Experimente (Roadmap) | 3 CUBX-Regionen × 200/300 DPI × PSM 6/11 = 12 Kandidaten; PSM 7 separat für Titel-/Sloganzeilen | Keine freigegebenen regionsgleichen Referenzen und keine quantitative Rangfolge; mehr erkannte Zeichen bedeuten nicht höhere Genauigkeit |
| VLM-Einzelversuche (Roadmap) | Qwen3-VL 2B: 2/3 Titel-/Sloganzeilen; Gemma 3 12B: 3/3; bei zehn Badges ein inhaltlich bedeutsamer Gemma-Fehler | Visuelle Einzelbefunde, **keine** statistische Freigabe; Gemma las `3D Games Banned` statt `3D Games Bundled` |
| VLM-Vertrauensrisiko | Qwen erklärte eine Unterstrich-Abweichung unter Berufung auf nicht vorhandenen Bildkontext | Modellbegründungen und Modell-Confidence nicht als Quellenbeleg verwenden |

Quellen stehen in `docs/ocr-quality-plan.md`, Abschnitte 12–14; zusätzlich `docs/PROJECT_ROADMAP.md` und `docs/PR13_POSEIDON_INTEGRATION_TEST_2026-11-22.md` auf `integration/pdf-ocr-webdav-2026-11-21`. Kein historischer Befund wird hier als **neuer Testlauf** dargestellt.

## 11. Abbruchkriterien und Definition „fertig“

**Abbruch:** Sicherheits-/Isolationsverletzung, Veränderung des Originals, notwendige DB-/Worker-/Apply-Verarbeitung, unklare Modell-/Quellidentität oder methodisch ungültiger Referenzvergleich. Ein individueller OCR-Fehler oder schlechter Qualitätswert ist ein reguläres **Messergebnis**, kein pauschaler Abbruchgrund.

**Abnahme fertig:** Korpus und Methoden freigegeben; alle M-IDs `grün` oder jede Abweichung ausdrücklich als offen/rot mit Entscheidung dokumentiert; alle freigegebenen S-/O-IDs ausgeführt oder begründet zurückgestellt; Referenzen unabhängig geprüft; Metriken pro Seite, Kategorie und Variante dokumentiert; kritische technische Fehler sichtbar; reproduzierbare Laufzeiten/Parameter dokumentiert; Abschlussbericht mit begründeter Architektur-Empfehlung. **Dokumentierte Abweichung bedeutet nicht automatisch fachliche Erfüllung.**

## 12. Abnahmeprotokoll – noch nicht ausgefüllt

| Feld | Eintrag |
| --- | --- |
| Fachliche Freigabe dieser Matrix | ausstehend |
| Freigegebener Korpus | ausstehend |
| Freigegebene Schwellenwerte / Varianten | ausstehend |
| Datum / Prüferin | — |
| Quell- und Referenzversionen (nur lokal) | — |
| Geprüfter Repository-Commit | — |
| Ergebnis A–E | offen |
| Ausnahmen / Abweichungen / Entscheidungen | — |
| Freigabe zu OCR-Evaluation | **nicht erteilt** |
| Freigabe zu Indexierung/Fakten-/Produktivbetrieb | **nicht Gegenstand dieser Matrix** |

## 13. Vorschläge und Änderungsprotokoll

**Vorschläge (nicht eigenmächtig umsetzen):**
- Vor Qualitätsmessungen den Status bestehender Ground-Truth-Pakete prüfen; keine provisorische Referenz als endgültig behandeln.
- OCR-Güte und tabellarische/mehrspaltige Struktur getrennt beurteilen.
- Falls die bestehende Evaluationssoftware Zahlen-/Einheiten-Paare oder erfundene Angaben nicht getrennt zählt, die Lücke dokumentieren und eine spätere Implementierung gesondert freigeben.
- Erst bei ausdrücklich freigegebenem Bedarf neue Testautomatisierung oder Integration in die Importpipeline planen.

| Datum | Änderung | Begründung |
| --- | --- | --- |
| 22.11.2026 | Erster eigenständiger Matrixentwurf mit 5 Prüfgruppen und bestehenden technischen Testzuordnungen | Reproduzierbare OCR-Qualitätsbewertung unabhängig von der eingefrorenen PR-#15-Abnahme planen |
| 22.11.2026 | B9, B10, E4, E5 ergänzt und E2 als selektiver, regelbasierter VLM-Zweitkandidat präzisiert | Vom Betreiber ausdrücklich gewünschter Abgleich mit `PROJECT_ROADMAP.md`; dokumentierte PSM-/Regionsversuche und VLM-Fehlermodi in der späteren Qualitätsbewertung berücksichtigen. Keine Testausführung und keine fachliche Freigabe der Gesamtmatrix |
