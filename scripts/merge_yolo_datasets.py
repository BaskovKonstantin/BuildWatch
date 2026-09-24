"""Merge compatible, ground-truth BuildWatch YOLO datasets without split leakage."""
from __future__ import annotations

import argparse
import json
import re
import shutil
from collections import Counter
from pathlib import Path


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "source"


def _copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise ValueError(f"duplicate merged destination: {destination.name}")
    try:
        destination.hardlink_to(source)
    except OSError:
        shutil.copy2(source, destination)


def merge_yolo_datasets(datasets: list[Path], output: Path) -> dict:
    """Merge source train/holdout directories while preserving canonical class IDs."""
    if not datasets:
        raise ValueError("at least one source dataset is required")
    output.mkdir(parents=True, exist_ok=True)
    expected_classes: list[str] | None = None
    sources = []
    splits = Counter()
    image_count = 0
    object_count = 0

    for dataset in datasets:
        metadata_path = dataset / "dataset.json"
        if not metadata_path.exists():
            raise ValueError(f"missing source metadata: {metadata_path}")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata.get("ground_truth") is not True:
            raise ValueError(f"source dataset is not ground truth: {dataset}")
        classes = metadata.get("classes")
        if not isinstance(classes, list) or not classes:
            raise ValueError(f"source dataset has no class list: {dataset}")
        if expected_classes is None:
            expected_classes = classes
        elif classes != expected_classes:
            raise ValueError(f"source dataset class order differs: {dataset}")
        source_name = str(metadata.get("source") or dataset.name)
        prefix = _slug(source_name)
        source_images = 0
        source_objects = 0
        for split in ("train", "holdout"):
            image_dir = dataset / split / "images"
            label_dir = dataset / split / "labels"
            if not image_dir.is_dir() or not label_dir.is_dir():
                raise ValueError(f"source dataset is missing {split} images/labels: {dataset}")
            for image_path in sorted(path for path in image_dir.iterdir() if path.is_file()):
                label_path = label_dir / f"{image_path.stem}.txt"
                if not label_path.exists():
                    raise ValueError(f"missing source label: {label_path}")
                filename = f"{prefix}__{image_path.name}"
                _copy(image_path, output / split / "images" / filename)
                _copy(label_path, output / split / "labels" / f"{Path(filename).stem}.txt")
                labels = [line for line in label_path.read_text(encoding="utf-8").splitlines() if line.strip()]
                source_images += 1
                source_objects += len(labels)
                image_count += 1
                object_count += len(labels)
                splits[split] += 1
        sources.append({
            "source": source_name,
            "dataset": str(dataset),
            "metadata": metadata,
            "images": source_images,
            "objects": source_objects,
        })

    result = {
        "format": "buildwatch-merged-yolo-v1",
        "ground_truth": True,
        "classes": expected_classes,
        "images": image_count,
        "objects": object_count,
        "splits": dict(splits),
        "sources_file": "sources.json",
    }
    (output / "sources.json").write_text(json.dumps({"sources": sources}, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "dataset.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, action="append", required=True, help="Repeat for each source dataset")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(merge_yolo_datasets(args.dataset, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
