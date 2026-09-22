# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import time
from pathlib import Path

from PIL import Image

from compare_detectors import (
    LABELS,
    OUT,
    REPORT,
    SAMPLES,
    WEIGHTS,
    draw_boxes,
    summarize,
)

images = sorted(
    SAMPLES.glob("Screenshot_*.png"),
    key=lambda p: int("".join(ch for ch in p.stem if ch.isdigit()) or 0),
)
payload = json.loads(REPORT.read_text(encoding="utf-8"))


def run_uisikdag_hub() -> dict:
    import torch
    from huggingface_hub import hf_hub_download

    pt = hf_hub_download(
        "uisikdag/yolo-v5-construction-machine-detection",
        "best.pt",
        local_dir=str(WEIGHTS / "uisikdag"),
    )
    t0 = time.perf_counter()
    model = torch.hub.load(
        "ultralytics/yolov5",
        "custom",
        path=pt,
        trust_repo=True,
        force_reload=False,
    )
    model.conf = 0.15
    load_s = time.perf_counter() - t0
    names = model.names
    rows = []
    infer_s = 0.0
    for path in images:
        t1 = time.perf_counter()
        result = model(str(path), size=640)
        infer_s += time.perf_counter() - t1
        dets = []
        for *xyxy, conf, cls_id in result.xyxy[0].tolist():
            cls_id = int(cls_id)
            name = names[cls_id] if isinstance(names, (list, dict)) else str(cls_id)
            if isinstance(names, dict):
                name = names[cls_id]
            dets.append(
                {
                    "label": str(name),
                    "score": float(conf),
                    "box": [float(v) for v in xyxy],
                }
            )
        rows.append({"image": path.name, "detections": dets})
        out_img = OUT / "uisikdag" / path.name
        out_img.parent.mkdir(parents=True, exist_ok=True)
        draw_boxes(Image.open(path), dets).save(out_img)
    return {
        "model": "uisikdag/yolo-v5 via torch.hub",
        "class_names": names,
        "load_s": load_s,
        "infer_s": infer_s,
        "per_image_s": infer_s / max(len(images), 1),
        "rows": rows,
    }


def run_dino() -> dict:
    from transformers import pipeline

    t0 = time.perf_counter()
    pipe = pipeline(
        "zero-shot-object-detection",
        model="IDEA-Research/grounding-dino-tiny",
        device=-1,
    )
    load_s = time.perf_counter() - t0
    rows = []
    infer_s = 0.0
    for path in images:
        image = Image.open(path).convert("RGB")
        t1 = time.perf_counter()
        preds = pipe(image, candidate_labels=LABELS, threshold=0.2)
        infer_s += time.perf_counter() - t1
        dets = []
        for p in preds:
            box = p["box"]
            dets.append(
                {
                    "label": p["label"],
                    "score": float(p["score"]),
                    "box": [
                        float(box["xmin"]),
                        float(box["ymin"]),
                        float(box["xmax"]),
                        float(box["ymax"]),
                    ],
                }
            )
        rows.append({"image": path.name, "detections": dets})
        out_img = OUT / "grounding_dino" / path.name
        out_img.parent.mkdir(parents=True, exist_ok=True)
        draw_boxes(image, dets).save(out_img)
    return {
        "model": "IDEA-Research/grounding-dino-tiny",
        "load_s": load_s,
        "infer_s": infer_s,
        "per_image_s": infer_s / max(len(images), 1),
        "rows": rows,
    }


for name, fn in (("uisikdag", run_uisikdag_hub), ("grounding_dino", run_dino)):
    print(f"=== {name} ===")
    try:
        pack = fn()
        payload["results"][name] = {"summary": summarize(pack), "detail": pack}
        payload.get("errors", {}).pop(name, None)
        print(json.dumps(payload["results"][name]["summary"], ensure_ascii=False, indent=2))
    except Exception as exc:
        payload.setdefault("errors", {})[name] = repr(exc)
        print(f"FAIL {name}: {exc!r}")

REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
print("wrote", REPORT)
