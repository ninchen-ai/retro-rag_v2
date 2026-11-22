# OCR-Qualitätsbewertung – Retro-RAG V2

**Status:** Entwurf – zur fachlichen Freigabe  
**Datum:** 22.11.2026  
**Arbeitsbranch:** `feat/ocr-quality-evaluation`  
**Umfang:** ausschließlich isolierte Dateievaluation, kein Eingriff in die Importpipeline

## 1. Ziel und Entscheidungsfrage

Die Evaluation soll reproduzierbar feststellen, wie zuverlässig die vorhandene PDF-Textgewinnung technisch relevante Inhalte erkennt und strukturell korrekt wiedergibt. Ein erfolgreicher OCR-Lauf ist kein Qualitätsnachweis.

**Am Ende zu entscheiden:**
1. Reichen PyMuPDF und die bestehende Tesseract-Konfiguration für bestimmte Dokumentklassen aus?
2. Wann sind andere Sprach-/DPI-Einstellungen, regionale OCR oder DocLayout-YOLO-Unterstützung sinnvoll?
3. Bringt ein lokales Vision-LLM bei schwierigen Seiten nachweisbare Vorteile gegenüber Tesseract – insbesondere ohne erfundene technische Angaben?
4. Bei welchen Qualitätsproblemen wird eine Warnung, eine manuelle Prüfung oder eine Sperre der automatischen Weiterverarbeitung empfohlen?

Die Evaluation erteilt **keine** Freigabe zur Indexierung, Versionsaktivierung oder Faktenübernahme. Empfehlungen werden erst nach separater Architektur- und Umsetzungsfreigabe übernommen.

## 2. Verbindliche Abgrenzung

- `conventions.md` gilt unverändert: Originale bleiben unverändert, Quellen und Prüfstatus müssen nachvollziehbar sein, keine automatische Faktenfreigabe.
- Die am 22.11.2026 fachlich freigegebene PR-#15-Matrix liegt auf `feat/resumable-import-worker-2026-11-22` unter `docs/test_matrix_pr15.md`. Ihr **eingefrorener Umfang** von 13 aktiven IDs (11 M, 2 S) betrifft ausschließlich die technische Abnahme des Extraktionsworkers. Die OCR-Evaluation ändert weder diese Matrix noch PR #15.
- Keine Änderungen an vorhandenen Dateien, Tests, Variablen oder Funktionsnamen. Keine neuen Tests vor gesonderter Freigabe.
- Alle späteren Versuche ausschließlich gegen lokale Quelldateien, ohne Datenbank, Worker, Nextcloud-Schreibzugriff oder `--apply`.
- Keine Test-PDFs, vollständigen Fremdtexte, Referenztranskriptionen, privaten Quellkennungen oder PDF-Hashes ins öffentliche Repository committen.
- Ergebnisse und temporäre Dateien nur in einem isolierten lokalen Evaluationsverzeichnis. Keine Produktivfreigabe und keine Gate-Änderung.

## 3. Bestehende OCR-Verarbeitung – Ausgangspunkt

- PyMuPDF extrahiert PDF-Text unmittelbar, mit `sort=True`; `ocr_mode="off"` ist die Vorgabe.
- `auto` versucht Tesseract-OCR, wenn weniger als **40** native Textzeichen vorliegen **und** die geschätzte Bildabdeckung mindestens **50 %** beträgt. Einzelne Seiten können nach Sichtprüfung erzwungen werden.
- Aufruf: `page.get_textpage_ocr(full=True)`; Standard `eng+deu`, **200 DPI**, gültiger Bereich 100–300 DPI.
- Status: `native`, `empty`, `ocr`, `ocr_failed`. Bei OCR-Fehlern bleibt eventuell vorhandener nativer Text erhalten; Warnungen umfassen Laufzeitfehler, leere OCR-Ergebnisse und fehlenden extrahierbaren Text.
- Die Auswahlheuristik erkennt nicht zuverlässig jede fehlerhafte Textschicht, Vektorseite oder komplexe Layoutstruktur.
- DocLayout-YOLO liefert optional Layoutregionen, **keine OCR**. Die Vision-LLM-Erkennung ist ein separates Experiment und kein integrierter Standardpfad.
- Ein technisch erfolgreicher Lauf oder ein gutes Detektor-Confidence-Maß bedeutet keine korrekte Lesereihenfolge, Tabellenstruktur oder technische Aussage.

## 4. Testkorpus: zehn vorgeschlagene Seitenplätze

**Nur Kategorien und Anforderungen; keine konkrete Testseite ist ausgewählt oder freigegeben.** Nach Freigabe sollen folgende Seiten bereitgestellt werden, bevorzugt aus lokal vorhandenen, rechtmäßig nutzbaren Handbüchern/Datenblättern:

| ID | Kategorie | Bereitzustellende Seite / gewünschte Merkmale |
| --- | --- | --- |
| OQ-01 | Sauberer Scan | Einspaltiger Handbuch-Fließtext mit deutlich erkennbaren Zeichen |
| OQ-02 | Sauberer Scan | Technisches Datenblatt mit Überschriften und gutem Kontrast |
| OQ-03 | Schlechter Scan | Text mit Rauschen, Kompressionsartefakten oder geringem Kontrast |
| OQ-04 | Schlechter Scan | Schiefe oder unscharfe Seite, ggf. ungleichmäßige Ausleuchtung |
| OQ-05 | Zweispaltig | Zwei Spalten mit eindeutig kontrollierbarer Lesereihenfolge |
| OQ-06 | Tabelle | Einfache technische Spezifikationstabelle mit Zeilen und Spalten |
| OQ-07 | Komplexe Tabelle | Mehrzeilige Zellen, gruppierte Spalten oder Pin-/Registermatrix |
| OQ-08 | Kleine Schrift | Fußnoten, dicht gesetzte Beschriftungen oder sehr kleine Fonts |
| OQ-09 | Modellnummern | Mehrere Produkt-, Chip- und Teilenummern mit verwechselbaren Zeichen |
| OQ-10 | Zahlen/Einheiten | Spannungen, Taktfrequenzen, Größen, Vorzeichen und Dezimalzahlen |

Kategorien dürfen sich überlappen, die Fehlerursachen sollen aber möglichst breit abgedeckt sein. Nach Freigabe pro Seite: Dokumentbezeichnung, 1-basierte PDF-Seite, Dateihash und Seiten-/Renderidentität **nur lokal** dokumentieren. Zu diesem Zeitpunkt keine Seitenauswahl und keine Transkription.

## 5. Unabhängige Referenztexte

1. Die Originalseite visuell durch einen Menschen transkribieren, **nicht** aus der zu bewertenden OCR-Ausgabe übernehmen.
2. Für jede Seite Referenztext und, wo nötig, getrennte Referenz für Textblock-Lesereihenfolge sowie Tabellenzellen/-beziehungen anlegen.
3. Zahlen, Sonderzeichen, Modellkennungen, Vorzeichen, Einheiten und Dezimaltrennzeichen exakt übernehmen; unlesbare Passagen markieren statt raten.
4. Eingebetteten PDF-Text allenfalls als Kontrollhilfe nach visueller Prüfung verwenden; bei abweichendem Bildtext gilt die visuell überprüfte Quelle.
5. Referenz nach zweitem visuellen Abgleich versionieren und einfrieren, **bevor** OCR-Varianten verglichen werden.
6. Referenz und Ergebnis für CER/WER nach einer vorab festgelegten gemeinsamen Normalisierung (Unicode NFC, Whitespace) vergleichen; Kennungen, Zahlen und Einheiten nie bedeutungsverändernd normalisieren.

Vorhandene Goldstandard- oder OCR-Experimentdateien sind keine automatisch freigegebenen Referenzen. Besonders provisorische Transkriptionen bleiben bis zur manuellen Prüfung ausgeschlossen.

## 6. Vergleichsvarianten

- **A:** Native PyMuPDF-Extraktion als Baseline (falls Textschicht vorhanden).
- **B:** bestehende Tesseract-Konfiguration über PyMuPDF: `eng+deu`, 200 DPI.
- **C:** Tesseract `eng`, 200 DPI, identische Seiten.
- **D:** Tesseract `eng+deu`, 300 DPI.
- **E (optional, erst nach Freigabe):** DocLayout-YOLO-Regionserkennung plus darauf abgestimmte OCR; Modell, Gewichte, Renderstand und Regionenauswahl nachweisbar festhalten.
- **F (optional, erst nach Freigabe):** lokales Vision-LLM; Modell/Version/Prompt, Seitenausschnitte und Erfindungen protokollieren.

Varianten E/F sind **keine** Behauptung einer vorhandenen Integration. Fehlt eine reproduzierbare Ausführungsmöglichkeit, ist die Variante als `nicht getestet` auszuweisen, nicht stillschweigend zu ersetzen. Vergleich nur auf identischem Quellinhalt und derselben geprüften Referenz; Ganzseiten- und Regionsmessungen getrennt halten.

## 7. Metriken und Verfahren

| Metrik | Definition |
| --- | --- |
| CER | Levenshtein-Zeichendistanz / Anzahl Referenzzeichen |
| WER | Levenshtein-Wortdistanz / Anzahl Referenzwörter |
| Modellnummern-Trefferquote | Anteil vollständig und zeichengetreu erkannter Referenz-Vorkommen |
| Zahlen-Trefferquote | Anteil korrekt erkannter Referenz-Zahlen einschließlich Vorzeichen/Dezimaltrennzeichen |
| Zahlen-/Einheiten-Trefferquote | Anteil korrekt erkannter vollständiger Wert-Einheit-Paare |
| Kritische erfundene Angaben | Zahl und Art zusätzlicher, nicht durch die Vorlage belegter Modell-/Zahlen-/Einheitenbehauptungen |
| Lesereihenfolge | Anteil korrekt aufeinanderfolgender Referenz-Textblockübergänge; eindeutig definierte Blockgrenzen erforderlich |
| Tabellenstruktur | Anteil korrekt rekonstruierter Referenz-Zellinhalte **mit** Zeilen-/Spaltenzuordnung; einfache Texterkennung allein genügt nicht |
| Laufzeit pro Seite | Sekunden pro Seite/Variante bei dokumentierter CPU/GPU, Engine, DPI und vorab geklärter Warm-/Kaltstartmessung |
| Warnungen und Ausfälle | Status, Anzahl, Art, fehlende Textbereiche und manuelle Nachprüfung |

Fehlerquoten und Trefferquoten sowohl je Seite als auch je Kategorie ausweisen. Wo eine Metrik nicht sinnvoll definiert ist (z. B. Tabellenstruktur auf Fließtext), `nicht anwendbar` statt Null melden. CER/WER können bei vielen Einfügungen über 100 % liegen. Durchschnittswerte dürfen einzelne kritische Fehler nicht verdecken.

## 8. Schwellenwerte – **sämtlich Vorschlag, zur Freigabe**

| Bereich | Vorgeschlagener Wert | Begründung |
| --- | --- | --- |
| CER, saubere Scans | ≤ 3 % | Hohe Zeichenqualität sollte bei gutem Kontrast erreichbar sein |
| CER, schwierige Scans | ≤ 10 % | Erlaubt Bildschwierigkeiten, ist aber keine fachliche Freigabe |
| WER, saubere Scans | ≤ 10 % | Begrenzt Wortfehler für die spätere Volltextsuche |
| WER, schwierige Scans | ≤ 25 % | Separater Toleranzbereich für schlechte Ausgangsqualität |
| Modellnummern | ≥ 99 % exakt | Bereits ein Zeichen kann eine andere Hardware bezeichnen |
| Zahlen | ≥ 99 % exakt | Zahlenfehler können technische Aussagen verfälschen |
| Wert/Einheit-Paare | ≥ 99 % exakt | Richtiger Zahlenwert ohne richtige Einheit ist nicht ausreichend |
| Lesereihenfolge | ≥ 95 % korrekte Blockübergänge | Vertauschte Blöcke verfälschen den Kontext |
| Tabellenstruktur | ≥ 95 % korrekte Zellzuordnungen | Zell-/Spaltenbeziehung ist für technische Fakten entscheidend |
| Kritische erfundene Angaben | 0 tolerierte Fälle | Nicht belegte technische Werte dürfen nicht als korrekt gelten |
| Laufzeit | zunächst **kein** harter Grenzwert | Erst gemessene Zeiten unter reproduzierbarer Hardwarebelastung bewerten |

Bei nur zehn Seiten sind Prozentwerte besonders für seltene Modellnummern statistisch wenig aussagekräftig. Deshalb zusätzlich Rohzähler und jeden kritischen Fehler ausweisen. **Zur Freigabe:** Ein bekannter Fehler an einer sicherheits- oder funktionsrelevanten technischen Kennung löst eine manuelle Prüfungsempfehlung aus, selbst bei sonst guter CER/WER.

## 9. Abbruchkriterien

Gesamtlauf abbrechen, wenn die Isolation oder Unveränderlichkeit von Quellen nicht gewährleistet ist, Datenbank/Worker/`--apply` erforderlich würden, die Engine-/Modellversion nicht nachvollziehbar ist oder der Referenzvergleich methodisch ungültig wird. Einzelne unlesbare Seiten nach dokumentierter Entscheidung auswertungsfrei stellen oder Ersatzseite **erst nach erneuter Freigabe** vorschlagen.

Schlechte OCR-Qualität, fehlgeschlagene Erkennung und eine dokumentierte Warnung sind **reguläre Messergebnisse**, kein Anlass, den gesamten Vergleich zu stoppen.

## 10. Definition von „fertig“

- Der endgültige Korpus sowie Referenz-, Varianten- und Schwellenregeln sind fachlich freigegeben.
- Für jede freigegebene Seite liegt eine unabhängige, manuell überprüfte Referenz vor.
- Jede freigegebene Variante wurde ausgeführt oder ihr Ausfall/Nichtvorhandensein begründet.
- Alle anwendbaren Qualitätsmetriken und Laufzeiten sind pro Seite/Variante dokumentiert.
- Grenzwertverletzungen, kritische Fehlablesungen und Halluzinationen sind sichtbar aufgelistet.
- Eine reproduzierbare Gegenüberstellung enthält Engine-/Modellstände, Parameter, Quell- und Referenzidentität.
- Ein Abschlussbericht empfiehlt begründet, welche OCR-Strategie bei welchen Seitentypen sinnvoll ist und welche Fälle manuelle Prüfung benötigen.
- Keine bestehende Pipeline, kein Test, keine Datenbank und keine produktive Konfiguration wurden verändert.

## 11. Noch ausstehende Freigaben

**Vor jeder Evaluation separat bestätigen:** Auswahl der konkreten zehn Seiten, Referenzkonventionen, Vergleichsvarianten E/F, die vorgeschlagenen Qualitätsgrenzen sowie Bewertung der Strukturmetriken.

**STOPP:** Vor Freigabe weder Testseiten tatsächlich auswählen noch Referenztexte erzeugen, Evaluationsversuche ausführen, Tests schreiben oder die Importpipeline ändern.

## 12. Bezugsdokumente

- `conventions.md` – verbindliche Projektregeln.
- `docs/test_matrix_pr15.md` auf Branch `feat/resumable-import-worker-2026-11-22` – eingefrorene PR-#15-Abnahme; **nur Referenz, nicht ändern**.
- `docs/OCR_QUALITY_EVALUATION.md` – vorhandene Qualitätsmessung und provisorische Baselines.
- `docs/PDF_OCR_STAGE4.md` – vorhandene Tesseract-/PyMuPDF-Seiten-OCR.
- `docs/PDF_LAYOUT_ROUTING_DOCLAYOUT_YOLO.md` – Trennung von Text, Layout und Tabellenstruktur.
