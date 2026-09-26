# -*- coding: utf-8 -*-
"""One-shot trained equipment detector for BuildWatch (Windows venv, CPU).

Input: JSON file {image, weights, out} (Windows paths, passed by the API).
Output: JSON {image, detections: [{label, score, box:[x1,y1,x2,y2]}]}.

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


def main() -> None:
    args = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    image_path = Path(args["image"])
    out_path = Path(args["out"])
    weights = args.get("weights", "yolov8s-world.pt")

    from ultralytics import YOLO

    model = YOLO(weights)
    result = model.predict(str(image_path), conf=CONF, imgsz=IMGSZ, device="cpu", verbose=False)[0]
    detections = []
    if result.boxes is not None:
        for box in result.boxes:
            detections.append({
                "label": result.names.get(int(box.cls[0]), str(int(box.cls[0]))),
                "score": float(box.conf[0]),
                "box": [float(v) for v in box.xyxy[0].tolist()],
            })
    payload = json.dumps(
        {"model": "equipment", "image": image_path.name, "detections": detections},
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
