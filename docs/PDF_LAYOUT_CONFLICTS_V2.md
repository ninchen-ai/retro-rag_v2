# DocLayout-YOLO: Konflikterkennung im V2-Manifest

Stand 10.11.2026. Portierung der geometrischen V1-Konfliktlogik aus
`feature/pdf-chapter-chunking/experiments/pdf_layout_conflict_review.py`
in das aktuelle V2-Batchformat. **Nur Review-Hinweise, keinerlei Freigaben.**

## Implementierung

`experiments/pdf_layout_conflicts_v2.py` verarbeitet ein vollständig
abgeschlossenes, unfreigegebenes `manifest.json` des
`doclayout_batch_benchmark.py`. Das Originalmanifest bleibt unverändert.
Alle Vergleiche finden ausschließlich in den **Pixelkoordinaten desselben
Eingabebildes** statt; es findet keine Pixel-zu-PDF-Punkte-Transformation
und keine neue Modellinferenz statt.

Konflikttypen:
- `FIGURE_TABLE_CLASS_CONFLICT`: `figure` und `table` überlappen mit IoU >= 0,75.
- `TITLE_CAPTION_CLASS_CONFLICT`: `title` und `table_caption` überlappen mit IoU >= 0,75.
- `ABANDON_CONTENT_CONFLICT`: `abandon` überlappt eine Klasse mit potentiell relevantem Inhalt (Titel, Text, Tabellen/Captions) mit IoU >= 0,75.
- `OVERLAPPING_TABLE_REGIONS`: zwei `table`-Boxen überdecken wenigstens 80 % der kleineren Box.

Die letzten beiden V2-spezifischen Erweiterungen berücksichtigen auch
den beobachteten USB-Konflikt und gesonderte Tabellenüberschriften.
Die V1-Heuristik für mögliche seitlich fortgesetzte Tabellen und die
Kombination mit PyMuPDF-Zellmatrizen folgen **erst nach** verifizierter
PDF-Geometrie-Anbindung. Überlappungen allein begründen keine Auswahl
einer Klasse und dürfen keine Inhalte entfernen.

## Ergebnisse des ersten realen Benchmarks

Eingabe: vom Poseidon-Lauf bereitgestelltes
`/tmp/retro-v2-doclayout-layout-cases/manifest.json` mit
3 erfolgreichen Detektionsläufen, 19 Detections. Die neue Konfliktlogik
wurde dagegen lokal schreibfrei getestet:

| Dokument | Konflikte |
|---|---|
| USB 2.0, S. 601 | `ABANDON_CONTENT_CONFLICT` zwischen Kopftext/`title` und `abandon`, IoU 1,0 |
| USB 2.0, S. 606 | Keine der vier modellierten Klassenüberschneidungen |
| MGA-G200, S. 522 | `TITLE_CAPTION_CLASS_CONFLICT`, IoU 1,0 und `FIGURE_TABLE_CLASS_CONFLICT`, IoU 1,0 |

**Keine Konflikte erkannt** bedeutet weder, dass der Text vollständig
und richtig geordnet ist, noch dass die Seite fachlich freigegeben wäre.
USB S. 606 hat weiterhin das bekannte Problem der mit
`sort=True` falsch verschachtelten Indexspalten.

## Prüfung auf Poseidon

Die Konflikterkennung benötigt **keine** DocLayout-YOLO-/Torch-Abhängigkeit
und kann daher in der bestehenden V2-`.venv` getestet werden:

```bash
cd ~/projects/retro-rag_v2
git pull --ff-only
source .venv/bin/activate

python -m pytest -q tests/test_pdf_layout_conflicts_v2.py
python -m ruff check experiments/pdf_layout_conflicts_v2.py tests/test_pdf_layout_conflicts_v2.py

python experiments/pdf_layout_conflicts_v2.py \
  --manifest /tmp/retro-v2-doclayout-layout-cases/manifest.json \
  --out /tmp/retro-v2-doclayout-layout-cases/conflicts-review.json
```

Die Ausgabe ist ein **separater lokaler JSON-Bericht** und enthält
Fallbezüge, Konfikt-Indizes sowie Prüfsummen des vollständigen Manifests
und der Modellgewichte, aber keine Rohtexte oder PDFs. Vorhandene
Ausgabedateien werden nicht überschrieben. Ausgaben mit Seitenbezügen
und Hashwerten gehören nicht ins öffentliche Repository.

## Nächste Schritte

1. Pixel-BBox mit PDF-Seitenrotation, DPI, Bildidentität, Originalseitenmaßen
   in PDF-Punkte übertragen; alte V1-Tests adaptieren.
2. Für USB 601/606 Textspannen zuerst Region/Spalte und dann der
   vertikalen Reihenfolge zuordnen; originale Textspannen erhalten.
3. Für G200 522 gesonderte, überprüfbare Pinmatrix-Zellstruktur entwickeln.
4. Referenztests gegen Goldstandard, ohne Freigabe durch YOLO-Confidence.

## Nachweislage

12 synthetische Tests und eine echte 3-Seiten-Manifest-Auswertung wurden
lokal erfolgreich ausgeführt. **Poseidon-Tests stehen noch aus.** Der
V2-Write-Gate bleibt geschlossen; keine Import-/DB-Integration erfolgt.
