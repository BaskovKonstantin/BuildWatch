# -*- coding: utf-8 -*-
"""Run the trained equipment_v1 detector on the Moscow smoke samples and merge into detector_compare.json."""
from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images", type=Path, default=ROOT / "context" / "dgp_extract" / "samples")
    parser.add_argument("--weights", type=Path, default=ROOT / "context" / "external" / "equipment_external_v2" / "training_run" / "runs" / "equipment_v1" / "weights" / "best.pt")
    parser.add_argument("--report", type=Path, default=ROOT / "context" / "detector_compare.json")
    parser.add_argument("--model-key", default="equipment_v1")
    parser.add_argument("--conf", type=float, default=0.15)
    parser.add_argument("--device", default="0")
    args = parser.parse_args()

    from ultralytics import YOLO

    images = sorted(args.images.glob("*.png"))
    if not images:
        raise SystemExit(f"no images under {args.images}")

    t0 = time.perf_counter()
    model = YOLO(str(args.weights))
    load_s = time.perf_counter() - t0

    rows = []
    infer_s = 0.0
    for path in images:
        t1 = time.perf_counter()
        result = model.predict(str(path), conf=args.conf, device=args.device, verbose=False)[0]
        infer_s += time.perf_counter() - t1
        dets = []
        if result.boxes is not None:
            for box in result.boxes:
                cls_id = int(box.cls[0])
                dets.append({
                    "label": result.names.get(cls_id, str(cls_id)),
                    "score": float(box.conf[0]),
                    "box": [float(v) for v in box.xyxy[0].tolist()],
                })
        rows.append({"image": path.name, "detections": dets})

    counts: Counter[str] = Counter()
    nonempty = 0
    for row in rows:
        if row["detections"]:
            nonempty += 1
        for d in row["detections"]:
            counts[d["label"]] += 1

    pack = {
        "summary": {
            "images": len(rows),
            "images_with_any_box": nonempty,
            "total_boxes": sum(len(r["detections"]) for r in rows),
            "by_class": dict(counts),
            "load_s": load_s,
            "infer_s": infer_s,
            "per_image_s": infer_s / len(rows),
        },
        "detail": {
            "model": str(args.weights),
            "load_s": load_s,
            "infer_s": infer_s,
            "per_image_s": infer_s / len(rows),
            "rows": rows,
        },
    }

    report = json.loads(args.report.read_text(encoding="utf-8"))
    report.setdefault("results", {})[args.model_key] = pack
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(pack["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
