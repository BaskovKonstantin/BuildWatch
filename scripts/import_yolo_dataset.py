"""Import explicitly mapped external YOLO datasets into BuildWatch format."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path

try:
    from scripts.import_external_dataset import CLASSES, CLASS_IDS
except ModuleNotFoundError:
    from import_external_dataset import CLASSES, CLASS_IDS


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def _split(name: str, holdout: float) -> str:
    if holdout <= 0:
        return "train"
    value = int(hashlib.sha256(name.encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF
    return "holdout" if value < holdout else "train"


def _copy_image(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        return
    try:
        destination.hardlink_to(source)
    except OSError:
        shutil.copy2(source, destination)


def _load_mapping(path: Path) -> dict[int, str | None]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    mapping = {}
    for key, value in raw.items():
        try:
            source_id = int(key)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"YOLO source mapping key must be an integer: {key!r}") from exc
        if value is not None and value not in CLASS_IDS:
            raise ValueError(f"unsupported BuildWatch class in mapping: {value!r}")
        mapping[source_id] = value
    return mapping


def _parse_label_file(path: Path, mapping: dict[int, str | None]) -> tuple[list[tuple[str, float, float, float, float]], int]:
    result = []
    clipped_objects = 0
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        fields = line.split()
        if len(fields) != 5:
            raise ValueError(f"{path.name}:{number}: expected five YOLO fields")
        try:
            source_id = int(fields[0])
            x, y, width, height = (float(value) for value in fields[1:])
        except ValueError as exc:
            raise ValueError(f"{path.name}:{number}: invalid YOLO values") from exc
        if source_id not in mapping:
            raise ValueError(f"{path.name}:{number}: undeclared source class {source_id}")
        if not (0 <= x <= 1 and 0 <= y <= 1 and 0 < width <= 1 and 0 < height <= 1):
            raise ValueError(f"{path.name}:{number}: normalized coordinates must be within (0, 1]")
        x1 = max(0.0, x - width / 2)
        y1 = max(0.0, y - height / 2)
        x2 = min(1.0, x + width / 2)
        y2 = min(1.0, y + height / 2)
        if x2 <= x1 or y2 <= y1:
            raise ValueError(f"{path.name}:{number}: bounding box has no area within image bounds")
        if x1 != x - width / 2 or x2 != x + width / 2 or y1 != y - height / 2 or y2 != y + height / 2:
            clipped_objects += 1
        width = x2 - x1
        height = y2 - y1
        x = x1 + width / 2
        y = y1 + height / 2
        label = mapping[source_id]
        if label is not None:
            result.append((label, x, y, width, height))
    return result, clipped_objects


def import_yolo_dataset(
    source: Path,
    output: Path,
    mapping_path: Path,
    source_name: str,
    license_name: str,
    source_url: str,
    archive_sha256: str,
    holdout: float = 0.2,
) -> dict:
    """Import one directory of image/YOLO-label pairs with an explicit mapping."""
    if not source.is_dir():
        raise FileNotFoundError(f"YOLO source directory does not exist: {source}")
    if not 0 <= holdout < 1:
        raise ValueError("holdout must be >= 0 and < 1")

    mapping = _load_mapping(mapping_path)
    output.mkdir(parents=True, exist_ok=True)
    by_class = Counter()
    image_count = 0
    object_count = 0
    ignored_objects = 0
    clipped_objects = 0
    splits = Counter()

    for image_path in sorted(path for path in source.iterdir() if path.suffix.lower() in IMAGE_SUFFIXES):
        label_path = image_path.with_suffix(".txt")
        if not label_path.exists():
            raise ValueError(f"missing label for image: {image_path.name}")
        rows, clipped = _parse_label_file(label_path, mapping)
        clipped_objects += clipped
        raw_rows = label_path.read_text(encoding="utf-8").splitlines()
        ignored_objects += len(raw_rows) - len(rows)
        split = _split(image_path.name, holdout)
        image_dir = output / split / "images"
        label_dir = output / split / "labels"
        _copy_image(image_path, image_dir / image_path.name)
        lines = []
        for label, x, y, width, height in rows:
            lines.append(f"{CLASS_IDS[label]} {x:.6f} {y:.6f} {width:.6f} {height:.6f}")
            by_class[label] += 1
            object_count += 1
        label_dir.mkdir(parents=True, exist_ok=True)
        (label_dir / label_path.name).write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        image_count += 1
        splits[split] += 1

    if image_count == 0:
        raise ValueError(f"no supported image files found in source directory: {source}")

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
        "clipped_objects": clipped_objects,
        "by_class": dict(by_class),
        "splits": dict(splits),
        "source_directory": str(source),
        "source_mapping": str(mapping_path),
    }
    (output / "dataset.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--source-name", required=True)
    parser.add_argument("--license", dest="license_name", required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--archive-sha256", required=True)
    parser.add_argument("--holdout", type=float, default=0.2)
    args = parser.parse_args()
    result = import_yolo_dataset(
        args.source, args.output, args.mapping, args.source_name, args.license_name,
        args.source_url, args.archive_sha256, args.holdout,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
