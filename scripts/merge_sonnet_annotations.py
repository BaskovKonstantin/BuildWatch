"""Merge per-image Sonnet annotation files into a resumable dataset manifest."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def merge(input_dir: Path, output: Path) -> dict:
    images = []
    for path in sorted(input_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        annotation = data.get("annotation", {})
        objects = []
        for item in annotation.get("objects", []):
            objects.append({
                "label": item["label"],
                "box": item["box"],
                "visibility": item.get("visibility", "clear"),
                "needs_review": item.get("needs_review", True),
                "reason": item.get("reason", ""),
                "source": "sonnet",
                "review_status": "candidate",
            })
        images.append({
            "image": data["image"],
            "width": data["width"],
            "height": data["height"],
            "objects": objects,
        })
    result = {
        "format": "buildwatch-pseudo-annotations-v1",
        "ground_truth": False,
        "source": "sonnet",
        "images": images,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = merge(args.input, args.output)
    print(json.dumps({"images": len(result["images"]), "ground_truth": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
