# -*- coding: utf-8 -*-
"""Compare trained equipment_v1 vs external checkpoints on a hold-out subsample with ground truth.

Only canonical classes each model is able to predict are counted for that model's
precision/recall (fair recall denominators). Ground truth is YOLO-format holdout labels.
"""
from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# canonical classes from ontology v1 (first release)
CANONICAL = {
    "excavator": "excavator",
    "dump truck": "dump_truck",
    "road roller": "road_roller",
    "crane manipulator": "crane_manipulator",
    "concrete mixer": "concrete_mixer",
    "bulldozer": "bulldozer",
    "truck": "truck",
    "mobile crane": "mobile_crane",
}

MODEL_CLASS_MAP = {
    "equipment_v1": {
        "excavator": "excavator",
        "dump truck": "dump_truck",
        "road roller": "road_roller",
        "crane manipulator": "crane_manipulator",
        "concrete mixer": "concrete_mixer",
        "bulldozer": "bulldozer",
        "truck": "truck",
        "mobile crane": "mobile_crane",
    },
    "thalos": {
        "excavator": "excavator",
        "mobile crane": "mobile_crane",
        "dump truck": "dump_truck",
        "road roller": "road_roller",
        # loader / tower crane are deferred classes in ontology v1
    },
    "uisikdag": {
        "Excavator": "excavator",
        "Mobile_crane": "mobile_crane",
        "Roller": "road_roller",
        "Bull_dozer": "bulldozer",
        # Worker / Loader / Safety helmet are deferred classes
    },
}


def iou(a, b) -> float:
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    union = area_a + area_b - inter
    return inter / union if union else 0.0


def load_gt(images_dir: Path, sample: list[str]) -> dict[str, list[tuple[str, list[float]]]]:
    gt = {}
    for name in sample:
        lbl = images_dir.parent / "labels" / (Path(name).stem + ".txt")
        objects = []
        if lbl.exists():
            img_path = images_dir / name
            from PIL import Image

            with Image.open(img_path) as im:
                w, h = im.size
            for line in lbl.read_text().splitlines():
                parts = line.split()
                if len(parts) != 5:
                    continue
                cls_id, cx, cy, bw, bh = int(parts[0]), *map(float, parts[1:])
                # class ids follow equipment.yaml order
                name_cls = CLASS_IDS[cls_id]
                x1 = (cx - bw / 2) * w
                y1 = (cy - bh / 2) * h
                x2 = (cx + bw / 2) * w
                y2 = (cy + bh / 2) * h
                objects.append((CANONICAL[name_cls], [x1, y1, x2, y2]))
        gt[name] = objects
    return gt


CLASS_IDS = {
    0: "excavator",
    1: "dump truck",
    2: "road roller",
    3: "crane manipulator",
    4: "concrete mixer",
    5: "bulldozer",
    6: "truck",
    7: "mobile crane",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--holdout", type=Path, default=ROOT / "context" / "external" / "equipment_external_v2" / "holdout" / "images")
    parser.add_argument("--sample-size", type=int, default=300)
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--iou-thr", type=float, default=0.5)
    parser.add_argument("--device", default="0")
    parser.add_argument("--output", type=Path, default=ROOT / "context" / "holdout_model_compare.json")
    args = parser.parse_args()

    from ultralytics import YOLO
    from PIL import Image

    all_images = sorted(p.name for p in args.holdout.glob("*.jpg"))
    random.seed(42)
    sample = sorted(random.sample(all_images, min(args.sample_size, len(all_images))))
    gt = load_gt(args.holdout, sample)
    print(f"sample: {len(sample)} images, gt objects: {sum(len(v) for v in gt.values())}")

    weights = {
        "equipment_v1": ROOT / "context" / "external" / "equipment_external_v2" / "training_run" / "runs" / "equipment_v1" / "weights" / "best.pt",
        "thalos": ROOT / "context" / "weights" / "thalos" / "heavy_equipment_weights.pt",
        "uisikdag": ROOT / "context" / "weights" / "uisikdag" / "best.pt",
    }

    results = {}
    for key, wpath in weights.items():
        model = YOLO(str(wpath))
        cmap = MODEL_CLASS_MAP[key]
        tp = Counter()
        fp = Counter()
        fn = Counter()
        infer_s = 0.0
        for name in sample:
            t0 = __import__("time").perf_counter()
            result = model.predict(str(args.holdout / name), conf=args.conf, device=args.device, verbose=False)[0]
            infer_s += __import__("time").perf_counter() - t0
            preds = []
            if result.boxes is not None:
                for box in result.boxes:
                    raw = result.names.get(int(box.cls[0]), str(box.cls[0]))
                    canon = cmap.get(raw)
                    if canon:
                        preds.append((canon, float(box.conf[0]), [float(v) for v in box.xyxy[0].tolist()]))
            preds.sort(key=lambda p: -p[1])
            truths = [t for t in gt[name] if t[0] in cmap.values() or t[0] == cmap.get(t[0])]
            # count only gt classes this model can predict
            gt_classes = set(cmap.values())
            truths = [t for t in gt[name] if t[0] in gt_classes]
            used = set()
            for canon, score, box in preds:
                matched = None
                for i, (gcls, gbox) in enumerate(truths):
                    if i in used or gcls != canon:
                        continue
                    if iou(box, gbox) >= args.iou_thr:
                        matched = i
                        break
                if matched is not None:
                    used.add(matched)
                    tp[canon] += 1
                else:
                    fp[canon] += 1
            for i, (gcls, _) in enumerate(truths):
                if i not in used:
                    fn[gcls] += 1
        per_class = {}
        for cls in sorted(set(tp) | set(fp) | set(fn)):
            p = tp[cls] / (tp[cls] + fp[cls]) if (tp[cls] + fp[cls]) else 0.0
            r = tp[cls] / (tp[cls] + fn[cls]) if (tp[cls] + fn[cls]) else 0.0
            per_class[cls] = {"precision": round(p, 3), "recall": round(r, 3), "tp": tp[cls], "fp": fp[cls], "fn": fn[cls]}
        tot_tp = sum(tp.values())
        tot_fp = sum(fp.values())
        tot_fn = sum(fn.values())
        results[key] = {
            "weights": str(wpath),
            "covered_classes": sorted(set(cmap.values())),
            "per_image_s": round(infer_s / len(sample), 4),
            "micro_precision": round(tot_tp / (tot_tp + tot_fp), 3) if tot_tp + tot_fp else 0.0,
            "micro_recall": round(tot_tp / (tot_tp + tot_fn), 3) if tot_tp + tot_fn else 0.0,
            "per_class": per_class,
        }
        r = results[key]
        print(f"{key}: P={r['micro_precision']} R={r['micro_recall']} ({r['per_image_s']}s/img)")

    args.output.write_text(json.dumps({"sample_size": len(sample), "conf": args.conf, "iou": args.iou_thr, "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved -> {args.output}")


if __name__ == "__main__":
    main()
