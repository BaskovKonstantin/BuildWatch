"""Apply Sonnet crop-review decisions to a pseudo-label manifest."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def apply_reviews(manifest_path: Path, reviews_dir: Path, output: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for image in manifest.get("images", []):
        review_file = reviews_dir / f"{Path(image['image']).stem}.json"
        if not review_file.exists():
            continue
        reviews = json.loads(review_file.read_text(encoding="utf-8")).get("reviews", [])
        for review in reviews:
            index = int(review["object_index"])
            objects = image.get("objects", [])
            if index < 0 or index >= len(objects):
                continue
            obj = objects[index]
            decision = review.get("decision")
            if decision in {"accept", "correct"} and review.get("label"):
                obj["label"] = review["label"]
                obj["review_status"] = "vlm_verified"
                obj["vlm_reason"] = review.get("reason", "")
            elif decision == "reject":
                obj["review_status"] = "rejected"
                obj["vlm_reason"] = review.get("reason", "")
            else:
                obj["review_status"] = "manual_review"
                obj["vlm_reason"] = review.get("reason", "")
            obj["review_source"] = "sonnet_crop"
    manifest["ground_truth"] = False
    manifest["format"] = "buildwatch-sonnet-detector-reviewed-v1"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--reviews", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = apply_reviews(args.manifest, args.reviews, args.output)
    print(json.dumps({"images": len(result.get("images", [])), "ground_truth": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
