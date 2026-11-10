# DocLayout-YOLO: isolierter Test auf Poseidon

## Zweck und Grenzen

Das V1-Skript aus dem Branch feature/pdf-chapter-chunking dient als Vorlage. Modell: juliozhao/DocLayout-YOLO-DocStructBench, Datei doclayout_yolo_docstructbench_imgsz1024.pt, imgsz 1024, conf 0.2. V2 erzeugt ausschließlich lokale Detektionsvorschläge und prüft die bereits exportierten Goldstandard-PNGs. Kein PDF-/Nextcloud-/Datenbank-Schreibzugriff, kein OCR und keine automatische Freigabe.

## Unit-Tests auf Poseidon

```bash
cd ~/projects/retro-rag_v2
git pull --ff-only
source .venv/bin/activate
python -m pytest -q tests/test_doclayout_batch_benchmark.py
python -m ruff check experiments/doclayout_batch_benchmark.py tests/test_doclayout_batch_benchmark.py
deactivate
```

## Separate Python-Umgebung

```bash
python3.11 -m venv ~/.venvs/retro-doclayout
source ~/.venvs/retro-doclayout/bin/activate
python -m pip install --upgrade pip
```

Installiere in dieser separaten Umgebung doclayout_yolo, PyTorch, Pillow und huggingface_hub nach deren kompatiblen Projektanleitungen. Eine feste Torch/CUDA-Version für die GTX 1060 wird bewusst nicht behauptet. CPU zuerst, GPU nach eigener Kompatibilitätsprüfung. Unveränderte V2-.venv und pyproject.toml.

## Modellgewichte

Vorher Quelle, Lizenz und Sicherheit prüfen. PyTorch-.pt-Dateien können beim Laden Code ausführen. Modellgewicht unter ~/models/doclayout-yolo ablegen, SHA-256 protokollieren und für reproduzierbare Folgeläufe die konkrete HuggingFace-Revision fixieren. Der Benchmark lädt **keine** Gewichte automatisch.

```bash
mkdir -p ~/models/doclayout-yolo
python - <<'PY'
from huggingface_hub import hf_hub_download
from pathlib import Path
import shutil

source = Path(hf_hub_download(
    repo_id="juliozhao/DocLayout-YOLO-DocStructBench",
    filename="doclayout_yolo_docstructbench_imgsz1024.pt",
))
target = Path.home() / "models/doclayout-yolo" / source.name
shutil.copy2(source, target)
print(target)
PY
sha256sum ~/models/doclayout-yolo/doclayout_yolo_docstructbench_imgsz1024.pt
```

## CPU-Baseline – zunächst drei Bilder

```bash
python experiments/doclayout_batch_benchmark.py \
  --input /tmp/retro-v2-pdf-goldstandard \
  --weights ~/models/doclayout-yolo/doclayout_yolo_docstructbench_imgsz1024.pt \
  --device cpu --imgsz 1024 --conf 0.2 \
  --max-images 3 --annotate \
  --out /tmp/retro-v2-doclayout-smoke
```

Dann alle 14 Prüfseiten in einem neuen Ausgabeverzeichnis:

```bash
python experiments/doclayout_batch_benchmark.py \
  --input /tmp/retro-v2-pdf-goldstandard \
  --weights ~/models/doclayout-yolo/doclayout_yolo_docstructbench_imgsz1024.pt \
  --device cpu --imgsz 1024 --conf 0.2 --annotate \
  --out /tmp/retro-v2-doclayout-full
```

Optional später --device cuda:0 in einem anderen Ausgabeordner. Keine GPU-Beschleunigung ohne Messung annehmen.

## Bericht und nächste Prüfung

Das lokal erzeugte manifest.json enthält pro Seite Pixelgrößen und SHA-256 der Eingabebilder, YOLO-Klassen, rohe Confidence, Pixel-Bounding-Boxes, Laufzeiten und Modellgewichts-SHA-256. Annotationen und Berichte nicht öffentlich einchecken. Vorhandene Ausgabeordner werden absichtlich nicht überschrieben. Nach Abbruch kann completed=false zurückbleiben.

- USB 2.0 Seite 601/606: Regionen und getrennte Lesereihenfolge prüfen.
- Matrox G200 Seite 522: Tabellen-/Abbildungsregionen, keine automatische Pinmatrix-Faktenübernahme.
- CUBX Seite 111: Bildbasierter Text, braucht weiterhin OCR.
- EHCI Seite 43: Detektorregionen mit PyMuPDF-Tabelle gegenprüfen.

Pixel-zu-PDF-Punkte muss anschließend mit Originalseitengröße, Rotation und Renderidentität aus dem V1-Geometrieadapter angepasst werden. Confidence ist keine fachliche Freigabe. Write-Gate bleibt geschlossen.

**Status:** Skript und Unit-Tests im GitHub-Branch vorhanden; noch nicht auf Poseidon mit echtem YOLO-Modell getestet.
