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


## Echte Adapterausgaben USB S. 601/606 ausgewertet (11.11.2026)

Vom Benutzer auf Poseidon erzeugte Dateien:
`retro-v2-usb-column-order-p601.json` und
`retro-v2-usb-column-order-p606.json`. Beide berichten
`status=REVIEW_REQUIRED`, `approved=false` und dieselbe PDF-SHA-256
`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`.

| Kriterium | S. 601 | S. 606 |
|---|---:|---:|
| Quellzeilen | 103 | 114 |
| Links zugeordnet | 50 | 56 |
| Rechts zugeordnet | 50 | 56 |
| Nicht zugeordnet | 3 | 2 |
| Zugeordnet gesamt | 100 (97,09 %) | 112 (98,25 %) |
| Referenzintegrität (eindeutige IDs, Quellhash, vollständige Abdeckung) | bestanden | bestanden |
| Reihenfolge (links vollständig vor rechts, innerhalb jeder Spalte y-sortiert) | bestanden | bestanden |

In Summe sind **212/217 (97,70 %) Zeilen** zugeordnet; **fünf
Zeilen sind nicht klassifiziert, aber in `source_lines` vollständig
erhalten**. Die gespeicherten SHA-256-Werte von konkatenierten
`source_text`-Zeilen wurden nachgerechnet; `proposed_text` stimmt
exakt mit `ordered_line_ids` überein. Keine doppelt zugeordneten
Quellzeilen und keine fehlenden Zeilen-IDs.

**S. 601, nicht zugeordnete Zeilen:**
- `0:0`: laufende Dokumentüberschrift
  `Universal Serial Bus Specification Revision 2.0`;
- `1:0`: gedruckte Seitenzahl `573` (PDF-Seite 601);
- `2:0`: **inhaltliche Abschnittsüberschrift `Index`**,
  im `proposed_text` noch nicht enthalten. Der Abschnittsbuchstabe
  `A` (`4:0`) ist dagegen korrekt in der linken Spalte enthalten.

**S. 606, nicht zugeordnete Zeilen:**
- `0:0`: laufende Dokumentüberschrift;
- `1:0`: gedruckte Seitenzahl `578` (PDF-Seite 606).

**Beobachtete Lesereihenfolge:** S. 601 endet links mit
`visible device state table, 9.1.1 Table 9-1` und beginnt rechts
mit `addresses`; S. 606 endet links mit
`overview, 5.12.2` und beginnt rechts mit
`clock model (continued)`. Die ursprüngliche zeilenweise
Spaltenvermischung von PyMuPDF `sort=True` ist für diese zwei
Testseiten in `proposed_text` behoben.

**Grenze der Bestätigung:** Geprüft sind Zeilenidentität,
geometrische Spaltenreihenfolge und markante Indexübergänge,
**nicht** die semantische Auflösung sämtlicher Indexeinträge
oder ihrer Fortsetzungszeilen. Die Quote ist eine
**Zuordnungsquote**, keine allgemeine Accuracy des Layoutmodells.
Insbesondere dürfen die fünf unzugeordneten Zeilen nicht
als in den endgültigen Text übernommen betrachtet werden.

### Konkrete Folgerungen

1. Separaten Review-Pfad für vorangestellte Abschnittsüberschriften
   (wie `Index`) implementieren: `heading` vor dem
   Spaltenhaupttext, mit Quellzeilen-ID und geometrischem Beleg;
   `abandon`-Kopf-/Fußzeilen bleiben erhalten, aber nicht automatisch
   in den Retrieval-Text übernommen.
2. Einen verlustfreien **Dokumentstruktur-Output** ergänzen, der
   `headings`, `columns`, `unassigned` und `source_lines`
   ausdrücklich trennt; `proposed_text` allein ist nicht
   vollständig.
3. Regressionstest mit den echten Fällen
   S. 601 (`Index`, `A`) und S. 606
   (`ClearHubFeature()` vor `clock model (continued)`).
4. `REVIEW_REQUIRED` und `approved=false` beibehalten, bis
   Überschriften und Restzeilen geprüft sowie die semantische
   Segmentierung des alphabetischen Index verifiziert sind.

Keine extrahierten Volltexte oder Seitenbilder in GitHub abgelegt.
Der V2-Write-Gate bleibt geschlossen.


## Erweiterung: Überschriften und Seitenmetadaten (11.11.2026)

Die bisherigen echten USB-Ausgaben belegen eine fehlende
`Index`-Abschnittsüberschrift vor der linken Spalte auf PDF-Seite 601.
Das Modul `experiments/pdf_column_order_v2.py` erzeugt daher zusätzlich
eine **strukturierte, weiterhin review-pflichtige Ansicht**:

- `structure.headings`: geometrisch belegte, vor beiden Textspalten
  liegende `title`-Zeilen ohne `abandon`-Überschneidung. Auf S. 601
  wird hier `Index` erwartet; der Buchstabe `A` bleibt Teil der
  linken Spalte.
- `structure.running_headers`: Zeilen oberhalb der Spalten mit
  `abandon`-Region. Bei gleichzeitiger `title`-Detektion bleibt
  `status=REVIEW_REQUIRED`, damit der Klassenkonflikt nicht verdeckt wird.
- `structure.page_numbers`: rein numerische, unter den Spalten liegende
  Zeilen mit `abandon`-Beleg.
- `structure.unresolved`: weiterhin nicht sicher zuordenbare Zeilen.
  Alle Elemente besitzen `line_id`, Quelltext, PDF-Punkte-BBox und
  Detektionsreferenzen.
- `proposed_text_with_headings`: vorgeschlagene Überschriften vor dem
  bisherigen links-dann-rechts-`proposed_text`, ohne Seitenmöbel.
  Das vorhandene `proposed_text` wird aus Kompatibilitätsgründen nicht
  verändert. `unassigned_line_ids` enthält weiterhin **alle** Zeilen
  außerhalb der Hauptspalten, auch wenn eine strukturelle Rolle
  vorgeschlagen wurde; `unresolved_line_ids` enthält nur echte
  Restfälle.

Die Zuordnung verwendet geometrische Regeln, **keine harte Sonderregel
für das Wort `Index`**. Ein Titel, der zugleich als `abandon`
erkannt wird, darf nicht ohne manuelle Prüfung als fachliche
Abschnittsüberschrift freigegeben werden.

Neue Regressionstests prüfen die getrennten Rollen, den Konfliktfall
`title`/`abandon`, unverändert erhaltene IDs und einen Fall, in dem
eine Überschrift mangels Detektornachweis ausdrücklich ungeklärt bleibt.
Die Testdatei wurde außerdem von einer versehentlichen Pillow-Importabhängigkeit
bereinigt.

### Test und reale Wiederholung auf Poseidon

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
    --out "/tmp/retro-v2-usb-column-order-structure-p${page}.json"
done
```

**Wichtig:** Neue Ausgabeziele verwenden, damit die vorherigen
`p601.json`/`p606.json` als Vergleichsreferenz erhalten bleiben.
Die erneut erzeugten Inhalte dürfen erst nach echtem Lauf und visueller
Gegenprüfung als bestätigt markiert werden.

Bis dahin gilt: **Implementiert und dokumentiert, aber noch nicht
auf Poseidon erneut getestet oder fachlich freigegeben.**
Write-Gate geschlossen.
