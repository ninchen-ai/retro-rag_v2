# PDF-Layout: spaltenbasierte Lesereihenfolge (V2)

Stand 10.11.2026 – **schreibfreier Vorschlagsadapter, keine automatische Freigabe**

## Ausgangslage

Die USB-2.0-Indexseiten 601/606 sind zweispaltig. PyMuPDF `sort=True`
vermischt die linke und rechte Spalte zeilenweise. DocLayout-YOLO hat
diese Haupttextspalten auf beiden Seiten räumlich erfolgreich erkannt.
Die implementierte V1-Pixel-zu-PDF-Koordinatenumrechnung wird hier um
zeilenbasierte, review-pflichtige Zuordnung ergänzt.

**Wichtiger Testbefund:** Ein einzelner PyMuPDF-Textblock kann Zeilen
beider Spalten enthalten. Deshalb arbeitet der V2-Adapter mit
`page.get_text("dict", sort=False)` auf **Textzeilenebene**, nicht auf
kompletten Textblöcken.

## Neues Modul

- `experiments/pdf_column_order_v2.py`: kombiniert die unveränderte
  Nextcloud-PDF-Version (SHA-256 aus Qualitätsbaseline), das konkrete
  Goldstandard-`page.png` (SHA-256 aus DocLayout-Manifest) und
  die DocLayout-YOLO-Bounding-Boxes.
- Bestimmt aus den ausreichend großen und sicheren `plain text`-Regionen
  die zwei Hauptspalten. Ordnet einzelne PyMuPDF-Textzeilen per
  Überdeckungsanteil zu: mindestens 65 % in einer Spalte und höchstens
  15 % in der anderen.
- Führt zunächst alle Zeilen der linken, dann die der rechten Spalte
  in geometrischer Y-Reihenfolge als **abgeleiteten Textvorschlag** zusammen.
- Quellenzeilen, Bounding-Boxes, IDs und Text bleiben erhalten; Header,
  Fußzeilen oder unklare Zeilen werden als `unassigned_line_ids`
  separat ausgewiesen, nicht weggeworfen.
- Alle Ausgaben stehen auf `REVIEW_REQUIRED`, `approved=false`.
  Kein automatisches Zusammenführen mit dem produktiven Importvertrag,
  keine Änderung der Datenbank, keine Indexierung.
- Rotierte oder zugeschnittene Seiten, fehlende/mehrdeutige Spalten,
  ungültige Bild-/PDF-Prüfsummen werden nicht stillschweigend verarbeitet.
  Für solche Seiten sind separate Transformations- und Review-Fälle nötig.

## Reale USB-Tests auf Poseidon

Mit vorhandener V2-`.venv`, gesetzter Nextcloud-WebDAV-Konfiguration
und bereits erzeugten Goldstandard- und YOLO-Dateien:

```bash
cd ~/projects/retro-rag_v2
git pull --ff-only
source .venv/bin/activate

python -m pytest -q tests/test_pdf_column_order_v2.py
python -m ruff check experiments/pdf_column_order_v2.py tests/test_pdf_column_order_v2.py

for page in 601 606; do
  python experiments/pdf_column_order_v2.py \
    --quality-report /tmp/retro-v2-pdf-quality.json \
    --goldstandard /tmp/retro-v2-pdf-goldstandard \
    --manifest /tmp/retro-v2-doclayout-layout-cases/manifest.json \
    --name usb_20.pdf --page "$page" \
    --out "/tmp/retro-v2-usb-column-order-p${page}.json"
done
```

Das Passwort wird, sofern nicht in
`RETRO_V2_NEXTCLOUD_APP_PASSWORD` gesetzt, interaktiv abgefragt.
Bestehende Berichtdateien werden nicht überschrieben.

### Prüfmaßstab

- S. 601: Indexspalte links vollständig, danach rechts;
  Abschnitt `A` und Einträge in geometrisch richtiger Reihenfolge.
- S. 606: `ClearHubFeature()`-Einträge links **vor**
  `clock model (continued)` rechts.
- Jede ursprünglich extrahierte Textzeile muss in `source_lines`
  auffindbar sein. `unassigned_line_ids` manuell beurteilen.
- Die neue Ausgabe wurde **nicht automatisch mit dem Goldstandard
  abgeglichen**. Auch bei erfolgreichem Lauf bleibt eine manuelle
  Sichtkontrolle von `proposed_text` und des Original-PNG erforderlich.

## Tests und Grenzen

Sechs synthetische Tests in einer isolierten lokalen Umgebung bestätigt:
Geometrie, korrekte Spaltenordnung, unveränderte Zeilenevidenz,
unzuordenbarer Header, fehlende zweite Spalte, Bildhash und Rotation,
mehrdeutige YOLO-Fälle. **Tests und Ruff auf Poseidon noch offen.**

Das Verfahren kann noch nicht: Kopf-/Fußzeilen semantisch aufnehmen,
komplexe Textflussgruppen über Spaltengrenzen verfolgen,
gesonderte Fußnoten oder Tabellen korrekt zuordnen.
Für technische Pin-Matrizen bleibt ein vollständig getrennter
2D-Tabellenpfad vorgesehen.

**Write-Gate bleibt geschlossen.** Weder der YOLO-Confidence-Wert
noch die geometrische Spaltenzuordnung bewirken eine Freigabe.
