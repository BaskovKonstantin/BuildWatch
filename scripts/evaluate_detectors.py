"""Evaluate detector JSON reports against a manually annotated validation set."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.rules import normalize_label


def iou(a: list[float], b: list[float]) -> float:
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    union = area_a + area_b - inter
    return inter / union if union else 0.0


def load_annotations(path: Path) -> dict[str, list[dict]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("images"), list):
        raise ValueError("annotations must contain an images list")
    return {
        item["image"]: [
            {"label": normalize_label(obj["label"]), "box": obj["box"]}
            for obj in item.get("objects", [])
        ]
        for item in data["images"]
    }


def load_predictions(path: Path, model: str) -> tuple[dict[str, list[dict]], float | None]:
    data = json.loads(path.read_text(encoding="utf-8"))
    result = data.get("results", {}).get(model)
    if not result:
        raise ValueError(f"report has no results for model {model!r}")
    rows = result.get("detail", {}).get("rows", [])
    predictions = {
        row["image"]: [
            {"label": normalize_label(det["label"]), "score": float(det["score"]), "box": det["box"]}
            for det in row.get("detections", [])
        ]
        for row in rows
    }
    summary = result.get("summary", {})
    latency = summary.get("per_image_s")
    return predictions, float(latency) if latency is not None else None


def evaluate(annotations: dict[str, list[dict]], predictions: dict[str, list[dict]], threshold: float, iou_threshold: float) -> dict:
    counts: dict[str, Counter] = defaultdict(Counter)
    for image, truths in annotations.items():
        candidates = [p for p in predictions.get(image, []) if p["score"] >= threshold]
        used: set[int] = set()
        for truth in truths:
            label = truth["label"]
            match = next(
                (
                    (index, prediction)
                    for index, prediction in enumerate(candidates)
                    if index not in used
                    and prediction["label"] == label
                    and iou(truth["box"], prediction["box"]) >= iou_threshold
                ),
                None,
            )
            if match is None:
                counts[label]["fn"] += 1
            else:
                used.add(match[0])
                counts[label]["tp"] += 1
        for index, prediction in enumerate(candidates):
            if index not in used:
                counts[prediction["label"]]["fp"] += 1

    classes = {}
    for label, count in sorted(counts.items()):
        tp, fp, fn = count["tp"], count["fp"], count["fn"]
        classes[label] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": tp / (tp + fp) if tp + fp else 0.0,
            "recall": tp / (tp + fn) if tp + fn else 0.0,
        }
    total = Counter()
    for count in counts.values():
        total.update(count)
    return {
        "images": len(annotations),
        "threshold": threshold,
        "iou_threshold": iou_threshold,
        "classes": classes,
        "micro": {
            "tp": total["tp"],
            "fp": total["fp"],
            "fn": total["fn"],
            "precision": total["tp"] / (total["tp"] + total["fp"]) if total["tp"] + total["fp"] else 0.0,
            "recall": total["tp"] / (total["tp"] + total["fn"]) if total["tp"] + total["fn"] else 0.0,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--model", required=True, choices=("yolo_world", "uisikdag"))
    parser.add_argument("--threshold", type=float, default=0.35)
    parser.add_argument("--iou", type=float, default=0.5)
    args = parser.parse_args()
    annotations = load_annotations(args.annotations)
    predictions, latency = load_predictions(args.report, args.model)
    result = evaluate(annotations, predictions, args.threshold, args.iou)
    result["model"] = args.model
    result["per_image_s"] = latency
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
