# -*- coding: utf-8 -*-
"""Run uisikdag/yolo-v5 construction detector via the pip `yolov5` package.

Notes:
- torch.hub does not work here (cache/module issues), and ultralytics 8.4 cannot
  load yolov5 checkpoints directly (it just AutoInstalls the same yolov5 pkg).
- torch>=2.6 defaults to weights_only=True, which the yolov5 package does not
  handle, so we monkeypatch torch.load for the trusted checkpoint load only.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import torch
from PIL import Image

from compare_detectors import OUT, REPORT, SAMPLES, WEIGHTS, draw_boxes, summarize

images = sorted(
    SAMPLES.glob("Screenshot_*.png"),
    key=lambda p: int("".join(ch for ch in p.stem if ch.isdigit()) or 0),
)
pt = WEIGHTS / "uisikdag" / "best.pt"

t0 = time.perf_counter()
import yolov5  # noqa: E402  (import after torch patching below)

_orig_load = torch.load
torch.load = lambda *a, **k: _orig_load(*a, **{**k, "weights_only": False})
model = yolov5.load(str(pt))
torch.load = _orig_load
model.conf = 0.15
load_s = time.perf_counter() - t0
names = model.names
print("names", names)

rows = []
infer_s = 0.0
for path in images:
    t1 = time.perf_counter()
    result = model(str(path), size=640)
    infer_s += time.perf_counter() - t1
    dets = []
    for *xyxy, conf, cls_id in result.pred[0].tolist():
        cls_id = int(cls_id)
        dets.append(
            {
                "label": str(names[cls_id]),
                "score": float(conf),
                "box": [float(v) for v in xyxy],
            }
        )
    rows.append({"image": path.name, "detections": dets})
    out = OUT / "uisikdag" / path.name
    out.parent.mkdir(parents=True, exist_ok=True)
    draw_boxes(Image.open(path), dets).save(out)
    print(path.name, len(dets), [d["label"] for d in dets])

pack = {
    "model": "uisikdag/yolo-v5 via pip yolov5 pkg",
    "class_names": names,
    "load_s": load_s,
    "infer_s": infer_s,
    "per_image_s": infer_s / max(len(images), 1),
    "rows": rows,
}
payload = json.loads(REPORT.read_text(encoding="utf-8"))
payload["results"]["uisikdag"] = {"summary": summarize(pack), "detail": pack}
payload.get("errors", {}).pop("uisikdag", None)
REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(payload["results"]["uisikdag"]["summary"], ensure_ascii=False, indent=2))
