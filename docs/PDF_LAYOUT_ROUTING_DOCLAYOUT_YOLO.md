# PDF-Stufe 3: getrennte Verarbeitungswege und DocLayout-YOLO (Architekturentscheidung)

Stand: 10.11.2026 – **Entwurf, keine Produktionsfreigabe**

## Ausgangslage

Die V2-Qualitätsanalyse von 29 Nextcloud-Quellen (28 eindeutige PDFs, 4.953 eindeutige Seiten) war technisch erfolgreich. Die sieben bislang visuell geprüften Goldstandard-Seiten haben aber getrennte Problemklassen aufgedeckt:

- CUBX S. 111, 3Com-Cover S. 1 und DirectX-Cover S. 2: bildbasierter Text, daher OCR sinnvoll;
- CUBX S. 112: tatsächlich leere Seite, keine OCR;
- USB 2.0 S. 601/606: zweispaltiger Index, PyMuPDF `sort=True` verschränkt Spalten;
- Matrox G200 S. 522: 2D-Pinmatrix; reine Text-Chunks verlieren die Zellen-/Pinzuordnung.

Daher **keinen einheitlichen PDF-zu-Text-zu-Chunk-Pfad** und keine semantische Freigabe allein aus Textmenge, Geometrie oder Detektor-Confidence.

## Nachgewiesene V1-Vorarbeiten

Quelle: [V1-Branch `feature/pdf-chapter-chunking`](https://github.com/ninchen-ai/retro-rag/tree/feature/pdf-chapter-chunking)

| V1-Datei | Verantwortlichkeit | V2-Entscheidung |
|---|---|---|
| `experiments/doclayout_cpu_benchmark.py` | DocLayout-YOLO v10, Dokument-Layoutklassen/BBox/Confidence aus gerendertem PNG; isolierte CPU-Ausführung | Als **optionalen, isolierten Inferenzadapter** neu fassen, zunächst CPU-Baseline |
| `experiments/pdf_layout_joint_review.py` | Pixel-zu-PDF-Punkte und räumliche Nähe zwischen Layoutregionen und PyMuPDF-Textelementen | Validierte Geometrie-Funktionen und Tests portieren; gleiche Bildversion überprüfen |
| `experiments/pdf_auto_label_instances.py` | Quelltext-Spans an Abbildungen zuordnen, Doppelzeichnungen geometrisch unterscheiden | Für figure-/pinout-bezogene Textlabels adaptieren |
| `experiments/pdf_table_region_review.py` | Tabellen-Caption und YOLO-Region geometrisch vorschlagen | Getrenntes Caption-/Region-Review statt voreiliger Matrixzuordnung |
| `experiments/pdf_table_quality_review.py` | YOLO-Region gegen PyMuPDF-Matrix/Zellen via IoU verknüpfen | Komplementäre Detektoren nutzen; **IoU ist kein Beleg für Zellrichtigkeit** |
| `experiments/pdf_layout_conflict_review.py` | figure/table-Konflikte, Überlappungen, mögliche Multipart-Tabellen sichtbar machen | Ambiguitäten als Review-Items erhalten |
| `experiments/pdf_table_composition_v02.py` | Kontrollierte horizontale Fortsetzung zweier Tabellenmatrizen, Rohzellen unverändert, Provenienz pro Zeile | Vorschlagsmodell wiederverwenden, aber **nicht** als allgemeine Pin-Matrix-Lösung ausgeben |
| `experiments/evaluate_layout_reference.py` | Referenzbasierte Auswertung, ungeprüfte Labels ausgeschlossen | An die 14 V2-Goldstandardfälle adaptieren |
| `docs/pdf-structure-v0.2.md` und JSON-Schema v0.2 | Strukturelemente, physische Regionen, Relationen, Quellhash/Provenienz und Review | V2-Datenvertrag ableiten, **nicht** blind V1-DB-Schema übernehmen |
| `docs/pdf-structural-chunk-preview-v0.2.md` | Textidentität wahren, strukturierte Tabellen erst nach Review als separate Einheiten | Das V2-Prinzip `source_text != normalized_layout_view` festschreiben |

Die V1-Implementierung benutzte für DocLayout-YOLO das HuggingFace-Modell
`juliozhao/DocLayout-YOLO-DocStructBench`, Gewicht
`doclayout_yolo_docstructbench_imgsz1024.pt`, und die Bibliothek
`doclayout_yolo.YOLOv10`. Die Gewichte/Abhängigkeiten **nicht ungeprüft im
V2-Standard-venv installieren**: Versionen, Modelllizenz, reproduzierbare
SHA-256-Modellidentität und CPU/GPU-Kompatibilität zunächst verifizieren.

## V2-Verarbeitungspfade (vorgeschlagen)

```text
Nextcloud (nur lesen) → PDF-SHA256 / Versionsprüfung
   ├─ PyMuPDF-Seiten-Text, Spans, BBox, Bookmarks (unveränderte Evidenz)
   ├─ PDF-Render → DocLayout-YOLO → Layout-Regionen/Confidence
   └─ Qualitäts- und Konfliktanalyse
       ├─ A: einspaltiger Text → Kapitelhinweise → verlustfreie Textchunks
       ├─ B: mehrspaltiger Text → Spaltenregionen → spaltenweise Lesereihenfolge
       ├─ C: Tabellen/Register/Pin-Matrizen → Regionen+Zellen+Koordinaten
       │      → verifizierte strukturelle Einheiten (nicht als Fließtext)
       ├─ D: bildbasierter Text → lokales OCR pro Region/Seite
       │      → Text + Pixel-/PDF-Punkte + OCR-Provenienz
       ├─ E: Abbildungen/Diagramme → Bildregion + Caption/Span-Bezüge,
       │      bei Bedarf gesonderte Vision-/Review-Stufe
       └─ F: leere Seiten → keine OCR, nachvollziehbarer Skip
           ↓
       Review/Gegenprüfung → strukturierte, versionierte Artefakte
           ↓
       V2 ImportContract / Staging (spätere Integration; Write-Gate bleibt zu)
```

Ein Dokument kann **mehrere Verarbeitungswege auf verschiedenen Seiten und
innerhalb derselben Seite** haben; Routing daher regionsbasiert, nicht
ausschließlich pro PDF. YOLO ist ein geometrischer Vorschlagsgeber, kein
OCR-System und keine alleinige Quelle für Lesereihenfolge, Text oder Zellen.

## Daten-/Sicherheitsvertrag (für die nächste Implementierung)

Jede Layoutregion muss mindestens enthalten: Dokument-SHA-256, Quell-/Versionsbezug,
1-basierte PDF-Seite, Render-DPI und -Pixelabmessungen, Bild-SHA-256,
Modellkennung mit Gewichts-SHA-256, Klasse, rohe Confidence, Pixel-BBox
und umgerechnete PDF-Punkte-BBox, Review-Status `proposed`.
Eingabepixel dürfen nicht stillschweigend reskaliert oder gedreht werden.
Rotierte Seiten zunächst gesondert kennzeichnen und gegebenenfalls zum Review
führen. Originaltexte, Spans und `raw_cells` bleiben unverändert.

- Keine automatischen `confirmed`-Labels und keine Faktenfreigabe aus Confidence.
- Geometrische Konflikte und unklare Regionszuordnungen als Review-Fälle führen.
- Nicht mit Textchunk-Hash gleichsetzen: eine neu sortierte Lesereihenfolge
  ist ein **abgeleitetes** Artefakt, keine Änderung des Quellenextrakts.
- Pinmatrix-Fakten müssen eindeutige 2D-Zellpositionen und Seitenbelege haben.
- Artefakte mit privaten Seitentexten/Bildern lokal speichern; nicht nach GitHub.
- Read-only-Experimente dürfen das V2-Write-Gate und produktive Rollen nicht öffnen.

## Kontrollierte nächste Iteration

1. **Isolierter DocLayout-YOLO-Basistest** der vorhandenen Goldstandard-PNGs
   (USB S. 601/606, Matrox S. 522, CUBX S. 111, EHCI S. 43); mit V1-Modell-
   und Parameterstand anfangen, CPU/GPU-Laufzeit protokollieren.
2. Pixel-zu-PDF-Geometrie aus V1 mit Tests portieren, vollständige
   Modell-/Render-Provenienz erzwingen.
3. Detektionen mit Seitenbildern manuell gegenprüfen; insbesondere
   Spalten- und Matrixgrenzen statt bloßer Text-/Table-Counts bewerten.
4. Dann erst separat **Spaltenordnung** und **Tabellen-/Pinmatrix-Zellen**
   implementieren und am Goldstandard vergleichen.
5. OCR-Adapter für bestätigte bildbasierte Regionen ergänzen.
6. Erst nach fachlicher Abnahme Strukturartefakte in die bestehende
   Import-Pipeline integrieren; keine Änderung des Write-Gates vor Freigabe.

## Vorläufige Grenzen

Der GitHub-V1-Branch belegt ausführlichen Code und dokumentierte Testfälle
(z. B. Intel-875P-Table-5-Komposition); für die konkret jetzt hochgeladenen
USB-/Matrox-Seiten liegen **noch keine DocLayout-YOLO-Detektionen** vor.
Das Verhalten für diese Seiten muss gemessen werden, nicht vorausgesetzt.
