# -*- coding: utf-8 -*-
"""One-shot YOLO-World detection for BuildWatch (Windows venv, CPU).

Input: JSON file {image, weights, out} (Windows paths, passed by the API).
Output: JSON {image, detections: [{label, score, box:[x1,y1,x2,y2]}]}.
Cold model load is slow (~4-5 min on CPU) — the API poller waits for it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import torch

LABELS = [
    "excavator", "dump truck", "truck", "bulldozer", "road roller",
    "concrete mixer", "mobile crane", "tower crane", "truck crane",
    "crane manipulator", "concrete pump", "drilling rig",
]


def main() -> None:
    args = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    image_path = Path(args["image"])
    out_path = Path(args["out"])
    weights = args.get("weights", "yolov8s-world.pt")

    from ultralytics import YOLOWorld

    model = YOLOWorld(weights)
    model.set_classes(LABELS)
    result = model.predict(str(image_path), conf=0.15, device="cpu", verbose=False)[0]
    detections = []
    if result.boxes is not None:
        for box in result.boxes:
            detections.append({
                "label": result.names.get(int(box.cls[0]), str(int(box.cls[0]))),
                "score": float(box.conf[0]),
                "box": [float(v) for v in box.xyxy[0].tolist()],
            })
    payload = json.dumps(
        {"model": "yolo_world", "image": image_path.name, "detections": detections},
        ensure_ascii=False,
    )
    temporary = out_path.with_name(out_path.name + ".tmp")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(out_path)


if __name__ == "__main__":
    # yolov5 checkpoints need weights_only=False under torch>=2.6.
    _orig_load = torch.load
    torch.load = (  # type: ignore[assignment]
        lambda *a, **k: _orig_load(*a, **{**k, "weights_only": False})
        if "weights_only" not in k else _orig_load(*a, **k)
    )
    main()
