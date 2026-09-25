"""Assemble VLM pseudo-labeled web images into a BuildWatch YOLO dataset.

Source layout (produced by vlm_label_dataset.py):
    <source>/<class_name_with_underscores>/images/*.jpg
    <source>/<class_name_with_underscores>/labels/*.txt
Optional per-image review files:
    <source>/<class_name_with_underscores>/labels/<stem>.review.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

# Canonical class order, same as import_external_dataset.py CLASSES.
CLASSES = (
    "excavator", "dump truck", "road roller", "crane manipulator",
    "concrete mixer", "bulldozer", "truck", "mobile crane",
)

# Underscore-separated folder names from VLM pipeline -> canonical class names.
CLASS_ALIASES = {name.replace(" ", "_"): name for name in CLASSES}

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
REVIEW_SUFFIX = ".review.json"


def _split_for_stem(stem: str, holdout_fraction: float) -> str:
    if holdout_fraction <= 0:
        return "train"
    number = int(hashlib.sha256(stem.encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF
    return "holdout" if number < holdout_fraction else "train"


def assemble_dataset(source: Path, output: Path, holdout_fraction: float) -> dict:
    if not source.is_dir():
        raise FileNotFoundError(f"source dataset directory not found: {source}")
    class_dirs = sorted(path for path in source.iterdir() if path.is_dir())
    if not class_dirs:
        raise ValueError(f"source dataset has no class directories: {source}")

    output.mkdir(parents=True, exist_ok=True)
    splits = {"train": 0, "holdout": 0}
    by_class = Counter()
    image_count = 0
    object_count = 0
    review_pending = 0
    broken = 0

    def fail(message: str) -> None:
        nonlocal broken
        broken += 1
        print(f"skipping: {message}", file=sys.stderr)

    for class_dir in class_dirs:
        folder_name = class_dir.name
        class_name = CLASS_ALIASES.get(folder_name.lower())
        if class_name is None:
            fail(f"unknown class folder {folder_name!r} in {source}")
            continue
        images_dir = class_dir / "images"
        labels_dir = class_dir / "labels"
        if not images_dir.is_dir() or not labels_dir.is_dir():
            fail(f"class folder {class_dir} is missing images/ or labels/")
            continue

        image_paths = sorted(
            path for path in images_dir.iterdir()
            if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
        )
        stems: dict[str, Path] = {}
        for image_path in image_paths:
            key = image_path.stem.lower()
            if key in stems:
                fail(f"duplicate image stem {image_path.stem!r} for class {class_name}")
                continue
            stems[key] = image_path

        for image_path in image_paths:
            key = image_path.stem.lower()
            name = image_path.stem
            label_path = labels_dir / f"{name}.txt"
            if not label_path.is_file():
                exists = any(
                    other.stem.lower() == key and not other.name.endswith(REVIEW_SUFFIX)
                    for other in labels_dir.iterdir() if other.is_file()
                )
                if exists:
                    # Case-only stem mismatch: use the matching label file.
                    label_path = next(
                        other for other in labels_dir.iterdir()
                        if other.is_file() and other.stem.lower() == key and not other.name.endswith(REVIEW_SUFFIX)
                    )
                else:
                    fail(f"missing label for image {image_path}")
                    continue
            review_path = labels_dir / f"{label_path.stem}{REVIEW_SUFFIX}"
            status = "vlm-pseudo-labels"
            if review_path.is_file():
                try:
                    data = json.loads(review_path.read_text(encoding="utf-8"))
                    status = str(data.get("review_status") or status)
                except (json.JSONDecodeError, OSError) as error:
                    fail(f"unreadable review file {review_path}: {error}")
                    continue
            review_pending += 1

            split = _split_for_stem(name, holdout_fraction)
            image_dir = output / split / "images"
            split_label_dir = output / split / "labels"
            image_dir.mkdir(parents=True, exist_ok=True)
            split_label_dir.mkdir(parents=True, exist_ok=True)
            destination_image = image_dir / f"{class_dir.name}__{image_path.name}"
            if not destination_image.exists():
                try:
                    destination_image.hardlink_to(image_path)
                except OSError:
                    shutil.copy2(image_path, destination_image)
            destination_label = split_label_dir / f"{class_dir.name}__{label_path.name}"
            shutil.copy2(label_path, destination_label)

            lines = [line for line in label_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            image_count += 1
            object_count += len(lines)
            splits[split] += 1
            by_class[class_name] += len(lines)

        # Labels without a matching image.
        label_paths = [path for path in labels_dir.iterdir() if path.is_file() and not path.name.endswith(REVIEW_SUFFIX)]
        for label_path in sorted(label_paths):
            if not any(image_path.stem.lower() == label_path.stem.lower() for image_path in image_paths):
                fail(f"missing image for label {label_path}")

    result = {
        "format": "buildwatch-external-yolo-v1",
        "source": str(source),
        "ground_truth": False,
        "review_status": "vlm-pseudo-labels; human review required",
        "classes": list(CLASSES),
        "images": image_count,
        "objects": object_count,
        "by_class": {name: by_class.get(name, 0) for name in CLASSES},
        "splits": splits,
        "reviewed_files": review_pending,
        "skipped_files": broken,
    }
    (output / "dataset.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("context/external/web_labeled_v1/dataset"))
    parser.add_argument("--output", type=Path, default=Path("context/external/web_yolo_v1"))
    parser.add_argument("--holdout-fraction", type=float, default=0.1)
    args = parser.parse_args()
    summary = assemble_dataset(args.source, args.output, args.holdout_fraction)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
