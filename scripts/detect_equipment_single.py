# -*- coding: utf-8 -*-
"""Sliced trained equipment detector for BuildWatch (Windows venv, CPU).

Input: JSON file {image, weights, out} (Windows paths, passed by the API).
Output: JSON {model, image, detections: [{label, score, box:[x1,y1,x2,y2]}]}.

Closed-class YOLOv8m@1280 trained on external construction equipment data
(context/external/equipment_external_v2/training_run_m1280). Inference runs at
the training resolution (1280) so small machinery is not lost.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

IMGSZ = 1280
CONF = 0.15
SLICE_SIZE = 1280
SLICE_OVERLAP = 0.15
MERGE_THRESHOLD = 0.5


def main() -> None:
    args = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    image_path = Path(args["image"])
    out_path = Path(args["out"])
    weights = args.get("weights", "yolov8s-world.pt")
    model_name = str(args.get("model") or "equipment")

    from sahi import AutoDetectionModel
    from sahi.predict import get_sliced_prediction

    model = AutoDetectionModel.from_pretrained(
        model_type="ultralytics",
        model_path=str(weights),
        confidence_threshold=CONF,
        device="cpu",
        image_size=IMGSZ,
    )
    result = get_sliced_prediction(
        str(image_path),
        model,
        slice_height=SLICE_SIZE,
        slice_width=SLICE_SIZE,
        overlap_height_ratio=SLICE_OVERLAP,
        overlap_width_ratio=SLICE_OVERLAP,
        # Keep a full-frame pass so large equipment is still evaluated at
        # scene scale; SAHI shifts and merges these boxes with tile results.
        perform_standard_pred=True,
        postprocess_type="GREEDYNMM",
        postprocess_match_metric="IOS",
        postprocess_match_threshold=MERGE_THRESHOLD,
        postprocess_class_agnostic=False,
        verbose=0,
    )
    detections = []
    for prediction in result.object_prediction_list:
        detections.append({
            "label": prediction.category.name,
            "score": float(prediction.score.value),
            # SAHI returns tile predictions shifted back into original-image
            # coordinates and merges duplicate boxes across overlapping tiles.
            "box": [float(v) for v in prediction.bbox.to_xyxy()],
        })
    payload = json.dumps(
        {"model": model_name, "image": image_path.name, "detections": detections},
        ensure_ascii=False,
    )
    temporary = out_path.with_name(out_path.name + ".tmp")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(out_path)


if __name__ == "__main__":
    # ultralytics checkpoints need weights_only=False under torch>=2.6.
    _orig_load = None
    import torch

    _orig_load = torch.load

    def _patched_load(*args, **kwargs):
        return _orig_load(*args, **{**kwargs, **({} if "weights_only" in kwargs else {"weights_only": False})})

    torch.load = _patched_load  # type: ignore[assignment]
    main()
