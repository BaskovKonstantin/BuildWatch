"""Import a YOLO dataset that already ships with official train/validation splits."""
from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter
from pathlib import Path

try:
    from scripts.import_external_dataset import CLASSES, CLASS_IDS
except ModuleNotFoundError:
    from import_external_dataset import CLASSES, CLASS_IDS


def _load_mapping(path: Path) -> dict[int, str | None]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    mapping = {}
    for key, value in raw.items():
        try:
            source_id = int(key)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"mapping key must be an integer: {key!r}") from exc
        if value is not None and value not in CLASS_IDS:
            raise ValueError(f"unsupported BuildWatch class in mapping: {value!r}")
        mapping[source_id] = value
    return mapping


def _copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        return
    try:
        destination.hardlink_to(source)
    except OSError:
        shutil.copy2(source, destination)


def _convert_label(label_path: Path, mapping: dict[int, str | None], image_dir: Path) -> tuple[list[str], int]:
    lines = []
    objects = 0
    for number, row in enumerate(label_path.read_text(encoding="utf-8").splitlines(), start=1):
        fields = row.split()
        if not fields:
            continue
        if len(fields) != 5:
            raise ValueError(f"{label_path.name}:{number}: expected five YOLO fields")
        try:
            source_id = int(fields[0])
            x, y, width, height = (float(value) for value in fields[1:])
        except ValueError as exc:
            raise ValueError(f"{label_path.name}:{number}: invalid YOLO values") from exc
        if source_id not in mapping:
            raise ValueError(f"{label_path.name}:{number}: undeclared source class {source_id}")
        if not (0 <= x <= 1 and 0 <= y <= 1 and 0 < width <= 1 and 0 < height <= 1):
            raise ValueError(f"{label_path.name}:{number}: invalid normalized coordinates")
        label = mapping[source_id]
        if label is None:
            continue
        lines.append(f"{CLASS_IDS[label]} {x:.6f} {y:.6f} {width:.6f} {height:.6f}")
        objects += 1
    return lines, objects


def import_yolo_split_dataset(
    source_root: Path,
    output: Path,
    mapping_path: Path,
    source_name: str,
    license_name: str,
    source_url: str,
    archive_sha256: str,
    train_split: str = "train",
    holdout_split: str = "valid",
) -> dict:
    """Convert a train/valid YOLO tree into BuildWatch train/holdout with explicit ID mapping."""
    if not source_root.is_dir():
        raise FileNotFoundError(f"source root does not exist: {source_root}")
    mapping = _load_mapping(mapping_path)
    by_class = Counter()
    splits = Counter()
    image_count = 0
    object_count = 0
    ignored_objects = 0

    split_map = {"train": train_split, "holdout": holdout_split}
    for target_split, source_split in split_map.items():
        image_dir = source_root / source_split / "images"
        label_dir = source_root / source_split / "labels"
        if not image_dir.is_dir() or not label_dir.is_dir():
            raise FileNotFoundError(f"missing source directories for split {source_split}: {image_dir}, {label_dir}")
        for image_path in sorted(path for path in image_dir.iterdir() if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}):
            label_path = label_dir / (image_path.stem + ".txt")
            if not label_path.exists():
                raise ValueError(f"missing label for image: {image_path.name}")
            lines, objects = _convert_label(label_path, mapping, image_dir)
            ignored_objects += len([row for row in label_path.read_text(encoding="utf-8").splitlines() if row.strip()]) - objects
            _copy(image_path, output / target_split / "images" / image_path.name)
            label_out = output / target_split / "labels" / label_path.name
            label_out.parent.mkdir(parents=True, exist_ok=True)
            label_out.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
            for line in lines:
                by_class[CLASSES[int(line.split()[0])]] += 1
            image_count += 1
            object_count += objects
            splits[target_split] += 1

    if image_count == 0:
        raise ValueError(f"no supported image files found in source: {source_root}")

    result = {
        "format": "buildwatch-external-yolo-v1",
        "source": source_name,
        "source_url": source_url,
        "license": license_name,
        "archive_sha256": archive_sha256,
        "ground_truth": True,
        "classes": list(CLASSES),
        "images": image_count,
        "objects": object_count,
        "ignored_objects": ignored_objects,
        "by_class": dict(by_class),
        "splits": dict(splits),
        "source_directory": str(source_root),
        "source_mapping": str(mapping_path),
        "split_mapping": {train_split: "train", holdout_split: "holdout"},
    }
    (output / "dataset.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--source-name", required=True)
    parser.add_argument("--license", dest="license_name", required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--archive-sha256", required=True)
    parser.add_argument("--train-split", default="train")
    parser.add_argument("--holdout-split", default="valid")
    args = parser.parse_args()
    result = import_yolo_split_dataset(
        args.source_root, args.output, args.mapping, args.source_name, args.license_name,
        args.source_url, args.archive_sha256, args.train_split, args.holdout_split,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
