"""Compare Sonnet pseudo-labels with cached detector predictions."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.rules import normalize_label

CRANE_LABELS = {"crane manipulator", "mobile crane", "tower crane", "truck crane"}


def iou(a, b):
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    area_a = max(0, a[2] - a[0]) * max(0, a[3] - a[1])
    area_b = max(0, b[2] - b[0]) * max(0, b[3] - b[1])
    union = area_a + area_b - inter
    return inter / union if union else 0.0


def compatible(expected, actual):
    expected = normalize_label(expected)
    actual = normalize_label(actual)
    return expected == actual or (expected in CRANE_LABELS and actual in CRANE_LABELS)


def load_detector_predictions(path: Path) -> dict[str, list[dict]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    result = {}
    for model, payload in data.get("results", {}).items():
        for row in payload.get("detail", {}).get("rows", []):
            for detection in row.get("detections", []):
                item = {
                    "label": normalize_label(detection["label"]),
                    "box": detection["box"],
                    "score": detection.get("score"),
                    "model": model,
                }
                result.setdefault(row["image"], []).append(item)
    return result


def merge(pseudo_path: Path, detector_path: Path, output: Path, iou_threshold: float = 0.5) -> dict:
    pseudo = json.loads(pseudo_path.read_text(encoding="utf-8"))
    predictions = load_detector_predictions(detector_path)
    for image in pseudo.get("images", []):
        for obj in image.get("objects", []):
            matches = []
            for prediction in predictions.get(image["image"], []):
                overlap = iou(obj["box"], prediction["box"])
                if overlap >= iou_threshold and compatible(obj["label"], prediction["label"]):
                    matches.append({"model": prediction["model"], "label": prediction["label"], "iou": round(overlap, 3)})
            obj["detector_matches"] = matches
            obj["review_status"] = "accepted_pseudo_label" if matches and not obj.get("needs_review", True) else "disagreement"
    pseudo["format"] = "buildwatch-sonnet-detector-agreement-v1"
    pseudo["ground_truth"] = False
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(pseudo, ensure_ascii=False, indent=2), encoding="utf-8")
    return pseudo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pseudo", type=Path, required=True)
    parser.add_argument("--detector-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--iou", type=float, default=0.5)
    args = parser.parse_args()
    result = merge(args.pseudo, args.detector_report, args.output, args.iou)
    total = sum(len(image.get("objects", [])) for image in result["images"])
    accepted = sum(
        obj.get("review_status") == "accepted_pseudo_label"
        for image in result["images"] for obj in image.get("objects", [])
    )
    print(json.dumps({"images": len(result["images"]), "objects": total, "accepted": accepted}, ensure_ascii=False))


if __name__ == "__main__":
    main()
