"""Export reviewed BuildWatch annotations to COCO and YOLO layouts."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

CLASSES = (
    "excavator", "dump truck", "road roller", "crane manipulator",
    "concrete mixer", "bulldozer", "truck", "mobile crane",
)
CLASS_IDS = {label: index for index, label in enumerate(CLASSES)}
ACCEPTED_STATUSES = {"accepted_pseudo_label", "vlm_verified"}


def split_for(image_name: str, holdout_fraction: float) -> str:
    if holdout_fraction <= 0:
        return "train"
    digest = int(hashlib.sha256(image_name.encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF
    return "holdout" if digest < holdout_fraction else "train"


def export_dataset(manifest_path: Path, images_dir: Path, output: Path, holdout_fraction: float = 0.2) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    output.mkdir(parents=True, exist_ok=True)
    coco_images = []
    coco_annotations = []
    split_counts = {"train": 0, "holdout": 0}
    object_count = 0
    image_id = 1
    annotation_id = 1

    for image in manifest.get("images", []):
        name = image["image"]
        source = images_dir / name
        if not source.exists():
            raise FileNotFoundError(source)
        split = split_for(name, holdout_fraction)
        destination_images = output / split / "images"
        destination_labels = output / split / "labels"
        destination_images.mkdir(parents=True, exist_ok=True)
        destination_labels.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination_images / source.name)
        split_counts[split] += 1
        coco_images.append({
            "id": image_id,
            "file_name": name,
            "width": image["width"],
            "height": image["height"],
            "split": split,
        })
        yolo_lines = []
        for obj in image.get("objects", []):
            if obj.get("review_status") not in ACCEPTED_STATUSES:
                continue
            label = obj["label"]
            if label not in CLASS_IDS:
                continue
            x1, y1, x2, y2 = [float(value) for value in obj["box"]]
            width = max(0.0, x2 - x1)
            height = max(0.0, y2 - y1)
            if width <= 0 or height <= 0:
                continue
            cx = (x1 + x2) / 2 / image["width"]
            cy = (y1 + y2) / 2 / image["height"]
            nw = width / image["width"]
            nh = height / image["height"]
            yolo_lines.append(f"{CLASS_IDS[label]} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}")
            coco_annotations.append({
                "id": annotation_id,
                "image_id": image_id,
                "category_id": CLASS_IDS[label] + 1,
                "bbox": [x1, y1, width, height],
                "area": width * height,
                "iscrowd": 0,
                "attributes": {
                    "review_status": obj.get("review_status"),
                    "source": obj.get("source", "sonnet"),
                },
            })
            annotation_id += 1
            object_count += 1
        (destination_labels / f"{Path(name).stem}.txt").write_text(
            "\n".join(yolo_lines) + ("\n" if yolo_lines else ""), encoding="utf-8"
        )
        image_id += 1

    coco = {
        "info": {
            "description": "BuildWatch reviewed pseudo-label dataset",
            "ground_truth": False,
            "source_manifest": str(manifest_path),
        },
        "licenses": [],
        "images": coco_images,
        "annotations": coco_annotations,
        "categories": [{"id": index + 1, "name": label} for index, label in enumerate(CLASSES)],
    }
    (output / "annotations.coco.json").write_text(json.dumps(coco, ensure_ascii=False, indent=2), encoding="utf-8")
    metadata = {
        "format": "buildwatch-reviewed-v1",
        "ground_truth": False,
        "classes": list(CLASSES),
        "accepted_statuses": sorted(ACCEPTED_STATUSES),
        "images": len(coco_images),
        "objects": object_count,
        "splits": split_counts,
    }
    (output / "dataset.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--images", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--holdout", type=float, default=0.2)
    args = parser.parse_args()
    if not 0 <= args.holdout < 1:
        raise SystemExit("--holdout must be in [0, 1)")
    print(json.dumps(export_dataset(args.manifest, args.images, args.output, args.holdout), ensure_ascii=False))


if __name__ == "__main__":
    main()
