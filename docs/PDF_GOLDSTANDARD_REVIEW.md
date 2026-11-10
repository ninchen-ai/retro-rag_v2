# Goldstandard-Prüfpakete für echte PDF-Seiten

## Zweck

Die Qualitätsbaseline vom 10.11.2026 liefert **Heuristiken**, aber noch keine
visuell überprüfte Referenz. Die lokale Goldstandard-Vorbereitung erzeugt deshalb
14 gezielt ausgewählte Prüfseiten mit:

- `page.png`: visueller Render der konkreten PDF-Seite;
- `extracted.txt`: von PyMuPDF ausgegebener Text in sortierter Reihenfolge;
- `metrics.json`: unveränderte Seitenmetriken aus dem Qualitätsbericht;
- `review.json`: **ungeprüftes** Bewertungsformular.

Es werden bewusst **keine** Aussagen als Goldstandard vorbelegt.
`null` bedeutet „noch nicht bewertet“. Eine Bewertung ist erst nach
Sichtprüfung von `page.png` und Abgleich mit `extracted.txt` gültig.

## Lauf auf Poseidon

Vorbedingungen: V2-Feature-Branch und die bereits für den Survey verwendete
Nextcloud-WebDAV-Konfiguration (URL, Benutzer, stabile Instanzkennung).

```bash
cd ~/projects/retro-rag_v2
git pull --ff-only
source .venv/bin/activate
python -m pip install -e '.[dev,pdf]'

python -m pytest -q tests/test_pdf_goldstandard.py
python -m ruff check src/retro_rag/importer/pdf_goldstandard.py tests/test_pdf_goldstandard.py

# Beginn mit vier Fällen zum Überprüfen der Artefakte:
python -m retro_rag.importer.pdf_goldstandard \
  --quality-report /tmp/retro-v2-pdf-quality.json \
  --max-cases 4 --dpi 120 \
  --output /tmp/retro-v2-pdf-goldstandard-smoke

# Danach alle 14 Fälle; Ausgabeverzeichnis darf noch NICHT existieren:
python -m retro_rag.importer.pdf_goldstandard \
  --quality-report /tmp/retro-v2-pdf-quality.json \
  --output /tmp/retro-v2-pdf-goldstandard
```

Bei fehlendem `RETRO_V2_NEXTCLOUD_APP_PASSWORD` wird das App-Passwort
interaktiv abgefragt. Die PDFs werden aus Nextcloud nur gelesen, in RAM
gehalten und anhand des im vollständigen Qualitätsbericht enthaltenen
SHA-256-Werts auf **unveränderten Inhalt** geprüft. Verschiedene Nextcloud-
Quellen mit identischem Inhalt werden für diese Prüfpakete nicht doppelt
gerendert; die Quellidentitäten in der eigentlichen V2-Import-Pipeline
bleiben davon unberührt.

Sicherheitsgrenzen: max. 50 MiB pro PDF, max. 1.000 Seiten, Rendering bei
72–180 DPI. Existierende Ausgabeordner werden grundsätzlich nicht
überschrieben, um manuelle Bewertungen zu schützen. Bei einem Abbruch
kann ein unvollständiger Ordner entstehen; für den nächsten Lauf einen
neuen Ausgabepfad verwenden. **Kein Resume und keine automatische Löschung
bereits geschriebener Artefakte.**

### Bewertungsprozess

1. Bild und extrahierten Text nebeneinander öffnen.
2. In `review.json` `review_status` erst nach tatsächlicher Prüfung
   von `unreviewed` auf `reviewed` setzen.
3. `page_kind` beschreiben (Text, Scan, leer, Vektor, gemischt, Sonstiges).
4. `ocr_needed`, `reading_order_correct`,
   `heading_boundaries_correct` und `table_structure_correct`
   mit `true`/`false` bewerten, soweit fachlich geprüft;
   sonst **null belassen**.
5. Bei Überschriften oder Tabellen die erwarteten Elemente in den
   Referenz-Arrays dokumentieren; fehlende Angaben nicht als „korrekt“
   interpretieren.
6. Schwierige Seiten als Referenzfälle für späteren Präzisions-/
   Recall-Vergleich markieren. Der Evaluator ist noch nicht implementiert.

**Datenschutz:** Dieser lokale Ordner enthält möglicherweise vollständige
urheberrechtlich geschützte Seitenbilder, Text, Dokumenttitel,
Nextcloud-Quellkennungen und Hashwerte. **Nicht in GitHub committen**
und bei Übertragung an andere Systeme deren Zugriffsschutz berücksichtigen.

## Testfälle (aus dem vollständigen Poseidon-Bericht)

| PDF | Seiten (PDF-Zählung ab 1) | Schwerpunkt |
|---|---|---|
| cubx-103.pdf | 111, 112 | Scanverdacht versus tatsächlich leere Seite |
| 3C905CX.pdf | 1 | OCR-Kandidat; zwei Quellorte identischer Datei |
| DirectX-Guide | 2 | OCR-Bedarf prüfen |
| 507700.pdf | 24 | Bildbasierte Seite |
| usb_20.pdf | 601, 606 | Mehrspaltigkeit, Leseordnung |
| AMD K6-2 Datenblatt | 326 | Sehr lange Seite / Leseordnung |
| MGA-G200_199811.pdf | 522 | Verlustfreies Text-Chunking |
| EHCI-Spezifikation | 43 | Häufige Tabellenkandidaten |
| USB 1.0-Spezifikation | 152 | Tabellen und Spalten |
| cubx-103.pdf | 21 | Tabellen ohne Bookmarks |
| agp20.pdf | 53 | Kapitelüberschriften |
| agp30.pdf | 40 | Kapitelüberschriften |

Die Seitenzahlen und Dateinamen wurden gegen die hochgeladene
`retro-v2-pdf-quality.json` abgeglichen. Es wurden keine
Originalseiten in GitHub übertragen. Der Goldstandard gilt derzeit als
**vorbereitet, nicht visuell bewertet**.

Write-Gate geschlossen lassen. Keine DB-/Embedding-/OCR-Operationen.


## Erste visuell geprüfte Goldstandard-Fälle (10.11.2026)

Die **gerenderten Seitenbilder** und die zugehörigen Seitenmetriken von
`cubx-103.pdf` wurden unabhängig vom automatischen Qualitätsklassifikator
visuell betrachtet. Die geprüften lokalen `review.json`-Dateien werden nicht
in das öffentliche GitHub-Repository übernommen.

| PDF-Seite (1-basiert) | Visueller Befund | Klassifikation | OCR-Bedarf | Ergebnis gegenüber PDF-Heuristik |
|---|---|---|---|---|
| 111 | Bildbasierte, vollflächige ASUS-AGP-V6800-Series-/GeForce-256-DDR-Werbeanzeige mit eingebetteten Texten und Leistungsangaben | `scan` (im Sinne von bildbasiert, kein belegter physischer Scan) | **ja** für Texterfassung | `ocr_candidate=true` bestätigt |
| 112 | Vollständig weiße gerenderte Seite ohne sichtbaren Inhalt | `blank` | **nein** | `ocr_candidate=false` bestätigt |

Zu S. 111: PyMuPDF lieferte 0 Zeichen, 0 Textblöcke, 1 Bildobjekt und
94,26 % geschätzte Bildabdeckung. Visuell erkennbare Überschriften sind
`AGP-V6800 Series` und `Span the Graphics Globe with DDR Intelligence`;
die automatische Überschriftenerkennung ohne Text-Layer hat hier einen
erwarteten Fehlfall. **Die Reihenfolge eines OCR-Ergebnisses ist noch nicht
beurteilt** und wird nicht als korrekt eingetragen.

Zu S. 112: 0 Zeichen, 0 Textblöcke, 0 Bildobjekte und 0 % Bildabdeckung.
Das gerenderte PNG wurde zudem als durchgehend weiß überprüft. Es gibt
keine OCR-relevanten Inhalte. Nicht anwendbare oder bislang nicht
evaluierte Review-Felder verbleiben ausdrücklich auf `null`.

Diese Referenzfälle belegen die **beiden OCR-Klassifikationen für diese
konkreten PDF-Seiten**. Daraus folgt noch kein allgemeiner Precision-/
Recall-Wert für die OCR-Heuristik und keine freigegebene OCR-Pipeline.
Auch eine Seitenanzeige mit sonstigen Vektoroperationen bleibt grundsätzlich
möglich; hier wurde nur die gerenderte Darstellung und der PyMuPDF-Bericht
geprüft. PDFs, Bilder und Text wurden nicht in GitHub veröffentlicht.

Nächster Schritt: OCR mit vorab festgelegten Referenztexten auf S. 111
isoliert evaluieren; auf S. 112 OCR auslassen. Danach getrennte Prüfungen
der Texterkennung und der Layout-/Lesereihenfolgequalität.


## Weitere visuell geprüfte Goldstandard-Fälle (10.11.2026)

Zusätzlich wurden die aus Nextcloud exportierten Seitenbilder von `3C905CX.pdf`
(S. 1) und `directx-demystified-a-comprehensive-guide-to-game-development-essentials.pdf`
(S. 2) unabhängig vom PDF-Textextraktor visuell bewertet.

| PDF-Seite | Beobachteter Inhalt | PDF-Analyse | Urteil |
|---|---|---|---|
| `3C905CX.pdf` S. 1 | Rasterbasierte Titelseite: „EtherLink PCI Network Interface Cards – User Guide“; Modellbezeichnungen 3C905C-TX-M, 3C905B und 3C900B | 0 Zeichen, 1 Bildobjekt, geschätzte Bildabdeckung 100 %, `ocr_candidate=true` | **OCR erforderlich**, um Titel und Modellbezug aus dieser Seite zu gewinnen |
| DirectX-Guide S. 2 | Bildbasiertes Buchcover mit „DIRECTX DEMYSTIFIED“, Untertitel „A Comprehensive Guide to Game Development Essentials“, „1ST EDITION“ und Autoren Frahaan Hussain / Kameron Hussain | 0 Zeichen, 1 Bildobjekt, geschätzte Bildabdeckung 58,72 %, `ocr_candidate=true` | **OCR sinnvoll** zur Erfassung von Titel, Ausgabe und Autoren, sofern keine zuverlässigen Metadaten anderweitig vorliegen |

**Abgrenzung:** Beide Seiten sind bildbasiert; ein tatsächlicher Papierscan
wird daraus nicht abgeleitet. Fehlende Überschriftenerkennung ohne
Textlayer ist bestätigt. Eine OCR-Textausgabe wurde **noch nicht**
durchgeführt; Erkennungsgenauigkeit, Lesereihenfolge und Tabellenstruktur
sind weiterhin nicht bewertet.

Zusammen mit dem CUBX-Anzeigenblatt S. 111 und der Leerseite S. 112
liegen damit **vier visuell geprüfte Seiten** vor:
drei mit begründetem OCR-Bedarf und eine ohne. Die restlichen
zehn der 14 Goldstandard-Prüffälle sind ungeprüft. Diese kleine, gezielt
ausgewählte Stichprobe ergibt keine allgemeine Precision/Recall-Schätzung.

Die lokal überarbeiteten `review.json`-Dateien enthalten
`review_status=reviewed` und die bestätigten OCR-Entscheidungen;
nicht geprüfte Leseordnungs-/Tabellenfelder bleiben `null`.
Originale Seitenbilder und Review-Artefakte wurden nicht ins
öffentliche Repository übernommen. V2-Write-Gate bleibt geschlossen.


## Visuell validierte Layout- und Chunking-Fälle (10.11.2026)

Aus dem lokalen Archiv `retro-v2-layout-review.tar.gz` wurden für folgende
drei Seiten jeweils `page.png`, `metrics.json`, `review.json` und
`extracted.txt` gemeinsam ausgewertet. Die Originalartefakte bleiben lokal.

| PDF / Seite (1-basiert) | Prüfung | Ergebnis |
|---|---|---|
| `usb_20.pdf` / 601 | zweispaltiger alphabetischer Index | `sort=True` verflicht linke und rechte Spalte zeilenweise. Die fachlich korrekte Reihenfolge ist **linke Spalte vollständig, dann rechte**. OCR nicht nötig; Lesereihenfolge **nicht korrekt** |
| `usb_20.pdf` / 606 | fortgesetzter zweispaltiger Index | Dasselbe Problem, zum Beispiel `ClearHubFeature()` gefolgt von `clock model (continued)` in derselben extrahierten Textzeile. OCR nicht nötig; Lesereihenfolge **nicht korrekt** |
| `MGA-G200_199811.pdf` / 522 | `Table A-3: PCI Pinout Legend (Bottom View)` | Breite Pin-Matrix, Zeilenbuchstaben, nummerierte Spalten und Signalkürzel. PyMuPDF-Textrepräsentation kann Pinpositionen nicht zuverlässig an ihre Signale binden; **Tabellenstruktur nicht korrekt**. Kein genereller OCR-Fall, sondern Koordinaten-/Strukturanalyse nötig |

### Tatsächliche Text-/Chunking-Messungen

Der V2-Algorithmus `split_page(text, max_chars=4000)` wurde
auf allen drei `extracted.txt`-Dateien mit der aktuellen Implementierung
nachgerechnet (einschließlich exakter Zeichenverkettung):

| PDF-Seite | Rohtext-Zeichen | Chunk-Längen | Exakte Rekonstruktion |
|---|---:|---|---|
| USB 2.0 S. 601 | 4.584 | 3.925 + 659 | ja |
| USB 2.0 S. 606 | 4.718 | 3.969 + 749 | ja |
| Matrox G200 S. 522 | 19.711 | 3.257 + 2.607 + 2.653 + 3.872 + 3.886 + 3.436 | ja |

**Wichtig:** Exakte Rekonstruktion bestätigt nur, dass beim Teilen keine
Zeichen verloren gingen. Die USB-Chunks enthalten weiterhin semantisch
vermischte Spalten; die G200-Chunks enthalten keine verlässlich auslesbare
Pin-zu-Signal-Zuordnung. Der `pdf_quality`-Bericht für G200 S. 522
zeigt 19.686 Zeichen nach `strip()`, dagegen enthält die tatsächlich
extrahierte Rohtextdatei 19.711 Zeichen. Davon sind ca. **90,7 %**
Whitespace-Zeichen (Leerzeichen und Zeilenumbrüche).

### Konsequenzen für Stufe 3

1. Bei gesicherter Mehrspaltigkeit Textblöcke mit Koordinaten auswerten:
   zuerst Spalten segmentieren, dann innerhalb jeder Spalte in
   Leserichtung sortieren. Indexseiten nicht als normaler Fließtext behandeln.
2. Technische Matrizen als **strukturiertes 2D-Artefakt mit Zellkoordinaten**
   führen (inklusive überprüfbarer Originalseiten-Referenz), **nicht**
   in normale zeichenbasierte RAG-Chunks umwandeln.
3. Bis zur validierten Matrixrekonstruktion keine Fakten wie
   „Pin X entspricht Signal Y“ automatisch aus den G200-Textchunks
   übernehmen.
4. Leseordnung und Tabellenstruktur künftig getrennt von
   `split_page` testen. Eine bestandene Verlustfreiheitsprüfung ist
   keine Retrieval- oder Faktengenauigkeitsfreigabe.
5. Die drei lokal ausgegebenen `review.json` wurden als
   `reviewed` mit **negativen** Befunden zu Leseordnung/Matrix
   vorbereitet. Andere, nicht geprüfte Aspekte bleiben `null`.

Damit sind nun **7 von 14 Goldstandard-Seiten** visuell geprüft
(4 OCR-/Leerseitenfälle und 3 Layout-/Chunking-Fälle). Weitere
7 Seiten und die Korrekturalgorithmen sind offen. Keine vollständigen
Seitenbilder oder Extraktionstexte in GitHub übertragen; Write-Gate
bleibt geschlossen.
