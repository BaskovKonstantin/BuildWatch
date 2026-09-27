"""Import licensed external COCO detection datasets into BuildWatch format."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections import defaultdict
from pathlib import Path

CLASSES = (
    "excavator", "dump truck", "road roller", "crane manipulator",
    "concrete mixer", "bulldozer", "truck", "mobile crane",
)
CLASS_IDS = {label: index for index, label in enumerate(CLASSES)}


def _split(name: str, holdout: float) -> str:
    if holdout <= 0:
        return "train"
    number = int(hashlib.sha256(name.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    return "holdout" if number < holdout else "train"


def _load_mapping(path: Path) -> dict[str, str | None]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {str(key).strip().lower(): value for key, value in raw.items()}


def import_coco(
    coco_path: Path,
    images_root: Path,
    output: Path,
    mapping_path: Path,
    source: str,
    license_name: str,
    holdout: float = 0.2,
) -> dict:
    data = json.loads(coco_path.read_text(encoding="utf-8"))
    mapping = _load_mapping(mapping_path)
    categories = {
        item["id"]: mapping.get(str(item["name"]).strip().lower())
        for item in data.get("categories", [])
    }
    annotations = defaultdict(list)
    for annotation in data.get("annotations", []):
        label = categories.get(annotation.get("category_id"))
        if label not in CLASS_IDS:
            continue
        bbox = annotation.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4 or bbox[2] <= 0 or bbox[3] <= 0:
            continue
        annotations[annotation["image_id"]].append((label, bbox))

    output.mkdir(parents=True, exist_ok=True)
    image_count = 0
    object_count = 0
    splits = {"train": 0, "holdout": 0}
    by_class = defaultdict(int)
    for image in data.get("images", []):
        source_file = images_root / image["file_name"]
        if not source_file.exists():
            continue
        split = _split(image["file_name"], holdout)
        image_dir = output / split / "images"
        label_dir = output / split / "labels"
        image_dir.mkdir(parents=True, exist_ok=True)
        label_dir.mkdir(parents=True, exist_ok=True)
        destination_image = image_dir / source_file.name
        if not destination_image.exists():
            try:
                destination_image.hardlink_to(source_file)
            except OSError:
                shutil.copy2(source_file, destination_image)
        lines = []
        for label, bbox in annotations.get(image["id"], []):
            x, y, width, height = [float(value) for value in bbox]
            cx = (x + width / 2) / image["width"]
            cy = (y + height / 2) / image["height"]
            lines.append(f"{CLASS_IDS[label]} {cx:.6f} {cy:.6f} {width / image['width']:.6f} {height / image['height']:.6f}")
            object_count += 1
            by_class[label] += 1
        (label_dir / f"{Path(image['file_name']).stem}.txt").write_text(
            "\n".join(lines) + ("\n" if lines else ""), encoding="utf-8"
        )
        image_count += 1
        splits[split] += 1

    result = {
        "format": "buildwatch-external-yolo-v1",
        "source": source,
        "license": license_name,
        "ground_truth": True,
        "classes": list(CLASSES),
        "images": image_count,
        "objects": object_count,
        "by_class": dict(by_class),
        "splits": splits,
        "source_annotations": str(coco_path),
    }
    (output / "dataset.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coco", type=Path, required=True)
    parser.add_argument("--images", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--license", required=True, dest="license_name")
    parser.add_argument("--holdout", type=float, default=0.2)
    args = parser.parse_args()
    print(json.dumps(import_coco(args.coco, args.images, args.output, args.mapping, args.source, args.license_name, args.holdout), ensure_ascii=False))


if __name__ == "__main__":
    main()
