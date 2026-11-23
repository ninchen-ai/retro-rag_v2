# OCR-Qualitätsbewertung – Retro-RAG V2

**Status:** Entwurf – zur fachlichen Freigabe; bisherige Testergebnisse berücksichtigt  
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

**Nur Kategorien und Anforderungen für die neue Bewertung; keine konkrete Seite für den neuen Zehner-Korpus ist ausgewählt oder freigegeben.** Bereits zuvor unabhängig visuell untersuchte Seiten und lokale Versuchsdaten werden als vorhandene Baseline dokumentiert; ihre erneute Auswahl für den neuen Korpus ist nicht vorweggenommen. Nach Freigabe sollen folgende Seiten bereitgestellt werden, bevorzugt aus lokal vorhandenen, rechtmäßig nutzbaren Handbüchern/Datenblättern:

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

## 13. Historische Test- und Messbefunde als verbindliche Ausgangslage

Dieser Abschnitt dokumentiert **bereits vorhandene** Ergebnisse des Entwicklungsbranches und der dort referenzierten Poseidon-Läufe. Er ist weder eine erneute Ausführung noch die Freigabe des zukünftigen Testkorpus. Frühere Ergebnisse bleiben im jeweiligen Geltungsbereich gültig und werden nicht stillschweigend als vollständige OCR-Qualitätsabnahme bezeichnet.

### 13.1 PDF-Survey und technische Baseline (10.11.2026)

- Der schreibfreie Vollbericht untersuchte **29/29 PDFs mit 5.064/5.064 Seiten**, ohne technische Seiten- oder Tabellenerkennungsfehler. Inhaltsgleiches Duplikat herausgerechnet: **28 eindeutige PDFs / 4.953 Seiten**.
- Unter diesen eindeutigen Seiten waren **22 ohne extrahierten Text**, **26 mit weniger als 40 Zeichen**, **4 heuristische OCR-Kandidaten** und **78 Seiten mit Mehrspaltenverdacht**. Heuristische Kandidaten sind keine verifizierten OCR-Fälle.
- Auf der Gesamtmenge wurden **3.720 PyMuPDF-Tabellenerkennungen** gezählt; diese sind keine bestätigten, korrekt rekonstruierten Tabellen.
- Der Vollbericht enthält keine belastbaren Laufzeitwerte für die OCR-Bewertung. Die technische Fehlerfreiheit belegt keine korrekte Lesereihenfolge oder korrekte technische Werte.

Quelle: `docs/PDF_QUALITY_BASELINE_2026-11-10.md`.

### 13.2 Bereits überprüfte Seitenklassifikationen und Layoutprobleme

- Die vorhandenen **14 Goldstandard-Prüfpakete** wurden vorbereitet; **7 Seiten** sind laut dokumentiertem Review visuell geprüft, nicht sämtliche 14.
- `cubx-103.pdf` S. 111: bildbasierte Werbeseite, OCR-Bedarf visuell bestätigt; S. 112: tatsächlich leere Seite, OCR nicht erforderlich.
- `3C905CX.pdf` S. 1 und DirectX-Guide S. 2: bildbasierte Titelseiten mit begründetem OCR-Bedarf.
- `usb_20.pdf` S. 601 und 606: `sort=True` verschränkt die beiden Indexspalten; korrekte Folge ist linke Spalte vollständig, danach rechte. **Kein OCR-Problem, sondern Lesereihenfolge/Struktur**.
- `MGA-G200_199811.pdf` S. 522: Pinmatrix verliert in einfacher Textrepräsentation die verlässliche 2D-Zell-/Signalbeziehung. Verlustfreies Zeichen-Chunking behebt dies nicht.
- Vorhandene Goldstandard-Review-Urteile zu Seitenklassifikation dürfen als historische Befunde genutzt werden; sie ersetzen **keine unabhängig verifizierte vollständige Texttranskription** für CER/WER.

Quelle: `docs/PDF_GOLDSTANDARD_REVIEW.md`.

### 13.3 Tesseract-Stufe 4: technisch erfolgreich, fachlich offen

- Für `cubx-103.pdf` S. 111 dokumentiert: **0 native Zeichen**, **94,26 % Bildabdeckung**; Tesseract 5.5.0 über PyMuPDF mit `eng+deu`, **200 DPI** lieferte **1.723 Zeichen** und keine OCR-Laufzeitwarnung.
- Der Kopfbereich enthielt erkennbare Fehler/Artefakte. Dies ist **kein** Nachweis einer ausreichenden Texterkennungsqualität oder einer Freigabe zur Indexierung.
- Vorhandene OCR-Funktionstests (synthetische PDFs/Mocks) prüfen Kontrollfluss und Fehlerverhalten, keine CER/WER an echten Scans.

Quelle: `docs/PDF_OCR_STAGE4.md`.

### 13.4 Vorläufige OCR-Qualitätsmessung und Reproduzierbarkeit (12.11.2026)

Das vorhandene Evaluationswerkzeug wurde auf Poseidon durch **8 bestandene Tests** und erfolgreiche Ruff-Prüfung technisch überprüft; diese Tests verwendeten synthetische Texte.

Für einen **maskierten PNG-Ausschnitt** aus der CUBX-Seite 111 mit Tesseract PSM 6 wurden folgende Werte gegen eine **provisorische, nicht abschließend freigegebene Referenz** reproduziert:

| Sprachvariante | CER | WER | Nachweisstatus |
| --- | ---: | ---: | --- |
| `eng` | 2,32 % | 15,00 % | Poseidon-Messung; Text später bytegenau gegen Vergleichsdatei bestätigt |
| `eng+deu` | 2,51 % | 16,25 % | Poseidon-Messung; Text später bytegenau gegen Vergleichsdatei bestätigt |

**Folgerungen:** In diesem **einen Ausschnittversuch** war `eng` besser als `eng+deu`. Das ist keine globale Sprachkonfigurationsempfehlung. Die hier beobachteten WER-Werte überschreiten den für *saubere Scans* vorgeschlagenen Grenzwert von 10 %: 15,00 % bzw. 16,25 % sind größer als der Entwurfswert von 10 %. Der Ausschnitt ist aber keine nach den neuen Regeln als „sauberer Scan“ klassifizierte, freigegebene Testseite; daher **keine formale Grenzwertverletzung der neuen Evaluation**.

Die Reproduzierbarkeit belegt nur dieses PNG-/PSM-6-Experiment, **nicht** eine Ganzseiten-OCR gegen die SHA-256-verifizierte Original-PDF bei 200 DPI. Identische Ausgangsregion und endgültig manuell bestätigte Referenz bleiben Voraussetzung für einen belastbaren Vergleich.

Das vorhandene Werkzeug berechnet bereits **CER, WER und `critical_term_recall`** (exakte Vorkommen markierter Fachbegriffe, ohne Unterscheidung von Groß-/Kleinschreibung). Dieses Merkmal berücksichtigt noch keine zusätzlich **erfundenen** kritischen Angaben. Die im Plan getrennt vorgeschlagenen Metriken für Zahlen-/Einheiten-Paare und erfundene Angaben sind daher **Evaluationsanforderungen**, nicht als implementiert zu behaupten. Bestehende Tests bleiben unberührt.

Quelle: `docs/OCR_QUALITY_EVALUATION.md`.

### 13.5 DocLayout-YOLO und Strukturversuche (10.–11.11.2026)

Auf Poseidon wurden drei gezielte CPU-Detektionsläufe mit dem bereits vorhandenen Goldstandard-Bildmaterial durchgeführt:

| Seite | Gemeldete Inferenzzeit | Detektionen | Fachliche Grenze |
| --- | ---: | --- | --- |
| USB 2.0 S. 601 | 1,8840 s | 8 Boxen | Zwei Spalten als Regionen erkennbar, Konflikt `title`/`abandon` |
| USB 2.0 S. 606 | 0,7302 s | 4 Boxen | Spalten erkennbar, aber damit keine automatisch bestätigte Leseordnung |
| Matrox G200 S. 522 | 0,7220 s | 7 Boxen | Pinmatrix gleichzeitig als `table` und `figure` klassifiziert |

Die Zeiten messen **nur die dokumentierten YOLO-Inferenzläufe**, nicht OCR-/Layout-Gesamtverarbeitung. Die Konflikterkennung bestand später **16 Unit-Tests** und Ruff; dies ist kein Zellstruktur- oder OCR-Gütesiegel.

Die anschließenden USB-Spaltenadapter-Ausgaben sind als `REVIEW_REQUIRED` und `approved=false` dokumentiert. Neuere Vorschlagsausgaben ordnen `Index` auf S. 601 am Anfang ein und führen `ClearHubFeature()` auf S. 606 vor `clock model (continued)`; die fachliche Abnahme und die semantische Gliederung des Indexes sind weiterhin offen.

Quellen: `docs/PDF_DOCLAYOUT_BENCHMARK.md`, `docs/PDF_LAYOUT_CONFLICTS_V2.md`, `docs/PDF_COLUMN_READING_ORDER_V2.md`.

### 13.6 Konsequenzen für den noch freizugebenden Evaluationsumfang

1. **Keine Wiederholung nur zum Nachweis technischer Ausführbarkeit:** Bestehende PDF-, OCR- und YOLO-Smoke-Tests als Baseline anführen. Erneute Ausführung nur, wenn sie für vergleichbare Messbedingungen oder eine spätere Regression erforderlich ist.
2. **Vorhandenes Goldstandard-Material vorrangig prüfen:** Die bereits dokumentierten Fälle (u. a. CUBX, 3Com, USB, Matrox) sind **Kandidaten**, keine automatisch für den neuen Zehner-Korpus ausgewählten Seiten. Zuerst den tatsächlichen lokalen Referenzstatus verifizieren; fehlende/ungeprüfte Transkriptionen bleiben offen.
3. **OCR-Güte und Layoutgüte trennen:** Die USB-Spalten und die Matrox-Pinmatrix sind primär Struktur- und nicht OCR-Fälle. Für die zehn geplanten Seitenplätze gegebenenfalls echte Bildtextfälle und separate Layoutkontrollen unterscheiden.
4. **Sprachen gezielt vergleichen:** `eng` und `eng+deu` sind wegen der dokumentierten unterschiedlichen Ergebnisse auf identischem Inhalt einzubeziehen; keine Verallgemeinerung aus nur einem Ausschnitt.
5. **Kritische technische Aussagen vorrangig bewerten:** Genauigkeit von Modellnummern, Zahlen und Wert-Einheit-Paaren sowie erfundene Angaben getrennt von CER/WER ausweisen; `critical_term_recall` als vorhandene Messmöglichkeit nutzen.
6. **Zeitvergleich methodisch sauber halten:** Vorhandene reine YOLO-Inferenzzeiten und OCR-Durchlaufzeiten dürfen nicht als gleiche Messgröße gegenübergestellt werden.
7. **Schwellenwerte bleiben Vorschläge:** Auch nach Einbeziehung der älteren Ergebnisse sind die Grenzwerte in Abschnitt 8 weiterhin **zur Freigabe** und nicht nachträglich für die alten Versuche anzuwenden.
8. **Offene technische Integrationen nicht vortäuschen:** Vision-LLM- und layoutgestützte OCR-Varianten vor einem Vergleich auf Implementierung und identischen Quellen-/Referenzstand prüfen; bestehende Abnahme- und PR-#15-Tests weder ersetzen noch erweitern.

**Stand nach Übernahme dieser Befunde:** Ausschließlich der Plan wurde aktualisiert. Es wurden keine zusätzlichen Seiten ausgewählt, keine Referenztexte angelegt und keine Messläufe gestartet.

## 14. Ergänzende Branchprüfung und PR-#13-Integrationsnachweise (22.11.2026)

**Abgeglichene Dokumentationsstände:**
- `feat/pdf-ocr-stage4/docs`
- `integration/pdf-ocr-webdav-2026-11-21/docs`
- `feat/ocr-quality-evaluation/docs`

Die gemeinsamen OCR-, Goldstandard-, Qualitätsbaseline-, DocLayout- und Spaltenordnungsdateien haben auf diesen Branches denselben Git-Blob-SHA; sie liefern deshalb **keine drei unabhängigen Beweisquellen**. `docs/OCR_QUALITY_EVALUATION.md` liegt nicht auf `feat/pdf-ocr-stage4`, aber identisch auf den beiden anderen Branches. **Neu und für den OCR-Plan relevant** ist besonders `docs/PR13_POSEIDON_INTEGRATION_TEST_2026-11-22.md` auf dem Integrationsbranch.

### 14.1 Reale technische PDF/OCR-Verkettung

Der auf Poseidon dokumentierte isolierte PR-#13-Test mit der **echten** `cubx-103.pdf` (112 Seiten) bestätigte:
- SHA-verifizierte lokale PDF-Datei und seitenweise Verarbeitung mit `ocr_mode=auto`, `ocr_pages={111}`.
- **114 Chunks**, OCR auf Seite **111**, **0 fehlgeschlagene OCR-Seiten**, **keine Warnungen**. Die bekannte leere Seite **112** wurde bewusst nicht zur OCR gezwungen.
- **114 echte** lokale Ollama-`nomic-embed-text`-Embeddings mit **768 Dimensionen** wurden im isolierten, nur transaktional geöffneten Testcluster erzeugt/geschrieben.
- Der Test bestand mit **`1 passed in 21.46s`**. Das ist die **gesamte E2E-Testdauer** einschließlich anderer Arbeitsschritte, **keine OCR-Zeit pro Seite**.
- Die unabhängige Nachkontrolle fand das externe Write-Gate geschlossen sowie keine verbliebenen Dokument-, Versions-, Job-, Chunk- oder Embedding-Zeilen. Das zuvor verwendete isolierte Container-Testsystem wurde später entfernt.
- Die Schlussregression des Integrationsstands `1f311b3` ergab **174 passed, 16 skipped** und Ruff **PASS**. Diese Regression ist ein technischer Nachweis und keine neue fachliche OCR-Messung.

**Grenze:** Weder 114 Chunks noch 114 Embeddings bestätigen korrekte Textinhalte, Lesereihenfolge, Tabellenstruktur oder technisch richtige Fakten. Es gibt weiterhin **keine endgültig freigegebene Vollseiten-CER/WER-Referenz für CUBX S. 111**. Der E2E-Nachweis berührt nicht die eingefrorene PR-#15-Testmatrix.

### 14.2 Leerseitenversuch als Beispiel zur Warnungsbewertung

Bei einem separaten realen PDF-Vorschaulauf wurde die tatsächlich leere CUBX-Seite **112 absichtlich zusätzlich zur OCR gezwungen**. Das führte zur erwartbaren Warnung `Seite 112: OCR lieferte keinen Text`, bei erfolgreichem Vorschau-Exitcode 0. Ein früherer Kontrolllauf ausschließlich mit S. 111 zeigte dagegen `ocr_failed_pages=[]` und `warnings=[]`.

Die Leerseitenwarnung ist **kein belegter Verlust relevanten Texts und keine unbehobene Regression**. Der neue Evaluationsplan muss deshalb:
1. **Richtig erkannte Leerseite** von `ocr_failed` oder fehlendem Text einer nichtleeren Seite unterscheiden.
2. Den Nenner für OCR-Güte nur aus Seiten mit tatsächlich relevantem Referenztext bilden; Leerseiten separat als Routing-/Warnungsfall ausweisen.
3. OCR-Warnungen stets mit visueller Seitenklassifikation bewerten, nicht nur zählen.

### 14.3 Auswirkungen auf die geplanten Versuche

- Bereits bestandene technische E2E-/Rollback-/Regressionstests **nicht nochmals als neue Qualitätsmessung aufführen**.
- Den noch fehlenden **Vollseiten-Ground-Truth-Abgleich** und die Genauigkeit von Modellnummern/Zahlen/Einheiten stärker priorisieren als einen weiteren allgemeinen OCR-Smoke-Test.
- Eine **Leerseiten-/Routing-Kontrolle** getrennt vom 10-seitigen Kernkorpus vorsehen, unter Nutzung bereits visuell geprüfter historischer Befunde; dies ist **keine Auswahl einer neuen Testseite**.
- Für einen fairen Laufzeitvergleich **reine OCR-Dauer, Layout-Inferenz und E2E-Gesamtdauer getrennt messen**.
- Vollständige OCR-Qualitätsbewertung, strukturierte Tabellen-/Pinmatrixprüfung und Vision-LLM-Gegenprüfung bleiben offen und freigabepflichtig.

Quelle: `docs/PR13_POSEIDON_INTEGRATION_TEST_2026-11-22.md` auf `integration/pdf-ocr-webdav-2026-11-21`. Historische Dokumentation bleibt unverändert; alle hier genannten Nachweise gelten nur für die ausdrücklich dokumentierten Testläufe.

## 15. Freigegebener geplanter Ablauf (22.11.2026)

**Freigabestatus:** Der nachfolgende **fünfphasige Ablaufplan** wurde am **22.11.2026** vom Betreiber ausdrücklich zur Aufnahme in dieses Dokument freigegeben. Die Freigabe gilt ausschließlich für die **Planung und Reihenfolge der Arbeitsschritte**. Sie ist **keine** Freigabe zur Auswahl konkreter Seiten, Erstellung von Referenzen, Durchführung von OCR-/Layout-/Vision-LLM-Versuchen, Änderung von Tests oder produktiver Verarbeitung.

**Arbeitsbranch:** `feat/ocr-quality-evaluation`  
**Geltungsbereich:** Isolierte Auswertung lokaler Dateien, ohne Datenbank, Worker, `--apply`, Nextcloud-/Archiv-/Originaländerung oder Veränderung des Write-Gates.  
**Verbindliche Abnahme:** `docs/ocr_quality_test_matrix.md` mit 29 eingefrorenen IDs (23 M, 3 S, 3 O). Die gesonderte PR-#15-Abnahme bleibt vollständig unberührt.

| Phase | Schwerpunkt | Zuordnung zur eingefrorenen Matrix | Geplante Tätigkeit |
| --- | --- | --- | --- |
| 1 | Isolation und Referenzgrundlage | A1–A5 | Lokale, schreibgeschützte Quellen und Ausgaben abgrenzen; Quell-/Renderidentität nachweisen; unabhängige, zweitgeprüfte Referenztexte und deren Prüfstatus festlegen. Ungeprüfte Referenzen nicht bewerten. |
| 2 | OCR-Routing und Texterkennung | B1–B10 | Native PyMuPDF-Ausgabe und OCR-Routing vergleichen; Leerseiten separat klassifizieren; CER/WER sowie `eng` gegen `eng+deu`, 200 gegen 300 DPI und geeignete PSM-6/7/11-Regionen vergleichen. Ganzseiten- und Regionsmessungen nur mit identischem Textumfang gegenüberstellen. |
| 3 | Technische Genauigkeit und Struktur | B6–B8, C1–C4 | Modellnummern, Zahlen, Einheiten und unbelegte zusätzliche technische Angaben einzeln bewerten; Lesereihenfolge, Tabellenzellen und Pin-/Registermatrizen unabhängig von OCR-Zeichenwerten prüfen. Klassenkonflikte dem Review zuordnen. |
| 4 | Optionale Methoden und Schutzbewertung | E1–E5 | Machbarkeit und Grenzen von DocLayout-YOLO-gestützter Regions-OCR und selektivem regelbasiertem Vision-LLM-Zweitkandidaten prüfen. E1–E3 nur bei gesonderter Freigabe ausführen, E4 als Soll-Prüfung behandeln; E5 als verpflichtende Schutzbewertung ohne implizite VLM-Ausführungsfreigabe berücksichtigen. |
| 5 | Bewertung und Abschluss | D1–D5 | Variantenvergleich, Reproduzierbarkeit, getrennte Zeitmessung (OCR/Layout/E2E), Qualitätsgrenzen, Einzelabweichungen und manuellen Reviewbedarf berichten; Empfehlungen für spätere OCR-Strategien begründen, ohne automatische Indexierungs-/Faktenfreigabe. |

**Geltende Reihenfolge:** Erst die noch offenen Einzelentscheidungen einholen (zehn Seitenkategorien und konkrete Seiten, Referenz-/Normalisierungs-/Strukturregeln, A–D-Varianten, Schwellenwerte, optionale E/F-Ausführung), danach die jeweilige fachlich freigegebene Phase durchführen. Die bereits dokumentierten historischen Poseidon-, PR-#13-, Tesseract- und DocLayout-Ergebnisse bleiben Ausgangsbefunde, aber keine neu bestandenen Matrixprüfungen.

**Stoppregel:** Bis zu den gesonderten Ausführungsfreigaben bleiben alle 29 Matrix-IDs im bisherigen Status. Keine neuen Testfälle, keine Codeänderungen, keine Messläufe und keine Änderung der Matrix oder der PR-#15-Unterlagen.

**Freigabeprotokoll:** 22.11.2026 – Nutzerfreigabe zur Aufnahme des geplanten fünfphasigen Ablaufs in `docs/ocr-quality-plan.md`. **Nur der Ablaufplan ist freigegeben; die konkreten Evaluationsschritte bleiben freigabepflichtig.**

## 16. A3 – Festgelegtes Verfahren für den manuellen Referenzabgleich (23.11.2026)

**Entscheidung des Betreibers vom 23.11.2026:** Für A3 wurde **Variante A** gewählt: Zwei **zeitlich getrennte manuelle Prüfdurchgänge durch dieselbe Person**. Diese Festlegung erlaubt die Vorbereitung des Prüfverfahrens, jedoch ausdrücklich **noch keine Auswahl konkreter Seiten und keine Erstellung von Referenztexten**.

### Verfahrensregeln für spätere, gesondert freizugebende Referenzen

1. Erstdurchgang: Sichtbaren Originalinhalt manuell erfassen, ohne OCR-Ausgaben als Referenz zu übernehmen; unlesbare Stellen sichtbar kennzeichnen statt raten.
2. Zweitdurchgang: Nach dokumentiertem zeitlichem Abstand das Original unabhängig vom ersten Durchgang **erneut visuell kontrollieren**; Datum/Uhrzeit beider Durchgänge und festgestellte Korrekturen lokal protokollieren. Ein Mindestabstand wurde **nicht festgelegt** und darf nicht unterstellt werden.
3. Besondere Zeichenfolgen (Modellnummern, Zahlen, Vorzeichen, Dezimaltrennzeichen, Einheiten) und bei Bedarf Blockreihenfolge/Zellbeziehungen einzeln prüfen.
4. Referenz erst nach vollständigem zweiten visuellen Abgleich versionieren und gegen spätere stille Änderungen schützen; vor diesem Zeitpunkt `review_status=unreviewed` beibehalten. Eine spätere technische Bewertung darf daraus keine automatische Indexierungs- oder Faktenfreigabe ableiten.
5. Alle Texte, Seitenbilder, Quellhashes und personenbezogenen Prüfprotokolle verbleiben im isolierten lokalen Evaluationsbereich; keine Übernahme ins öffentliche Repository.

### Explizite Einschränkung der Unabhängigkeit und A3-Abnahme

**Die zweite Kontrolle erfolgt nicht durch eine andere Person.** Dadurch ist sie zeitlich, aber **nicht personell unabhängig**; eigene Fehler oder Vorannahmen können in beiden Durchgängen bestehen bleiben. Dies ist eine bewusste methodische Einschränkung und **kein gleichwertiger Nachweis einer unabhängigen Zweitprüfung**.

Die eingefrorene Matrix führt A3 als „Unabhängiger Referenztext“ mit Zweitprüfung. Ihre Akzeptanzkriterien werden durch diese Dokumentation **nicht geändert oder stillschweigend als erfüllt bewertet**. Ob ein anhand von Variante A erstellter Referenztext A3 trotz der eingeschränkten Unabhängigkeit fachlich erfüllen darf, ist **vor einer späteren A3-Abnahme ausdrücklich zu entscheiden und als Abweichung zu dokumentieren**; andernfalls bleibt A3 offen. Eine echte Zweitprüfung durch eine andere Person kann diese Einschränkung später beheben.

**Status:** Prüfverfahren Variante A fachlich festgelegt; A3-Abnahme weiterhin **offen**. Der am 23.11.2026 freigegebene Korpusrahmen OQ-01 bis OQ-10 ist hiervon unabhängig; **keine konkreten Seiten freigegeben**, keine Referenzen erzeugt und keine OCR-Evaluation ausgeführt. PR #15 sowie die eingefrorene OCR-Testmatrix bleiben unverändert.
