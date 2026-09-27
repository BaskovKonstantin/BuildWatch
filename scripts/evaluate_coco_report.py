"""Evaluate a detector report against a COCO ground-truth annotation file."""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

CLASSES = (
    "excavator", "dump truck", "road roller", "crane manipulator",
    "concrete mixer", "bulldozer", "truck", "mobile crane",
)


def iou(a, b):
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    union = area_a + area_b - inter
    return inter / union if union else 0.0


def evaluate_coco(coco_path: Path, report_path: Path, model: str, threshold: float = 0.35, iou_threshold: float = 0.5) -> dict:
    coco = json.loads(coco_path.read_text(encoding="utf-8"))
    mapping = {
        "Excavator": "excavator", "Truck": "truck", "Roller": "road roller",
        "Bulldozer": "bulldozer", "Concrete mixer": "concrete mixer",
        "Crane": "mobile crane",
    }
    categories = {
        category["id"]: mapping.get(category["name"])
        for category in coco.get("categories", [])
    }
    truth = defaultdict(list)
    for ann in coco.get("annotations", []):
        label = categories.get(ann.get("category_id"))
        if label not in CLASSES:
            continue
        x, y, width, height = ann["bbox"]
        truth[ann["image_id"]].append((label, [x, y, x + width, y + height]))
    image_names = {image["id"]: image["file_name"] for image in coco.get("images", [])}
    report = json.loads(report_path.read_text(encoding="utf-8"))
    payload = report.get("results", {}).get(model, {})
    predictions = {
        row["image"]: [
            {"label": item["label"], "score": float(item["score"]), "box": item["box"]}
            for item in row.get("detections", [])
            if item["label"] in CLASSES and float(item["score"]) >= threshold
        ]
        for row in payload.get("detail", {}).get("rows", [])
    }
    counts = defaultdict(Counter)
    for image_id, name in image_names.items():
        candidates = predictions.get(name, [])
        used = set()
        for label, box in truth.get(image_id, []):
            match = next((index for index, prediction in enumerate(candidates)
                          if index not in used and prediction["label"] == label
                          and iou(box, prediction["box"]) >= iou_threshold), None)
            if match is None:
                counts[label]["fn"] += 1
            else:
                used.add(match)
                counts[label]["tp"] += 1
        for index, prediction in enumerate(candidates):
            if index not in used:
                counts[prediction["label"]]["fp"] += 1
    classes = {}
    total = Counter()
    for label in CLASSES:
        count = counts[label]
        total.update(count)
        tp, fp, fn = count["tp"], count["fp"], count["fn"]
        classes[label] = {
            "support": tp + fn,
            "evaluated": bool(tp + fn),
            "tp": tp, "fp": fp, "fn": fn,
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
        }
    return {
        "model": model,
        "images": len(image_names),
        "threshold": threshold,
        "iou_threshold": iou_threshold,
        "classes": classes,
        "micro": {
            "tp": total["tp"], "fp": total["fp"], "fn": total["fn"],
            "precision": total["tp"] / (total["tp"] + total["fp"]) if total["tp"] + total["fp"] else 0.0,
            "recall": total["tp"] / (total["tp"] + total["fn"]) if total["tp"] + total["fn"] else 0.0,
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coco", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--model", default="thalos")
    parser.add_argument("--threshold", type=float, default=0.35)
    parser.add_argument("--iou", type=float, default=0.5)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = evaluate_coco(args.coco, args.report, args.model, args.threshold, args.iou)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
