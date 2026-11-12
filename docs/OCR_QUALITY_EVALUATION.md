# OCR-Qualitätsbewertung – Stage 4, separater Abnahmeschritt

## Ziel

Die erfolgreiche Tesseract-Ausführung ist **kein** Qualitätsnachweis. Dieses
Werkzeug bewertet ausschließlich lokal erzeugte OCR-Texte gegen manuell
geprüfte Referenztranskriptionen. Es ändert weder Original-PDFs noch
Nextcloud, PostgreSQL oder den Index. Das Write-Gate bleibt geschlossen.

Ausgangspunkt: `feat/pdf-ocr-stage4`, insbesondere
`docs/PDF_OCR_STAGE4.md` und die durch `pdf_goldstandard.py` erzeugten
lokalen Pakete unter `/tmp/retro-v2-pdf-goldstandard`.

## Lokale Vorbereitung auf Poseidon

1. Im bestehenden Paketverzeichnis `page.png` visuell prüfen und die
   vollständige **korrekte** Transkription als UTF-8 `reference.txt` speichern.
   Nicht ungeprüft den OCR-Text als Referenz kopieren.
2. Den tatsächlich erzeugten OCR-Text **derselben PDF-Seite** unverändert als
   `ocr.txt` speichern. Engine, Sprachpakete, DPI und Preprocessing für den
   Vergleich separat notieren. Nach Möglichkeit dieselbe Quell-SHA-256 verwenden.
3. Erst nach manueller Referenzprüfung in `review.json` den Wert
   `review_status` auf `reviewed` setzen. Unter `reference` optional
   `"critical_terms": ["AGP-V6800", "300MHz", "32MB"]` ergänzen.
   Jeder dieser Begriffe muss in `reference.txt` tatsächlich vorkommen.
4. Für jedes ausgewählte Paket die drei Dateien `review.json`,
   `reference.txt` und `ocr.txt` bereitstellen.

Beispiel:

```bash
cd ~/projects/retro-rag_v2
git fetch origin
git switch feat/ocr-quality-evaluation
git pull --ff-only
source .venv/bin/activate
python -m pytest -q tests/test_ocr_evaluation.py
python -m ruff check src/retro_rag/importer/ocr_evaluation.py tests/test_ocr_evaluation.py

python -m retro_rag.importer.ocr_evaluation \
  --goldstandard-dir /tmp/retro-v2-pdf-goldstandard \
  --report /tmp/retro-v2-ocr-evaluation.json
```

## Kennzahlen

- **CER** = Levenshtein-Zeichendistanz / Anzahl Referenzzeichen.
- **WER** = Levenshtein-Wortdistanz / Anzahl Referenzwörter.
- Unicode-NFC und zusammengefasster Whitespace sorgen dafür, dass reine
  Zeilenumbrüche nicht automatisch als Fehler gezählt werden. Abweichende
  Lesereihenfolge beeinflusst die Scores weiterhin.
- **critical_term_recall** = mindestens so oft wie in der Referenz vorhandene
  exakte Fachbegriffe / Anzahl referenzierter Fachbegriffs-Vorkommen;
  der Abgleich ignoriert Groß-/Kleinschreibung, nicht aber Zeichen/Zahlen.
  Null, wenn geprüfte Terme vorliegen, aber keiner erkannt wurde; `null`
  falls keine Fachbegriffe hinterlegt sind.
- Die Metriken können über 1.0 liegen (insbesondere bei Einfügungen).
- Das Ergebnis `evaluated_not_approved` ist **keine** Freigabe.
  Es gibt derzeit bewusst keinen automatischen Grenzwert für Indexierung.

## Abnahmeplan

Zuerst `cubx-103.pdf` S. 111 (grafisch gestalteter Scan),
`3C905CX.pdf` S. 1 und `507700.pdf` S. 24 gegen eigene Referenzen
auswerten. Anschließend OCR-Varianten bei identischer Quellversion mit
200/300 DPI, `eng` gegenüber `eng+deu`, und bei Bedarf selektiven
Bildausschnitten vergleichen. Vor einer späteren Freigabe zusätzlich
Lesereihenfolge, Tabellen sowie technische Aussagen manuell bewerten.

Die Bewertung erfolgt nur für Pakete mit `review_status=reviewed`.
Nicht begutachtete oder unvollständige Fälle erscheinen im Bericht mit
`not_evaluated`; der CLI-Prozess endet dann mit Exitcode 1. Rohtexte,
private Quellkennungen und Referenzdateien **nicht ins öffentliche Repo**
committen. Auch Berichte mit PDF-Hashes ausschließlich lokal aufbewahren.

## Grenzen

CER/WER messen Textabweichungen und können wichtige Hardwarefehler
untergewichten. `critical_term_recall` prüft benannte Begriffe, aber noch
nicht, ob weitere erfundene technische Werte im OCR-Text stehen. Eine
gesonderte fachliche und Layout-Abnahme bleibt zwingend.

## Verifikation auf Poseidon (12.11.2026)

Nach Korrektur der Ruff-Hinweise TRY004 (TypeError statt ValueError)
und I001 (Importformatierung) auf `feat/ocr-quality-evaluation`
wurden durch den lokalen Projektlauf auf Poseidon bestätigt:

- `python -m pytest -q tests/test_ocr_evaluation.py`:
  **8 passed in 0.02s**
- `python -m ruff check src/retro_rag/importer/ocr_evaluation.py tests/test_ocr_evaluation.py`:
  **All checks passed!**

Diese Ergebnisse betreffen reine Regressionstests mit synthetischen
Referenz-/OCR-Texten, keine CER-/WER-Messung an echten Scans.

## Reproduzierbarkeit des Ausschnittvergleichs (12.11.2026)

Auf Poseidon wurde das lokal bereitgestellte Paket
`/tmp/retro-v2-ocr-specs` mit dem maskierten Ausschnitt der hochgeladenen
CUBX-Seite 111 erneut durch Tesseract (PSM 6) verarbeitet. Der Vergleich mit
`reference_provisional.txt` ergab dieselben **gerundeten** CER-/WER-Werte wie
im zuvor gelieferten Testpaket:

| Variante | CER | WER |
| --- | ---: | ---: |
| Paketdatei `eng` | 2,32 % | 15,00 % |
| Poseidon `eng` | 2,32 % | 15,00 % |
| Paketdatei `eng+deu` | 2,51 % | 16,25 % |
| Poseidon `eng+deu` | 2,51 % | 16,25 % |

**Grenzen:** Gleiche Scores sind kein Nachweis byteidentischer Texte (separater
`cmp`-Test steht noch aus). Der Ausschnitt stammt aus einem hochgeladenen PNG,
nicht aus einem verifiziert mit 200 DPI gerenderten Original-PDF. Die Referenz
ist noch nicht endgültig manuell freigegeben; die Werte sind deshalb eine
**vorläufige, reproduzierbare Experiment-Baseline**, keine OCR-Abnahme und
keine Erlaubnis zur Indexierung. Kein Datenbankschreibzugriff erfolgte.

Als nächstes den Textvergleich bytegenau durchführen, danach den identischen
technischen Bereich aus der SHA-256-geprüften Original-PDF bei definierten
200 DPI bearbeiten. Für den Vergleich von Ganzseiten- und Bereichs-OCR müssen
identische Referenzinhalte / Textregionen zugrunde liegen.
