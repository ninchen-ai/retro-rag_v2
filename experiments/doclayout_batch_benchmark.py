"""Isolierter, schreibfreier DocLayout-YOLO-Batchbenchmark für lokale PNGs.

Benötigt die SEPARATE Python-Umgebung mit doclayout_yolo, PyTorch und Pillow.
Weder Modellgewichte noch Abhängigkeiten werden automatisch geladen.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import sys
import time
from datetime import UTC, datetime
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalize_detections(result, width: int, height: int) -> list[dict]:
    """Originaldetektionen mit gültigen Pixelkoordinaten; keine Freigaben."""
    if width <= 0 or height <= 0:
        raise ValueError("Ungültige Bildabmessungen")
    detections = []
    for box in (result.boxes if result.boxes is not None else []):
        cls = int(box.cls[0].item())
        confidence = float(box.conf[0].item())
        coords = [float(value) for value in box.xyxy[0].tolist()]
        if len(coords) != 4 or not all(math.isfinite(v) for v in coords):
            raise ValueError("Nicht-endliche Modell-Bounding-Box")
        x0, y0, x1, y1 = coords
        if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height):
            raise ValueError(f"Detektorbox außerhalb der Bildgrenzen: {coords}")
        if not 0 <= confidence <= 1:
            raise ValueError("Ungültige Confidence")
        detections.append({
            "class_name": str(result.names[cls]),
            "confidence": round(confidence, 5),
            "bbox_pixels": [round(value, 2) for value in coords],
            "review_status": "proposed",
        })
    return sorted(detections, key=lambda d: (
        d["bbox_pixels"][1], d["bbox_pixels"][0], d["class_name"],
    ))


def prepare_inputs(root: Path, maximum: int, cases: list[str] | None = None) -> list[Path]:
    if maximum < 0:
        raise ValueError("max-images muss >= 0 sein")
    if not root.is_dir():
        raise ValueError(f"Goldstandard-Ordner fehlt: {root}")
    paths = sorted(root.glob("*/page.png"))
    if not paths:
        raise ValueError("Keine Goldstandard-PNG-Dateien gefunden")
    if cases:
        chosen = []
        seen = set()
        for prefix in cases:
            matches = [path for path in paths if path.parent.name.startswith(prefix)]
            if len(matches) != 1:
                raise ValueError(f"Fallfilter {prefix!r}: {len(matches)} Treffer statt genau einem")
            if matches[0] in seen:
                raise ValueError(f"Doppelter Fallfilter: {prefix}")
            seen.add(matches[0])
            chosen.append(matches[0])
        paths = chosen
    return paths[:maximum] if maximum else paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path,
                        default=Path("/tmp/retro-v2-pdf-goldstandard"))
    parser.add_argument("--weights", type=Path, required=True,
                        help="Bereits vorhandene lokale .pt-Datei; KEIN automatischer Download")
    parser.add_argument("--out", type=Path,
                        default=Path("/tmp/retro-v2-doclayout-benchmark"))
    parser.add_argument("--device", default="cpu", choices=("cpu", "cuda:0"))
    parser.add_argument("--imgsz", type=int, default=1024)
    parser.add_argument("--conf", type=float, default=0.2)
    parser.add_argument("--max-images", type=int, default=0)
    parser.add_argument("--case", action="append", default=[],
                        help="Eindeutiges Fallverzeichnis-Präfix; mehrfach möglich")
    parser.add_argument("--annotate", action="store_true",
                        help="Lokal annotierte Vorschau speichern")
    args = parser.parse_args()
    if args.imgsz < 256 or args.imgsz > 2048 or not 0 < args.conf < 1:
        parser.error("imgsz muss 256..2048 und conf im Bereich 0..1 liegen")
    if args.out.exists():
        parser.error("Ausgabeordner bereits vorhanden; alte Ergebnisse nicht überschreiben")
    weights = args.weights.expanduser().resolve(strict=True)
    if not weights.is_file() or weights.suffix != ".pt":
        parser.error("Gewichte müssen eine vorhandene lokale .pt-Datei sein")
    images = prepare_inputs(args.input, args.max_images, args.case)
    weights_hash = sha256(weights)

    # Modelle/weights können beim Laden Code ausführen: ausschließlich
    # vertrauenswürdige, vorab geprüfte Gewichte benutzen.
    from doclayout_yolo import YOLOv10
    from PIL import Image
    import torch

    if args.device.startswith("cuda") and not torch.cuda.is_available():
        parser.error("CUDA angefordert, aber keine CUDA-fähige GPU verfügbar")
    model = YOLOv10(str(weights))
    args.out.mkdir(parents=True, exist_ok=False)
    runs: list[dict] = []
    metadata = {
        "created_at": datetime.now(UTC).isoformat(),
        "mode": "read_only_pdf_layout_proposals",
        "completed": False,
        "device": args.device,
        "python_version": platform.python_version(),
        "torch_version": torch.__version__,
        "weights_name": weights.name,
        "weights_sha256": weights_hash,
        "image_size_parameter": args.imgsz,
        "confidence_threshold": args.conf,
        "approved": False,
        "runs": runs,
    }

    def save() -> None:
        (args.out / "manifest.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    save()
    for n, image_path in enumerate(images, start=1):
        rel = image_path.relative_to(args.input)
        case_id = rel.parent.name
        image_hash = sha256(image_path)
        with Image.open(image_path) as image:
            width, height = image.size
        entry = {
            "case_id": case_id,
            "source_image": str(rel),
            "image_sha256": image_hash,
            "image_width": width,
            "image_height": height,
            "review_status": "proposed",
        }
        try:
            start = time.perf_counter()
            result = model.predict(
                str(image_path), device=args.device, imgsz=args.imgsz,
                conf=args.conf, verbose=False,
            )[0]
            entry["seconds"] = round(time.perf_counter() - start, 4)
            entry["detections"] = normalize_detections(result, width, height)
            entry["status"] = "ok"
            if args.annotate:
                # YOLO/Ultralytics plot liefert BGR; lokale PNG nur als Reviewhilfe.
                annotated = Image.fromarray(result.plot()[..., ::-1])
                annotated.save(args.out / f"{case_id}-annotated.png")
        except (RuntimeError, ValueError, TypeError, OSError, KeyError) as exc:
            entry["status"] = "error"
            entry["error"] = f"{type(exc).__name__}: {exc}"
        runs.append(entry)
        save()
        print(
            f"[{n}/{len(images)}] {case_id}: {entry['status']}"
            + (f", {entry['seconds']} s" if "seconds" in entry else ""),
            flush=True,
        )
    metadata["completed"] = True
    save()
    print(f"Lokaler Bericht: {args.out / 'manifest.json'}")
    return 0 if all(row["status"] == "ok" for row in runs) else 1


if __name__ == "__main__":
    sys.exit(main())
