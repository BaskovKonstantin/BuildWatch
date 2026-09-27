# -*- coding: utf-8 -*-
"""One-shot Thalos heavy-equipment detector."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import torch

LABEL_FIXES = {
    "backhoe_loader": "loader",
    "compactor": "road roller",
    "concrete_mixer_truck": "concrete mixer",
    "dozer": "bulldozer",
    "dump_truck": "dump truck",
    "mobile_crane": "mobile crane",
    "tower_crane": "tower crane",
    "wheel_loader": "loader",
    "grader": "grader",
}


def main() -> None:
    args = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))
    from ultralytics import YOLO

    model = YOLO(args["weights"])
    results = model.predict(
        args["image"],
        conf=float(args.get("conf", 0.15)),
        imgsz=int(args.get("imgsz", 640)),
        device=args.get("device", "cpu"),
        verbose=False,
    )
    detections = []
    result = results[0]
    for box in result.boxes:
        raw = str(result.names[int(box.cls[0])])
        detections.append({
            "label": LABEL_FIXES.get(raw, raw),
            "score": float(box.conf[0]),
            "box": [float(v) for v in box.xyxy[0].tolist()],
        })
    output = Path(args["out"])
    payload = json.dumps({"model": "thalos", "image": Path(args["image"]).name, "detections": detections}, ensure_ascii=False)
    temporary = output.with_name(output.name + ".tmp")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(output)


if __name__ == "__main__":
    _orig_load = torch.load
    torch.load = lambda *a, **k: _orig_load(*a, **{**k, "weights_only": False}) if "weights_only" not in k else _orig_load(*a, **k)
    main()
