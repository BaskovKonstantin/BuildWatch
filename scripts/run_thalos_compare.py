"""Run the external Thalos checkpoint on project images and write a comparison report."""
from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images", type=Path, default=ROOT / "context" / "dgp_extract" / "samples")
    parser.add_argument("--weights", type=Path, default=ROOT / "context" / "weights" / "thalos" / "heavy_equipment_weights.pt")
    parser.add_argument("--output", type=Path, default=ROOT / "context" / "thalos_compare.json")
    parser.add_argument("--conf", type=float, default=0.15)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--device", default="0")
    parser.add_argument("--pattern", default="Screenshot_*.png")
    args = parser.parse_args()
    from ultralytics import YOLO

    images = sorted(args.images.glob(args.pattern))
    load_start = time.perf_counter()
    model = YOLO(str(args.weights))
    load_s = time.perf_counter() - load_start
    rows = []
    counts = Counter()
    infer_s = 0.0
    for image in images:
        with Image.open(image) as opened:
            width, height = opened.size
        start = time.perf_counter()
        result = model.predict(str(image), conf=args.conf, imgsz=args.imgsz, device=args.device, verbose=False)[0]
        infer_s += time.perf_counter() - start
        detections = []
        for box in result.boxes:
            raw = str(result.names[int(box.cls[0])])
            label = {
                "backhoe_loader": "loader", "compactor": "road roller",
                "concrete_mixer_truck": "concrete mixer", "dozer": "bulldozer",
                "dump_truck": "dump truck", "mobile_crane": "mobile crane",
                "tower_crane": "tower crane", "wheel_loader": "loader",
            }.get(raw, raw)
            counts[label] += 1
            detections.append({"label": label, "score": float(box.conf[0]), "box": [float(v) for v in box.xyxy[0].tolist()]})
        rows.append({"image": image.name, "width": width, "height": height, "detections": detections})
    report = {
        "device": args.device,
        "weights": str(args.weights),
        "results": {"thalos": {
            "summary": {
                "images": len(images),
                "images_with_any_box": sum(bool(row["detections"]) for row in rows),
                "total_boxes": sum(counts.values()),
                "by_class": dict(counts),
                "load_s": load_s,
                "infer_s": infer_s,
                "per_image_s": infer_s / len(images) if images else None,
            },
            "detail": {"rows": rows},
        }},
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["results"]["thalos"]["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
