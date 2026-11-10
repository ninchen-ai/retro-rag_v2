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
