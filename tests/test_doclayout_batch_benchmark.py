"""Unit-Tests des isolierten DocLayout-Benchmarks ohne Torch/YOLO-Installation."""

import hashlib
import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "experiments" / "doclayout_batch_benchmark.py"
SPEC = importlib.util.spec_from_file_location("doclayout_batch_benchmark", SCRIPT)
benchmark = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(benchmark)


class Scalar:
    def __init__(self, value):
        self.value = value

    def item(self):
        return self.value


class Coords:
    def __init__(self, values):
        self.values = values

    def tolist(self):
        return self.values


class Box:
    def __init__(self, cls=1, conf=0.91, box=None):
        self.cls = [Scalar(cls)]
        self.conf = [Scalar(conf)]
        self.xyxy = [Coords(box or [5.0, 10.0, 50.0, 60.0])]


class Result:
    names = {1: "table", 2: "figure"}

    def __init__(self, boxes):
        self.boxes = boxes


def test_bbox_classification_is_proposal_only():
    detections = benchmark.normalize_detections(Result([Box()]), 100, 200)
    assert detections == [{
        "class_name": "table",
        "confidence": 0.91,
        "bbox_pixels": [5.0, 10.0, 50.0, 60.0],
        "review_status": "proposed",
    }]


def test_reject_out_of_bounds():
    with pytest.raises(ValueError, match="außerhalb"):
        benchmark.normalize_detections(Result([Box(box=[5, 10, 250, 60])]), 100, 200)


def test_reject_invalid_confidence_and_nonfinite_coordinates():
    with pytest.raises(ValueError, match="Confidence"):
        benchmark.normalize_detections(Result([Box(conf=2.0)]), 100, 200)
    with pytest.raises(ValueError, match="Nicht-endliche"):
        benchmark.normalize_detections(Result([Box(box=[0, 0, float("nan"), 50])]), 100, 200)


def test_empty_boxes():
    assert benchmark.normalize_detections(Result(None), 100, 200) == []


def test_image_discovery_sorted_and_limited(tmp_path):
    for name in ("b-case", "a-case", "c-case"):
        folder = tmp_path / name
        folder.mkdir()
        (folder / "page.png").write_bytes(b"png")
    assert [p.parent.name for p in benchmark.prepare_inputs(tmp_path, 2)] == [
        "a-case", "b-case",
    ]
    with pytest.raises(ValueError, match="max-images"):
        benchmark.prepare_inputs(tmp_path, -1)


def test_sha256_streaming(tmp_path):
    path = tmp_path / "weights.pt"
    path.write_bytes(b"known test bytes")
    assert benchmark.sha256(path) == hashlib.sha256(b"known test bytes").hexdigest()
