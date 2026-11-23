# Testmatrix – OCR-Qualitätsbewertung (Retro-RAG V2)

**Status:** Abnahmeumfang fachlich freigegeben und eingefroren am 22.11.2026; konkrete Testdurchführung nicht freigegeben, technische Abnahme ausstehend  
**Stand:** 23.11.2026 – historische Nachweise und A5-Zwischenfreigaben aller zehn OQ-Seitenkandidaten dokumentiert  
**Branch:** `feat/ocr-quality-evaluation`  
**Grundlage:** `docs/ocr-quality-plan.md`, `docs/OCR_QUALITY_EVALUATION.md`, `conventions.md` sowie `docs/PROJECT_ROADMAP.md` auf `integration/pdf-ocr-webdav-2026-11-21` (historischer Stand 21./22.11.2026)  
**Umgebung für spätere Versuche:** Poseidon, ausschließlich isolierte lokale Dateien

## 1. Geltungsbereich und Regeln

Diese Matrix ist **eigenständig**. Die fachlich eingefrorene PR-#15-Abnahme unter `docs/test_matrix_pr15.md` auf `feat/resumable-import-worker-2026-11-22` umfasst den Extraktionsworker und bleibt **unberührt**.

1. Der **Abnahmeumfang von 29 IDs (A1–A5, B1–B10, C1–C4, D1–D5, E1–E5) ist mit ausdrücklicher Freigabe am 22.11.2026 eingefroren**. Prioritäten und Szenariobeschreibungen bleiben ohne gesonderten Änderungsbeschluss unverändert. Neue IDs oder Prioritätsänderungen benötigen eine neue ausdrückliche Freigabe mit Datum und Begründung im Änderungsprotokoll.
2. Diese Freigabe betrifft **ausschließlich den Prüfumfang**, nicht die konkrete Auswahl der zehn Seiten, die Ground-Truth-Erstellung, die Messverfahren-/Schwellenwertfreigabe oder die Testausführung. Bis zu separaten Freigaben keine konkreten Testseiten auswählen, keine Referenztexte erstellen und keine OCR-/Layout-/VLM-Evaluationsläufe durchführen.
3. Keine bestehende Datei, Funktion, Variable oder bestehenden Tests verändern; keine neuen Tests eigenmächtig schreiben.
4. Evaluation ausschließlich gegen lokale Kopien/Dateien: **keine Datenbank, kein Worker, kein `--apply`, kein Index, keine Änderungen an Nextcloud, Archiv, Originalen oder Write-Gate**.
5. Die Matrix unterscheidet **vorhandene technische Testabdeckung** von **fachlicher Messung am freigegebenen Korpus**. Ein bestandener Unit-Test ist keine bestandene OCR-Qualitätsmessung.
6. Ergebnisse und abweichende Befunde je ID dokumentieren. Noch fehlende oder nur teilweise vorhandene Abdeckung wird nicht automatisch grün.
7. Keine PDF-Originale, OCR-Rohtexte, vollständigen Referenztexte, private Quellkennungen, Quellhashes oder Berichte mit solchen Angaben in Git committen. Nur anonymisierte, aggregierte Abnahmeprotokolle dürfen ins Repository.
8. Eine Qualitätsabnahme berechtigt **nicht** zur Indexierung, Faktenfreigabe oder Produktionsschaltung.

**Priorität:** M = muss, S = sollte, O = optional.  
**Status:** `offen`, `grün`, `rot`, `entfällt`; **alle neuen Abnahme-IDs beginnen mit `offen`**.  
**Vorhandene Abdeckung:** direkt = vorhandener Test für einen technischen Teilaspekt; teilweise = nur angrenzende Prüfung; keine = kein belegter Test. Das ersetzt keinen Laufnachweis der neuen Matrix.

**Eingefrorener Matrixumfang: 29 IDs – 23 × M, 3 × S, 3 × O.** B9, B10, E4 und E5 sowie die E2-Präzisierung wurden vor der Freigabe aufgenommen. **Nicht** mitfreigegeben: konkrete Testseiten, Referenztexte, die vorgeschlagenen Schwellenwerte und die Ausführung. E1–E3 bleiben optionale, E4 eine Soll-Prüfung; E5 verpflichtet zur Schutzbewertung, autorisiert aber keine VLM-Ausführung.

## 2. Freigaben vor der Ausführung

| Freigabepunkt | Entscheidung | Status |
| --- | --- | --- |
| Zehn Kategorien OQ-01 bis OQ-10 als Korpusrahmen | 23.11.2026: Kategorien fachlich freigegeben; keine Seiten ausgewählt | freigegeben |
| Konkrete zehn Originalseiten und Seiten-/Renderidentitäten | **OQ-01 bis OQ-10 als zehn konkrete Seitenkandidaten am 23.11.2026 fachlich zwischenfreigegeben**; bei OQ-04 ausschließlich linke Buchseite 100, moderate Beleuchtungsabweichung und Bundkrümmung. Lokale Original-/Seiten-/Renderidentität, vollständige Korpus- und A5-Abnahme ausstehend | Teilfreigabe 10/10 |
| Manuelle Transkription, zweiter visueller Abgleich und eingefrorene Referenz | A3-Verfahren A am 23.11. festgelegt: zwei zeitlich getrennte manuelle Kontrollen durch dieselbe Person; keine personelle Unabhängigkeit; keine Texte erstellen | Verfahren festgelegt, Referenzen offen |
| Gemeinsame Textnormalisierung, Block-/Zellreferenzregeln | Zur Freigabe | offen |
| Grenzwerte und kritische Fehlertoleranz aus Qualitätsplan Abschnitt 8 | Zur Freigabe | offen |
| A–D: PyMuPDF/Tesseract-Sprach- und DPI-Vergleich | Historische Versuche liegen vor; neue vergleichende Korpus-Messläufe nicht freigegeben | offen |
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

### A5-Zwischenfreigabe – sechs konkrete Seitenkandidaten (23.11.2026)

**Fachliche Entscheidung:** Der Betreiber hat OQ-05 bis OQ-10 am 23.11.2026 ausdrücklich **als Seitenkandidaten für die weitere Vorbereitung** zwischenfreigegeben. Keine Freigabe von Vollreferenzen, Qualitätsmessungen oder gesamtem A5.

| ID | Zwischenfreigegebene Seite (PDF-Seite 1-basiert) | Sichtprüfung und fachliche Eignung | Grenze |
| --- | --- | --- | --- |
| OQ-05 | `usb_20.pdf`, S. 601 | Zwei Indexspalten, historisch visuell bestätigt; dokumentiertes `sort=True`-Lesereihenfolgeproblem | Strukturreferenz und korrekten Leseweg noch abnehmen |
| OQ-06 | `agp30.pdf`, S. 40 | „Table 16: Graphics Card Options“, drei Spalten, sechs Datenzeilen, visuell klar abgrenzbar | Zell-/Zeilen-/Spaltenzuordnung gesondert prüfen |
| OQ-07 | `MGA-G200_199811.pdf`, S. 522 | Historisch visuell bestätigte komplexe Pinmatrix | Signal-/Pin-Zuordnung noch nicht abgenommen |
| OQ-08 | `82443BX.PDF`, S. 124 | Dicht beschrifteter Pinplan mit Fußnoten; 4,9 pt dominante Schrift laut historischem Bericht | Natives Text-PDF; keine automatische Raster-OCR-Freigabe |
| OQ-09 | `Core X6800 and Core Duo E6000 and E4000.PDF`, S. 20 | Visuell geprüft: eng gruppierte ähnliche CPU-Modellnummern und technische Werte; S. 9 nur Reserve | Natives Text-PDF; exakte Kennungstrefferquote ausstehend |
| OQ-10 | `cubx-103.pdf`, S. 21 | Visuell geprüfte Prozessor-/Busfrequenzen, Multiplikatoren und DIP-Schalterwerte | Präzise Wert-Einheit- und Zeilenzuordnung noch messen |

**Nachtrag zum zuvor unbesetzten Stand:** OQ-02 ist seit der nachstehenden ausdrücklichen Freigabe als Kandidat besetzt. OQ-01 und OQ-03 sind anhand neu bereitgestellter Scanbilder visuell geeignet, jedoch **noch nicht ausdrücklich als konkrete Seiten freigegeben**. OQ-04 bleibt aufgrund teilweise verdeckter Bildinhalte nur bedingt geeignet. Die CUBX-Werbung S. 111 ist kein nachgewiesener schlechter Scan.

### A5-Zwischenfreigabe – OQ-02 TMS4164 (23.11.2026)

**Fachliche Entscheidung:** Der Betreiber hat nach Sichtprüfung des von ihm bereitgestellten, 19-seitigen Texas-Instruments-Datenblatts `TMS4164-datasheet-texas-instruments.pdf` **PDF-Seite 2 (1-basiert, gedruckte S. 4-42)** ausdrücklich als Seitenkandidaten für OQ-02 freigegeben.

**Eignung:** Bildbasierte technische Datenblattseite mit der Bezeichnung TMS4164, klaren Überschriften und Unterabschnitten wie `operation`, `address`, `write enable` und `refresh` sowie zusammenhängendem technischen Fließtext. Das Dokument wurde als 19-seitige Scan-PDF vorgelegt; bei der Sichtung war kein auslesbarer Text vorhanden. Dies ist eine **visuelle Eignungsentscheidung**, keine bestandene OCR-Gütemessung oder vollständige technische PDF-Validierung.

**Grenzen:** Original-PDF sowie spätere lokal ermittelte SHA-256-, Bild-/Renderparameter und Referenzversionen ausschließlich lokal sichern; **kein Upload der Quelle nach Git**. Keine Referenztexte, CER/WER, OCR- oder VLM-Ausführung freigegeben. Die bereits bestehenden OQ-05–OQ-10-Zwischenfreigaben bleiben unverändert. A5 bleibt `offen`, solange die Gesamtauswahl und deren Identitätsprüfung nicht abgeschlossen sind.

**Historischer Zwischenstand nach OQ-02-Freigabe:** OQ-01 und OQ-03 waren zu diesem Zeitpunkt visuell geeignet, aber noch nicht zwischenfreigegeben; OQ-04 war nur bedingt geeignet. **Die nachfolgende ausdrückliche Zwischenfreigabe von OQ-01 und OQ-03 ersetzt diesen alten Status.**

### A5-Zwischenfreigabe – OQ-01 und OQ-03 (23.11.2026)

**Fachliche Entscheidung:** Nach der visuellen Sichtprüfung von vier neu vorgelegten Scanbildern wurde die gemeinsame Zwischenfreigabe der bereits vorgeschlagenen Seiten für **OQ-01 und OQ-03** am 23.11.2026 vom Betreiber bestätigt. Die Freigabe gilt ausschließlich als **fachliche Eignung der beiden Seitenkandidaten**, nicht als Abschluss der vollständigen A5-Abnahme.

| ID | Zwischenfreigegebene Vorlage | Visueller Eignungsbefund | Verbleibende Voraussetzung |
| --- | --- | --- | --- |
| OQ-01 – Sauberer Scan | Gedrucktes **CP/M-Handbuch**, Abschnitt **7.2**, gedruckte Seite **7-6** | Gut lesbarer, überwiegend einspaltiger Fließtext mit klaren Zwischenüberschriften, leichter Papieralterung und vergleichsweise hohem Kontrast | Lokale Original-Scanidentität, Scanprofil/Hash und spätere vollständige manuelle Referenz ausstehend |
| OQ-03 – Schlechter Scan | Gedrucktes **C64-Programmlisting**, gedruckte Seite **104** | Sichtbar schwacher Druck-/Scan-Kontrast, dünne Zeichen und viele verwechselbare BASIC-Zeichen; echter eingescannter Problemfall, nicht nachträglich künstlich verschlechtert | Lokale Original-Scanidentität, Scanprofil/Hash, Lesbarkeitsgrenzen und spätere manuelle Referenz ausstehend |

**Abgrenzung zu OQ-04:** Die separat gesichtete C64-Assemblerbuchseite **92** zeigt Bundschatten und teilweise verdeckte Tabellen. Sie bleibt **nur bedingt geeignet und nicht zwischenfreigegeben**, weil verdeckte Inhalte eine überprüfbare Volltextreferenz verhindern können. Für OQ-04 eine besser prüfbare echte Schräglagen-, Unschärfe- oder Ausleuchtungsvorlage suchen oder nach gesonderter Entscheidung die testbare Region eindeutig eingrenzen.

**Schutzgrenzen:** Die beiden hochgeladenen Bilder sind visuelle Sichtungsgrundlage; die Originaldateien, Bild-/Quellhashes, tatsächlichen Scanparameter und spätere Referenztexte werden ausschließlich lokal dokumentiert. Keine OCR, keine Referenztranskription, keine neuen Tests und keine Datenbank-/Nextcloud-/Archivänderungen freigegeben. **Neun von zehn konkrete Seitenkandidaten sind fachlich zwischenfreigegeben.** A5 und alle 29 eingefrorenen Abnahme-IDs bleiben `offen`.

### A5-Zwischenfreigabe – OQ-04 Maschinensprache für Einsteiger (23.11.2026)

**Fachliche Entscheidung:** Der Betreiber hat nach visueller Prüfung ausdrücklich die neue Scanvorlage **„Maschinensprache für Einsteiger“, gedruckte Seite 100**, als zehnten und letzten **A5-Seitenkandidaten OQ-04** zwischenfreigegeben. Diese Seite ersetzt den früheren, nur bedingt geeigneten Vorschlag „C64-Assemblerbuch, S. 92“; die alte Aufnahme bleibt als historischer Befund erhalten, ist **nicht** Teil der ausgewählten zehn Seiten.

**Eignungsbefund:** Vollständig lesbare linke Buchseite mit Fließtext, technischen Adressen und Assemblerlisting. Erkennbar sind **mäßige ungleichmäßige Beleuchtung am Buchbund** sowie leichte Seitenkrümmung; **keine gesicherte erhebliche Unschärfe und keine ausgeprägte Schräglage**. Das Testmerkmal ist hier die milde Beleuchtungs-/Geometrieabweichung, nicht ein schwer beschädigter Scan.

**Abgrenzung:** Das hochgeladene Originalbild enthält rechts einen angeschnittenen Teil der Nachbarseite. Der bewertete Textumfang umfasst **nur die vollständig sichtbare linke gedruckte Seite 100**, nicht die rechte Nachbarseite oder Scannerhintergrund. Am 23.11.2026 wurde nach Sichtprüfung einer abgeleiteten Vorschau die **konkrete Bewertungsregion** ausdrücklich fachlich freigegeben (nachfolgende Ergänzung). Originalscan unverändert lassen.

**A5-Gesamtstand:** Nun sind alle **zehn Seitenkandidaten OQ-01 bis OQ-10 fachlich zwischenfreigegeben**. Die formale A5-Test-ID bleibt **`offen`**, bis alle Quellen/Scanparameter und die konkrete Render-/Regionsidentität lokal nachvollziehbar dokumentiert und der Gesamtkorpus gesondert abgenommen sind. Die Referenz-Erstellung nach A3, CER/WER-, OCR-, Layout- und VLM-Ausführung sowie Index-/Faktenfreigaben bleiben unautorisiert.

### A5 – Freigabe der OQ-04-Bewertungsregion (23.11.2026)

**Entscheidung:** Der Betreiber hat nach visueller Prüfung der lokal erzeugten Vorschau `OQ-04-region-proposal.png` die Koordinaten **`(300, 50, 1950, 2400)`** ausdrücklich als **endgültigen Bewertungsbereich für OQ-04** freigegeben. Koordinatensystem: Bildpixel, Ursprung oben links, `x2` und `y2` exklusiv. Die unveränderte Originalquelle ist `sources/OQ-04.png` im lokalen A5-Korpus; **2448 × 3437 px**. Abgeleitete Bewertungsregion: **1650 × 2350 px**.

**Umfang:** Gedruckte linke Buchseite 100 aus „Maschinensprache für Einsteiger“ mit Seitenkopf, vollständigem Assemblerlisting und Fließtext; rechte angeschnittene Nachbarseite und Scannerhintergrund bleiben ausgeschlossen. Natürlicher, **moderater** Bundschatten und leichte geometrische Abweichung bleiben als OQ-04-Qualitätsmerkmal enthalten. Das ist kein Nachweis starker Unschärfe.

**Lokaler Status:** Die Vorschau wurde vom Betreiber lokal erzeugt und als Bild im Dialog visuell begutachtet; die verbindliche Regionsfreigabe ist dokumentiert. **Noch nicht bestätigt** ist die dauerhafte Speicherung der freigegebenen Regionsmetadaten im lokalen Korpusmanifest oder einer separaten revisionssicheren lokalen Freigabedatei, einschließlich SHA-256-Abgleich der gespeicherten Original- und Vorschau-Bytes. Dies ist vor der vollständigen A5-Abnahme auf Poseidon nachzuweisen. Rohbild, Vorschau und bisheriges Manifest nicht überschreiben; Quelle, Hashwerte und vollständige Referenztexte ausschließlich lokal.

**Schutzgrenzen:** Freigabe nur der OQ-04-Region, **keine** Freigabe der A5-Gesamtabnahme, von A3-Referenzen, OCR-, Layout- oder VLM-Testläufen, Indexierung oder Faktenübernahme. Alle 29 eingefrorenen Test-IDs und deren Kriterien bleiben unverändert `offen`.

**Nachweisgrenzen:** Die sechs Seiten sind überwiegend native Text-PDFs; Eignung für Struktur-/Präzisionsprüfungen bedeutet **keine** nachgewiesene Raster-OCR-Qualität. Original-PDF-SHA-256, Versions- und Renderparameter sowie spätere Referenztexte nur lokal sichern. Alle 29 eingefrorenen Test-IDs, Akzeptanzkriterien, Prioritäten und formalen Status bleiben unverändert `offen`. A5 insgesamt noch nicht freigegeben. Keine Testausführung, keine Indexierungs- oder Faktenfreigabe.

## 4. A – Isolation, Quellen und Referenzqualität

| ID | Szenario | Akzeptanzkriterium | Prio | Status | Vorhandene Abdeckung / Grenze |
| --- | --- | --- | --- | --- | --- |
| A1 | Isolierter Betrieb | Keine DB-/Worker-/Nextcloud-Schreibzugriffe, keine Quelldateiänderung; lokales Ausgabeverzeichnis | M | offen | 23.11. Poseidon: isoliertes Arbeitsverzeichnis, Bubblewrap ohne Netzroute, historische Dateien ro; SHA-256-Integritätscheck PASS. **Rest:** vollständigen Korpuslauf isoliert nachweisen; WebDAV-PROPFIND war gesondert lesend mit Netz. |
| A2 | Exakte Quell-/Renderidentität | Identischer PDF-Inhalt/Seite/Region mit SHA- und Render-/Modellparametern; kein Vergleich unterschiedlicher Ausschnitte | M | offen | 23.11. echter CUBX-Quellhash gegen Review und OCR-Run identisch; S.111 bei 140 DPI mit PyMuPDF 1.28.2 als 1157×1638 PNG pixelidentisch. **Rest:** andere freigegebene Seiten und Regions-/Engineparameter; kein Beweis bytegleicher 200-DPI-OCR. |
| A3 | Unabhängiger Referenztext | Manuell vom sichtbaren Original erstellt, zweitgeprüft und vor der Messung eingefroren | M | offen | 23.11. Verfahren A entschieden: zwei zeitversetzte manuelle Durchgänge durch dieselbe Person, nicht personell unabhängig. **Rest:** Referenzseiten freigeben, Vollreferenzen erstellen/versionieren; Akzeptanz der eingeschränkten Unabhängigkeit gesondert entscheiden. |
| A4 | Ungeprüfte Referenz abweisen | Ungeprüfte/unvollständige Referenz liefert keine Gütezahlen und keine Freigabe | M | offen | 23.11. Bubblewrap: 3 bestehende Schutz-/Provenienztests PASS in 0,08 s, SHA-Manifest PASS, Git sauber. **Rest:** unvollständige Referenz und vollständige Freigabebarriere am Korpus prüfen; bestehende 3 Tests nicht grundlos wiederholen. |
| A5 | Korpusabdeckung dokumentieren | Alle zehn freigegebenen Seitenplätze belegt oder Abweichung begründet; Kategorien nachvollziehbar | M | offen | **23.11.: zehn konkrete Seitenkandidaten OQ-01–OQ-10 zwischenfreigegeben**; OQ-04-Region **(300, 50, 1950, 2400)** nach Sichtprüfung ausdrücklich freigegeben (Abschnitt 3). Zehn Originaldateien auf Poseidon lokal gesichert; 6 historische Hashes bestätigt und 4 neue Hashes erfasst. **Rest:** dauerhafte lokale Regionsfreigabe/Hashbeziehung und Quellen-/Scan-/Renderidentitäten kontrollieren; A5-Gesamtkorpus gesondert abnehmen. |

## 5. B – OCR-Routing und Textqualität

| ID | Szenario | Akzeptanzkriterium | Prio | Status | Vorhandene Abdeckung / Grenze |
| --- | --- | --- | --- | --- | --- |
| B1 | Native Extraktion vs. OCR-Auslösung | Textseiten erhalten native Ausgabe; echte Scan-Kandidaten/erzwungene geprüfte Seiten werden korrekt unterschieden | M | offen | Stage-4-Regressions-/Mocktests; realer CUBX-PDF-Lauf: OCR S.111, Leer S.112, 112 Seiten/114 Chunks, ohne Warnungen bei nur S.111. **Rest:** Routing am freigegebenen Korpus; technische Basis nicht erneut testen. |
| B2 | Leerseite / OCR-Warnungen | Visuell leere Seite zählt nicht als verlorener Text; OCR-Fehler bei nichtleeren Seiten werden getrennt markiert | M | offen | S.112 visuell bestätigte weiße Leerseite, bei absichtlich erzwungener OCR erwarteter Leertext-Fehler; Lauf nur S.111 ohne Warnungen. Vektor-Negativtest vorhanden. **Rest:** Warnungs-/Leerfallabnahme je einschlägigem Korpusfall. |
| B3 | CER/WER je Seite und Variante | Auf freigegebenen Ganzseitenreferenzen berechnen und einzeln sowie nach Kategorie berichten | M | offen | 8 OCR-Evaluator-Tests (synthetisch) und Ruff PASS; CER/WER-Funktionen vorhanden. **Rest:** CER/WER gegen vollständige, freigegebene Seitenreferenzen je Variante. |
| B4 | Sprachvergleich `eng` / `eng+deu` | Gleiche Originalregion, DPI, Referenz und OCR-Parameter bis auf Sprache; Ergebnisunterschiede belegt | M | offen | CUBX-PNG bei PSM6: `eng` CER 2,32 %/WER 15 %, `eng+deu` CER 2,51 %/WER 16,25 %; bytegleich reproduziert, **Referenz provisorisch**. **Rest:** Vergleich am freigegebenen Korpus, keine allgemeine Sprachentscheidung. |
| B5 | DPI-Vergleich 200 / 300 | Vergleich auf identischer Quelle/Referenz und kontrollierten Einstellungen; Laufzeit protokolliert | S | offen | Historisch 12 Regionen-Kandidaten (PSM6/11, 200/300 DPI) plus 6 Einzelzeilen-Kandidaten (PSM7). **Rest:** identische Regionen, endgültige Referenzen und vergleichbare Laufzeiten. |
| B6 | Modellnummern exakt | Jede freigegebene Referenzkennung exakt prüfen, Fehl-/Verwechslungen einzeln berichten | M | offen | Synthetischer Kennungstest; reale CUBX-Werte im Spezifikationsbereich weitgehend erkannt; VLM-Badge-Fehler `Banned`/`Bundled`. **Rest:** absolute Treffer/Fehler aller freigegebenen Referenzkennungen. |
| B7 | Zahlen und Wert-Einheit-Paare | Vorzeichen, Dezimalstellen, Kennungen, Einheiten und Wertepaare separat zählen; kritische Fehler ausweisen | M | offen | CUBX-Werte `300MHz`, `32MB DDR SGRAM`, `704x480` visuell untersucht, keine vollständige Wert-Einheit-Metrik. **Rest:** Vorzeichen/Dezimalzeichen/Wertepaare gegen freigegebene Referenzen zählen. |
| B8 | Erfundene technische Angaben | Zusätzlich im OCR-/Vision-Ergebnis auftauchende unbelegte technische Kennungen und Werte explizit bewerten | M | offen | Gemma verwechselt `Banned`/`Bundled`, Qwen erzeugt unbelegte Erklärungen; `critical_term_recall` erfasst fehlende, nicht erfundene Begriffe. **Rest:** unbelegte/entstellte technische Angaben separat prüfen. |
| B9 | PSM 6/7/11 unter gleichen Bedingungen | Für jeweils geeignete, freigegebene Bildregionen identische Quelle, Zuschnitt, DPI, Sprache und Referenz; nur PSM variieren; CER/WER und kritische Zeichen vergleichen | M | offen | 3 CUBX-Regionen × 200/300 DPI × PSM6/11 = 12 Kandidaten; drei Zeilen × 200/300 × PSM7 = 6; nach Regression 153 passed, 11 skipped. **Rest:** PSM6/7/11 auf exakt derselben geeigneten Region mit verifizierter Referenz. |
| B10 | Ganze Seite gegenüber Regions-OCR | Den Textumfang vorab genau angleichen: Ganzseitenergebnis auf dieselben Referenzregionen abbilden, gesondert Vollständigkeit/Regionenabdeckung bewerten; keine Ganzseiten-CER gegen einzelne Crop-Referenz | M | offen | CUBX-Ganzseiten-OCR (1723 Zeichen) und 18 Regions-/Zeilen-Kandidaten existieren. **Rest:** regionsidentischer Vergleich und Vollständigkeitsbewertung; keine Ganzseiten-CER gegen Crop-Referenz. |

## 6. C – Layout und Struktur

| ID | Szenario | Akzeptanzkriterium | Prio | Status | Vorhandene Abdeckung / Grenze |
| --- | --- | --- | --- | --- | --- |
| C1 | Zweispaltige Lesereihenfolge | Reihenfolge der vorab referenzierten Textblöcke/Übergänge nachweisbar korrekt | M | offen | USB 2.0 S.601/606: echte zweispaltige Indexseiten, PyMuPDF `sort=True` vermischt Spalten; Segmentierungsvorschläge `REVIEW_REQUIRED`. **Rest:** geprüfte Blockreferenz und nachgewiesene korrekte Leseordnung. |
| C2 | Einfache Tabellenstruktur | Zelltexte plus Zeilen-/Spaltenbeziehungen mit geprüfter Referenz vergleichen | M | offen | 3720 technische Tabellenhinweise im Survey, EHCI S.43, USB 1.0 S.152, CUBX S.21 als historische Kandidaten. **Rest:** einfache Tabelle mit validierten Zell-/Zeilen-/Spaltenbeziehungen. |
| C3 | Komplexe Pin-/Registermatrix | Jede freigegebene Pin-/Signal- bzw. Register-/Wert-Zuordnung nachweisbar; keine Faktenfreigabe bei Mehrdeutigkeit | M | offen | Matrox G200 S.522 visuell bestätigte Pinmatrix; Chunking verlustfrei, aber 2D-Zuordnung ungesichert; YOLO `table`/`figure`-Konflikt. **Rest:** geprüfte Pin-/Signal-Zuordnungen. |
| C4 | DocLayout-YOLO nur als Vorschlag | Klassenkonflikte und unzugeordnete Inhalte bleiben erhalten und führen zu Review, nicht zur automatischen Auswahl | S | offen | 16 Unit-Tests zu Layoutkonflikten bestanden; reale YOLO-CPU-Läufe USB S.601 1,8840 s, S.606 0,7302 s, Matrox S.522 0,7220 s. **Rest:** tatsächlichen Review-Fallback und unzugeordnete Inhalte fachlich abnehmen. |

## 7. D – Vergleichbarkeit, Messung und Ergebnisentscheidung

| ID | Szenario | Akzeptanzkriterium | Prio | Status | Vorhandene Abdeckung / Grenze |
| --- | --- | --- | --- | --- | --- |
| D1 | Messvarianten vergleichbar | A–D für dieselbe freigegebene Quelle; E/F nur nach Einzelentscheidung; fehlende Varianten als `nicht getestet` kennzeichnen | M | offen | OCR-/Sprach-/DPI-/PSM-Varianten und VLM-Einzelversuche historisch vorhanden. **Rest:** dieselben freigegebenen Quellen/Referenzen und gesonderte Methodenfreigabe; E/F nur separat. |
| D2 | Laufzeit auf gleicher Grundlage | OCR-Zeit/Seite, reine Layout-Inferenz und gesamte Pipeline getrennt ausweisen, Host/Modelle/Startbedingungen dokumentieren | M | offen | YOLO-CPU-Inferenz 0,7220–1,8840 s, realer PDF/OCR/Embedding-E2E 21,46 s – verschiedene Metriken. **Rest:** OCR/Layout/E2E auf vergleichbarer Grundlage separat messen. |
| D3 | Qualitätsgrenzen anwenden | Sämtliche vorgeschlagenen, **erst noch freizugebenden** Grenzwerte je Seite/Kategorie auswerten; kritische Fehler nicht wegmitteln | M | offen | Grenzwerte in Abschnitt 9 noch unbestätigte Vorschläge; provisorischer CUBX-WER ist keine formale Grenzwertverletzung. **Rest:** Schwellen freigeben und pro Seite inkl. kritischer Fehlstellen anwenden. |
| D4 | Manuelle Nachprüfung und Empfehlung | Begründete Entscheidung zu Standard-OCR, regionalem Routing, zusätzlicher Layoutanalyse und Review-Bedarf | M | offen | Historisch: Tesseract bei Spezifikationen brauchbar, Stiltext schwierig, USB/Matrox strukturell fehleranfällig, VLM kann Fachbegriffe falsch lesen. **Rest:** freigegebene Bewertung und begründete Empfehlung. |
| D5 | Reproduzierbarkeit/Provenienz | Quell-/Seitenidentität, Referenzversion, Engine-/Modellversion, Sprache, DPI, Parameter und Ergebnis dokumentiert | M | offen | CUBX-Quellhash und 140-DPI-Render pixelidentisch (23.11.); PNG-PSM6-Sprachtexte bytegleich (12.11.); PR13-Real-E2E bestanden. **Rest:** Quelle/Referenz/Region/Engine/Modell/Prompt/Laufzeiten für jede endgültige Variante nachvollziehbar. |

## 8. E – Optionale, gesondert freizugebende Vergleiche

| ID | Szenario | Akzeptanzkriterium | Prio | Status | Vorhandene Abdeckung / Grenze |
| --- | --- | --- | --- | --- | --- |
| E1 | DocLayout-gestützte Regions-OCR | Eindeutige Region zu exakt gleicher Referenz; Textgenauigkeit und Struktur separat vergleichen | O | offen | YOLO-Regionserkennung und getrennte CUBX-Regions-OCR erprobt, nicht als integrierte Kette gegen gleiche Referenz abgenommen. **Rest optional:** vollständiger Regionenvergleich nach gesonderter Freigabe. |
| E2 | Selektiver, regelbasierter Vision-LLM-Zweitkandidat | Erst Standardextraktion/Tesseract; VLM ausschließlich bei vordefinierten auffälligen Regionen und nach gesonderter Freigabe. Tesseract- und VLM-Transkripte parallel als unbestätigte Kandidaten mit Region, Modell, Prompt, Abweichungen und Reviewbedarf erhalten; **kein automatisches Überschreiben, Indexieren oder Faktenfreigeben** | O | offen | Qwen3-VL 2B/Gemma3 12B als lokale OCR-Zweitkandidaten manuell erprobt, kein regelbasierter Trigger- und Reviewprozess. **Rest optional:** Trigger, nachvollziehbare parallele Kandidaten und menschliche Freigabebarriere. |
| E3 | Ressourcen und Nutzen | Qualitätsgewinn gegen CPU-/GPU-/RAM- und Laufzeitkosten dokumentieren | O | offen | Gemma3 12B auf GTX 1060 6GB ausprobiert; VRAM/CPU-Snapshots, aber keine vergleichbaren Laufzeit-/Qualitätsreihen. **Rest optional:** Nutzen und Ressourcenaufwand mit gleichen Bedingungen. |
| E4 | Qwen3-VL 2B gegen Gemma 3 12B | Nach gesonderter VLM-Ausführungsfreigabe dieselben ungesehenen, unabhängig referenzierten Bildregionen und neutrale Transkriptionsprompts vergleichen; Wiederholungen, CER/WER, Kennungen, Fehler und Ressourcen pro Modell dokumentieren | S | offen | Qwen3-VL 2B 2/3, Gemma3 12B 3/3 Zeilen visuell korrekt; Gemma-Badge `Banned` statt `Bundled`. **Rest nur nach Zusatzfreigabe:** blinde, wiederholte, regionsgleiche quantitative Vergleiche. |
| E5 | VLM-Halluzinationen, Prompt-Einfluss und Reviewbarriere | An historischen Befunden sowie – nur falls gesondert freigegeben – neuen Blind-/Wiederholungsversuchen unbelegte Ergänzungen, falsch begründete Kandidaten, Prompt-Leakage und Tesseract/VLM-Konflikte erfassen. Kriterien/Entscheidung zur menschlichen Prüfung dokumentieren; keine Selbstbestätigung, kein automatisches Überschreiben oder Fakten-/Indexfreigabe | M | offen | Qwen rationalisierte falsche Unterstriche mit nicht belegten Aussagen; Gemma las `Banned` statt `Bundled`. **Rest verpflichtend:** historische Risiko-/Promptbewertung und funktionierende menschliche Reviewbarriere dokumentieren; keine neue VLM-Ausführung ohne Freigabe. |

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

### Nachtrag 23.11.2026 – historisch erledigte Teilprüfungen, verbleibende Abnahmen

Die 29 Test-IDs sind weiterhin **unverändert eingefroren**. Die Einzelzeilen der Matrix enthalten jetzt die nachweislich bereits erledigten historischen Teilprüfungen und **jeweils nur noch den offenen Rest**. Ein bestandener technischer Test ist nicht dasselbe wie eine bestandene vollständige fachliche Matrix-ID.

| Vorhandener Nachweis | Belegter Umfang | Keine erneute technische Pflichtwiederholung für |
| --- | --- | --- |
| PDF-Qualitätsbaseline vom 10.11. | 29 PDFs, 5.064 Seiten technisch vollständig; 7/14 Goldstandard-Seiten visuell klassifiziert | PDF-Survey und rein technische Klassifikation |
| Stage-4-OCR-Regression und reale CUBX-Vorschau | 17 Tests zu PDF/OCR, realer Seiten-OCR-Lauf und kontrolliertes Leerseitenrouting | Synthetischer Kontrollfluss, grundlegende OCR-Erreichbarkeit |
| OCR-Evaluator vom 12.11. | 8 Tests und Ruff bestanden; CER/WER-Rechenfunktionen | Bereits bestätigte Metrik-Unit-Tests |
| CUBX-Sprachvergleich vom 12.11. | PSM6, PNG-Ausschnitt: `eng` 2,32 % CER/15 % WER; `eng+deu` 2,51 %/16,25 %; bytegleich reproduziert, **provisorische Referenz** | Reproduzierbarkeit dieses historischen Ausschnitts |
| CUBX-Regionen und PSM7 vom 21.11. | 12 PSM6/11-Kandidaten, sechs PSM7-Zeilenkandidaten; Regression zuletzt 153 passed, 11 skipped | Experimentelle Machbarkeit, keine CER/WER-Abnahme |
| DocLayout-YOLO und Struktur | USB-/Matrox-Einzelfälle, 16 Konflikttests, drei reale CPU-Inferenzzeiten | Detektionsmachbarkeit, nicht Layout- oder Tabellenfreigabe |
| Qwen3-VL 2B und Gemma3 12B | Titel/Slogan 2/3 bzw. 3/3; Gemma verwechselte `Bundled` mit `Banned`; Qwen unbelegte Fehlerbegründung | Historische qualitative Einzelbefunde; keine VLM-Blindstudie |
| PR13 Real-Dokument-E2E vom 22.11. | CUBX 112 Seiten, 114 Chunks und 114 Ollama-Embeddings; isolierter Test 1 passed in 21,46 s | Technische Verkettung, keine OCR-Güte |
| Poseidon A1/A2 vom 23.11. | Bubblewrap schreibgeschützt/netzisoliert, SHA-Manifeste PASS; CUBX-Originalhash verifiziert und S.111 bei 140 DPI unter PyMuPDF 1.28.2 pixelidentisch | Historische Einzel-Quell-/Renderprüfung |
| Poseidon A4 vom 23.11. | 3 vorhandene Schutz-/Provenienztests in Isolation bestanden (0,08 s), historische Dateien unverändert | Diese drei technischen Tests |

**Wichtige Unterscheidung beim Nextcloud-Bestand:** Aktuelle PROPFIND-Inventur: 29 PDFs mit 28 verschiedenen *Dateinamen*. Die historische PDF-Analyse identifizierte 28 eindeutige *Inhalte*. Aus der aktuellen Namenszählung allein lässt sich die heutige SHA-256-Identität nicht erneut beweisen. Keine PDFs wurden bei der Inventur heruntergeladen.

**Offene Abnahmen statt Testwiederholungen – empfohlene Reihenfolge:**

1. **A5/A2:** Bereits vorhandenen lokalen Qualitätsbericht prüfen; fehlende Scankategorien ergänzend visuell untersuchen und erst danach zehn konkrete Seiten jeweils gesondert freigeben; Original-/Regionidentität bestätigen.
2. **A3:** Manuelle Vollreferenzen nach dem vereinbarten zeitlich getrennten Zweidurchgangsverfahren erstellen, nachdem die Referenz-Erstellung eigens freigegeben wurde. **Keine personell unabhängige Zweitprüfung**: methodische Abweichung vor Abnahme ausdrücklich entscheiden und dokumentieren.
3. **A4/A1:** Noch fehlende Schutzabdeckung für unvollständige Referenzen und den gesamten isolierten Evaluationslauf bestätigen, ohne die drei bereits bestandenen Unit-Tests nur zum Nachweis zu wiederholen.
4. **B/C/D:** Nur ausstehende fachliche Messungen anhand freigegebener Regionen und Referenzen, einschließlich der noch zu genehmigenden Grenzwerte. Zeichengüte, Leseordnung und Matrix-Zellzuordnung getrennt beurteilen.
5. **E5 verpflichtend:** Bereits nachgewiesene VLM-Fehlermodi und Reviewbarriere fachlich bewerten. E1–E4 nur bei eigenständiger optionaler Freigabe ausführen, andernfalls offen/mit begründeter Zurückstellung behandeln.

**Formale Bewertung:** Alle 29 IDs bleiben `offen`, bis das gesamte jeweilige eingefrorene Akzeptanzkriterium erfüllt oder eine Abweichung entschieden ist. Eine historische Teilabdeckung darf nicht als grüner Gesamttest umetikettiert werden. **Es gibt aber nicht 29 neu auszuführende Tests**: Die verbleibenden Anforderungen stehen in der letzten Spalte jeder ID.

**Quellen:** `docs/PDF_OCR_STAGE4.md`, `docs/OCR_QUALITY_EVALUATION.md`, `docs/PDF_GOLDSTANDARD_REVIEW.md`, `docs/ocr-quality-plan.md`; `docs/PROJECT_ROADMAP.md` und `docs/PR13_POSEIDON_INTEGRATION_TEST_2026-11-22.md` auf `integration/pdf-ocr-webdav-2026-11-21`; vom Betreiber am 23.11.2026 im Dialog übermittelte A1/A2/A4-Poseidon-Ausgaben. Die letzten Ausgaben sind **nicht** als ins Repository importiertes Testlog zu verstehen.

## 11. Abbruchkriterien und Definition „fertig“

**Abbruch:** Sicherheits-/Isolationsverletzung, Veränderung des Originals, notwendige DB-/Worker-/Apply-Verarbeitung, unklare Modell-/Quellidentität oder methodisch ungültiger Referenzvergleich. Ein individueller OCR-Fehler oder schlechter Qualitätswert ist ein reguläres **Messergebnis**, kein pauschaler Abbruchgrund.

**Abnahme fertig:** Korpus und Methoden freigegeben; alle M-IDs `grün` oder jede Abweichung ausdrücklich als offen/rot mit Entscheidung dokumentiert; alle freigegebenen S-/O-IDs ausgeführt oder begründet zurückgestellt; Referenzen unabhängig geprüft; Metriken pro Seite, Kategorie und Variante dokumentiert; kritische technische Fehler sichtbar; reproduzierbare Laufzeiten/Parameter dokumentiert; Abschlussbericht mit begründeter Architektur-Empfehlung. **Dokumentierte Abweichung bedeutet nicht automatisch fachliche Erfüllung.**

## 12. Abnahmeprotokoll – noch nicht ausgefüllt

| Feld | Eintrag |
| --- | --- |
| Fachliche Freigabe dieser Matrix | **22.11.2026 – 29 IDs und Prioritäten verbindlich eingefroren** |
| Freigegebener Korpus | **10/10 Seitenkandidaten sowie OQ-04-Regionskoordinaten fachlich freigegeben**; lokale Freigabemetadaten/Hashabgleich und A5-Gesamtabnahme weiterhin offen |
| Freigegebene Schwellenwerte / Varianten | ausstehend |
| Datum / Prüferin | — |
| Quell- und Referenzversionen (nur lokal) | — |
| Geprüfter Repository-Commit | — |
| Ergebnis A–E | 29 formale IDs offen; technische Teilnachweise und verbleibende Restprüfungen je ID dokumentiert |
| Ausnahmen / Abweichungen / Entscheidungen | A5: Alle zehn Seitenkandidaten zwischenfreigegeben. OQ-04 S. 100: Region (300, 50, 1950, 2400) nach Sichtprüfung freigegeben; nur linke Seite, moderate Bundschattenwirkung. Dauerhafte lokale Regionsfreigabe und Hashabgleich noch nachzuweisen. Native Text-PDFs bleiben kein Raster-OCR-Beleg |
| Freigabe zu OCR-Evaluation | Historische Tests und technische A1/A2/A4-Prüfungen dokumentiert; **keine** Freigabe neuer OCR-/VLM-Gütemessungen |
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
| 22.11.2026 | **Fachliche Freigabe und Einfrieren des Abnahmeumfangs: 29 IDs, 23 M / 3 S / 3 O** | Ausdrückliche Zustimmung des Betreibers nach akzeptiertem Entwurf. Dies ist keine Freigabe der konkreten Testseiten, der Ground-Truth-Erstellung, der Schwellenwerte oder der Testdurchführung; PR #15 bleibt unberührt |
| 23.11.2026 | Historische OCR-/Layout-/VLM-/PR13-Ergebnisse und aktuelle A1/A2/A4-Teilnachweise je ID eingetragen; OQ-Kategorien und A3-Verfahrenstatus aktualisiert | **Kein** Ändern von 29 IDs, Prüfkriterien, Prioritäten oder Schwellenwerten; keine automatische fachliche Freigabe; PR #15 unberührt |
| 23.11.2026 | OQ-05 bis OQ-10 als sechs konkrete Seitenkandidaten fachlich zwischenfreigegeben und samt Grenzen in Abschnitt 3 dokumentiert | Betreiberfreigabe nach visueller Sichtung; vier Scan-Kategorien, alle formalen Matrix-IDs und gesamte A5-Abnahme bleiben offen |
| 23.11.2026 | OQ-02: Texas Instruments TMS4164, PDF-Seite 2, als siebten konkreten Seitenkandidaten fachlich zwischenfreigegeben | Ausdrückliche Nutzerfreigabe nach Sichtung des 19-seitigen gescannten Datenblatts; OQ-01/OQ-03/OQ-04 und A5-Gesamtabnahme offen; keine Änderung eingefrorener Testkriterien |
| 23.11.2026 | OQ-01 (CP/M-Handbuch S. 7-6) und OQ-03 (C64-Programmlisting S. 104) nach Sichtprüfung als achte und neunte Seitenkandidaten fachlich zwischenfreigegeben | Gemeinsame Betreiberzustimmung zu den vorgeschlagenen Kandidaten; OQ-04 wegen verdeckter Inhalte offen; keine Referenzen, neuen Testläufe oder Änderung eingefrorener Kriterien |
| 23.11.2026 | OQ-04: „Maschinensprache für Einsteiger“, gedruckte Seite 100, nach visueller Sichtprüfung als zehnten Seitenkandidaten fachlich zwischenfreigegeben | Ausdrückliche Betreiberzustimmung; nur die vollständig sichtbare linke Seite, milde Bundschatten-/Geometrieabweichung, rechte Nachbarseite ausgeschlossen; lokale Identitäts- und A5-Gesamtabnahme offen |
| 23.11.2026 | OQ-04: endgültige Bewertungsregion (300, 50, 1950, 2400) aus dem Originalscan 2448 × 3437 px ausdrücklich freigegeben | Betreiberzustimmung nach visueller Prüfung des 1650 × 2350 px-Ausschnitts; nur Bewertungsbereich, keine A5-Gesamtabnahme. Lokaler persistenter Regionsstatus und Hashnachweis noch ausstehend |
