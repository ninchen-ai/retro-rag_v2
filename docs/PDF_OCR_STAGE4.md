# PDF-OCR – Entwicklungsstufe 4 (11.11.2026)

## Umfang

Optionale, **schreibfreie** OCR im PDF-Adapter `read_pdf()`. Standard bleibt
`ocr_mode="off"`. Mit `ocr_mode="auto"` wird nur dann OCR versucht,
wenn die Seite weniger als 40 extrahierbare Zeichen **und** mindestens 50 %
geschätzte Bildabdeckung aufweist. Die Bildfläche ist ein Indikator, keine
garantierte Scan-Erkennung. Vektorseiten oder falsch erkannter eingebetteter
Text werden dadurch nicht automatisch repariert.

`ocr_pages={111}` erlaubt nach manueller Sichtprüfung eine einzelne
PDF-Seite gezielt zu bearbeiten (1-basiert). Nur in Kombination mit
`ocr_mode="auto"` zulässig. Der Originaltext anderer Seiten bleibt erhalten.
Verarbeitet wird mit PyMuPDF `get_textpage_ocr(full=True)`, Tesseract
läuft lokal. Es werden **keine** OCR-Daten in Original-PDFs zurückgeschrieben.
Keine Cloud, keine Datenbank, kein automatisch freigegebenes Indexing.

Beispiel auf Poseidon:

```bash
sudo apt install tesseract-ocr tesseract-ocr-eng tesseract-ocr-deu
cd ~/projects/retro-rag_v2
git fetch origin
git switch feat/pdf-ocr-stage4
git pull --ff-only
source .venv/bin/activate
python -m pip install -e '.[dev,pdf]'
python -m pytest -q tests/test_pdf_extraction.py tests/test_pdf_ocr.py
python -m ruff check src/retro_rag/importer/pdf.py \
  src/retro_rag/importer/pdf_ocr.py tests/test_pdf_ocr.py
```

OCR-Test eines **lokalen, autorisierten** PDFs ohne Persistenz:

```bash
python - <<'PY'
from pathlib import Path
from retro_rag.importer.pdf import read_pdf
contract = read_pdf(Path("/pfad/zur/cubx-103.pdf"), "local:ocr-validation",
                    ocr_mode="auto", ocr_pages={111},
                    ocr_language="eng+deu", ocr_dpi=200)
print("OCR-Seiten:", contract.document.metadata["ocr_pages"])
print("OCR-Fehler:", contract.document.metadata["ocr_failed_pages"])
print("Warnungen:", contract.warnings)
print("Indexierung erlaubt:", contract.indexing_allowed)
print("OCR-Seite 111:", "\n".join(c.text for c in contract.chunks if c.page == 111)[:1500])
PY
```

## Nachweis und offene Abnahme

- Pro Quellseite bleiben `Chunk.page`, `heading_path` und SHA-256 des
  Text-Chunks erhalten; PDF-Originalhash bleibt unverändert.
- `document.metadata` führt OCR-Modus, erfolgreich bearbeitete Seiten,
  fehlgeschlagene Seiten sowie bei Erfolg Engine, Sprache und DPI.
- OCR-Ausfall wird **nicht** verschwiegen: `ocr_failed_pages` und `warnings`
  zeigen Fehler; vorhandener Originaltext bleibt erhalten.
- Auch erfolgreiches OCR ist zunächst **ungeprüft**.
  `indexing_allowed=False` bleibt bestehen; keine DB-Schreibzugriffe.
- Reine Leerseiten ohne ausreichende Bildabdeckung bleiben ungeprüft.
- Tesseract wird nur bei tatsächlichem OCR-Bedarf benötigt.
- Die neue OCR-Testsuite verwendet synthetische PDFs und Mock-OCR; sie prüft
  Kontrollfluss und Rückfall, **nicht** die Qualität echter Tesseract-Erkennung.

**Automatisierte Abnahme auf Poseidon erfolgreich (11.11.2026):** Auf dem Branch
`feat/pdf-ocr-stage4` nach Korrektur des gebundenen Test-Mocks (`9b1dd4b`)
wurden `python -m pytest -q tests/test_pdf_extraction.py tests/test_pdf_ocr.py`
mit **17 passed in 0.15s** und `python -m ruff check
src/retro_rag/importer/pdf.py src/retro_rag/importer/pdf_ocr.py
tests/test_pdf_ocr.py` mit **All checks passed!** abgeschlossen.
Dies sind Regressionstests mit Mock-OCR, kein Nachweis über die Erkennungsqualität
von Tesseract auf realen Scans.

**Tesseract-End-to-End-Test auf Poseidon erfolgreich (11.11.2026):**
- Nextcloud-WebDAV lieferte `cubx-103.pdf`; Verarbeitung aus einem lokalen temporären Verzeichnis, ohne Schreiben nach Nextcloud oder in PostgreSQL.
- PDF-Seite 111: **0 Zeichen nativer PDF-Text**, OCR mit Tesseract 5.5.0 über PyMuPDF, `ocr_mode="auto"`, `ocr_pages={111}`, `ocr_language="eng+deu"`, `ocr_dpi=200`.
- Rückgabe: `ocr_pages=[111]`, `ocr_failed_pages=[]`, **1723 Zeichen** OCR-Ausgabe, `indexing_allowed=False`, keine Warnung zur Seite 111.
- Erkennbare Textteile: „AGP-V6800“, „300MHz DDR video memory“, „32MB DDR SGRAM“, „OpenGL“. Der Kopfbereich enthält deutlich fehlerhafte Zeichenfolgen und durch die Gestaltung verursachte Artefakte.
- **Einordnung:** technischer Durchlauf erfolgreich, keine fachliche Qualitätsfreigabe. Die OCR-Ergebnisse wurden anhand der Textausgabe betrachtet, aber noch nicht systematisch mit einer visuellen Ground-Truth-Transkription verglichen. 1723 Zeichen und fehlende Laufzeitfehler sind keine Aussage über OCR-Präzision.

**Noch offen vor Qualitätsabnahme:** visuell geprüfte Referenztranskription und Vergleich technischer Bezeichnungen/Zahlen, Wiederholung auf anderen Scan-Typen (`507700.pdf` S. 24), ggf. Bildvorverarbeitung oder Bereichs-OCR bei grafisch gestalteten Seiten. Fehlerhaften OCR-Text nicht als bestätigten Fakt übernehmen; die Gate-Sperre bleibt geschlossen.

## Grenzen

`full=True` ersetzt für ausgewählte Seiten den extrahierten Text durch
OCR-Text; daher nur scanverdächtige oder explizit geprüfte Seiten bearbeiten.
Mehrspalten-/Tabellenstruktur und Lesereihenfolge sind dadurch nicht validiert.
Ein OCR-Ergebnis kann fachlich falsch sein, auch wenn es nicht leer ist.
Für fortgeschrittene partielle OCR/Layout-Rekonstruktion ist eine separate
Evaluation nötig.