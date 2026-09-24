"""Prepare official MOCS COCO splits as BuildWatch YOLO datasets."""
from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path

try:
    from scripts.import_external_dataset import CLASSES, CLASS_IDS
except ModuleNotFoundError:
    from import_external_dataset import CLASSES, CLASS_IDS


def _load_mapping(path: Path) -> dict[str, str | None]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {str(key).strip().lower(): value for key, value in raw.items()}


def _copy_image(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        return
    try:
        destination.hardlink_to(source)
    except OSError:
        shutil.copy2(source, destination)


def _output_dirs(output: Path, split: str) -> tuple[Path, Path]:
    images = output / split / "images"
    labels = output / split / "labels"
    images.mkdir(parents=True, exist_ok=True)
    labels.mkdir(parents=True, exist_ok=True)
    return images, labels


def prepare_coco_split(
    coco_path: Path,
    images_root: Path,
    output: Path,
    mapping_path: Path,
    split: str,
) -> dict:
    """Convert one official COCO split and keep its official boundary."""
    if not images_root.is_dir():
        raise FileNotFoundError(f"MOCS image directory does not exist: {images_root}")

    data = json.loads(coco_path.read_text(encoding="utf-8"))
    mapping = _load_mapping(mapping_path)
    categories = {
        item["id"]: mapping.get(str(item["name"]).strip().lower())
        for item in data.get("categories", [])
    }
    annotations = defaultdict(list)
    mapped_objects = 0
    ignored_objects = 0
    by_class = Counter()
    ignored_by_class = Counter()

    for annotation in data.get("annotations", []):
        category = next(
            (item["name"] for item in data.get("categories", []) if item["id"] == annotation.get("category_id")),
            str(annotation.get("category_id")),
        )
        label = categories.get(annotation.get("category_id"))
        bbox = annotation.get("bbox")
        valid_bbox = isinstance(bbox, list) and len(bbox) == 4 and bbox[2] > 0 and bbox[3] > 0
        if label not in CLASS_IDS or not valid_bbox:
            ignored_objects += 1
            ignored_by_class[str(category)] += 1
            continue
        annotations[annotation["image_id"]].append((label, [float(value) for value in bbox]))
        mapped_objects += 1
        by_class[label] += 1

    image_dir, label_dir = _output_dirs(output, split)
    image_count = 0
    missing_images = []
    for image in data.get("images", []):
        source_file = images_root / image["file_name"]
        if not source_file.exists():
            missing_images.append(image["file_name"])
            continue
        destination_image = image_dir / Path(image["file_name"]).name
        _copy_image(source_file, destination_image)
        lines = []
        for label, bbox in annotations.get(image["id"], []):
            x, y, width, height = bbox
            x1 = max(0.0, min(x, float(image["width"])))
            y1 = max(0.0, min(y, float(image["height"])))
            x2 = max(0.0, min(x + width, float(image["width"])))
            y2 = max(0.0, min(y + height, float(image["height"])))
            clipped_width = x2 - x1
            clipped_height = y2 - y1
            if clipped_width <= 0 or clipped_height <= 0:
                continue
            lines.append(
                f"{CLASS_IDS[label]} "
                f"{(x1 + clipped_width / 2) / image['width']:.6f} "
                f"{(y1 + clipped_height / 2) / image['height']:.6f} "
                f"{clipped_width / image['width']:.6f} {clipped_height / image['height']:.6f}"
            )
        (label_dir / f"{Path(image['file_name']).stem}.txt").write_text(
            "\n".join(lines) + ("\n" if lines else ""), encoding="utf-8"
        )
        image_count += 1

    result = {
        "format": "buildwatch-mocs-yolo-v1",
        "source": "mocs",
        "split": split,
        "ground_truth": True,
        "classes": list(CLASSES),
        "images": image_count,
        "source_images": len(data.get("images", [])),
        "source_annotations": len(data.get("annotations", [])),
        "mapped_objects": mapped_objects,
        "ignored_objects": ignored_objects,
        "missing_images": len(missing_images),
        "by_class": dict(by_class),
        "ignored_by_class": dict(ignored_by_class),
        "source_annotations_path": str(coco_path),
        "source_images_path": str(images_root),
    }
    (output / f"{split}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def write_dataset_manifest(output: Path, results: list[dict]) -> dict:
    """Write the manifest consumed by the training preparation wrapper."""
    trainable = [result for result in results if result["split"] != "test"]
    manifest = {
        "format": "buildwatch-mocs-yolo-v1",
        "source": "mocs",
        "ground_truth": bool(trainable) and all(result["ground_truth"] for result in trainable),
        "test_ground_truth": False,
        "classes": list(CLASSES),
        "splits": [result["split"] for result in results],
        "images": sum(result["images"] for result in results),
        "mapped_objects": sum(result.get("mapped_objects", 0) for result in results),
    }
    (output / "dataset.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def prepare_test_split(image_info_path: Path, images_root: Path, output: Path) -> dict:
    """Copy test images with empty labels; test has no ground-truth annotations."""
    if not images_root.is_dir():
        raise FileNotFoundError(f"MOCS test image directory does not exist: {images_root}")

    data = json.loads(image_info_path.read_text(encoding="utf-8"))
    image_dir, label_dir = _output_dirs(output, "test")
    image_count = 0
    missing_images = []
    for image in data.get("images", []):
        source_file = images_root / image["file_name"]
        if not source_file.exists():
            missing_images.append(image["file_name"])
            continue
        _copy_image(source_file, image_dir / Path(image["file_name"]).name)
        (label_dir / f"{Path(image['file_name']).stem}.txt").write_text("", encoding="utf-8")
        image_count += 1

    result = {
        "format": "buildwatch-mocs-yolo-v1",
        "source": "mocs",
        "split": "test",
        "ground_truth": False,
        "classes": list(CLASSES),
        "images": image_count,
        "source_images": len(data.get("images", [])),
        "annotations": 0,
        "missing_images": len(missing_images),
        "source_image_info_path": str(image_info_path),
        "source_images_path": str(images_root),
    }
    (output / "test.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, default=Path("context/ontology/external_equipment_v1.json"))
    parser.add_argument("--train-annotations", type=Path)
    parser.add_argument("--train-images", type=Path)
    parser.add_argument("--val-annotations", type=Path)
    parser.add_argument("--val-images", type=Path)
    parser.add_argument("--test-info", type=Path)
    parser.add_argument("--test-images", type=Path)
    args = parser.parse_args()

    results = []
    if args.train_annotations or args.train_images:
        if not args.train_annotations or not args.train_images:
            parser.error("--train-annotations and --train-images must be supplied together")
        results.append(prepare_coco_split(args.train_annotations, args.train_images, args.output, args.mapping, "train"))
    if args.val_annotations or args.val_images:
        if not args.val_annotations or not args.val_images:
            parser.error("--val-annotations and --val-images must be supplied together")
        results.append(prepare_coco_split(args.val_annotations, args.val_images, args.output, args.mapping, "val"))
    if args.test_info or args.test_images:
        if not args.test_info or not args.test_images:
            parser.error("--test-info and --test-images must be supplied together")
        results.append(prepare_test_split(args.test_info, args.test_images, args.output))
    if not results:
        parser.error("at least one official MOCS split is required")
    write_dataset_manifest(args.output, results)
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
