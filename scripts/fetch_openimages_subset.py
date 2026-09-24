"""Build an attributed, explicitly mapped equipment subset from Open Images CSVs."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import shutil
import time
from collections import Counter, defaultdict
from contextlib import contextmanager
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

try:
    from scripts.import_external_dataset import CLASSES, CLASS_IDS
except ModuleNotFoundError:
    from import_external_dataset import CLASSES, CLASS_IDS


OFFICIAL_ANNOTATIONS_URL = "https://storage.googleapis.com/openimages/v6/oidv6-train-annotations-bbox.csv"
OFFICIAL_IMAGE_INFO_URL = "https://storage.googleapis.com/openimages/v6/oidv6-train-images-with-labels-with-rotation.csv"


@contextmanager
def _open_csv(source: Path | str):
    if isinstance(source, Path) or not str(source).startswith(("https://", "http://", "file://")):
        with Path(source).open("r", newline="", encoding="utf-8") as file:
            yield file
        return
    request = Request(str(source), headers={"User-Agent": "BuildWatch dataset preparation/1.0"})
    with urlopen(request, timeout=120) as response:
        with io.TextIOWrapper(response, encoding="utf-8", newline="") as file:
            yield file


def _load_mapping(path: Path) -> dict[str, str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    mapping = {str(key): value for key, value in raw.items()}
    if not mapping:
        raise ValueError("Open Images mapping must not be empty")
    invalid = {key: value for key, value in mapping.items() if value not in CLASS_IDS}
    if invalid:
        raise ValueError(f"unsupported BuildWatch classes in mapping: {invalid}")
    return mapping


def _stable_key(label: str, image_id: str) -> str:
    return hashlib.sha256(f"{label}:{image_id}".encode("utf-8")).hexdigest()


def _split(image_id: str, holdout: float) -> str:
    value = int(hashlib.sha256(image_id.encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF
    return "holdout" if value < holdout else "train"


def _download(url: str, destination: Path, retries: int = 3) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        return
    for attempt in range(retries):
        temporary = destination.with_suffix(destination.suffix + ".part")
        try:
            request = Request(url, headers={"User-Agent": "BuildWatch dataset preparation/1.0"})
            with urlopen(request, timeout=120) as response, temporary.open("wb") as output:
                shutil.copyfileobj(response, output)
            temporary.replace(destination)
            return
        except HTTPError as exc:
            temporary.unlink(missing_ok=True)
            if exc.code < 500 and exc.code != 429:
                raise
            if attempt + 1 == retries:
                raise
            time.sleep(2 ** attempt)
        except Exception:
            temporary.unlink(missing_ok=True)
            if attempt + 1 == retries:
                raise
            time.sleep(2 ** attempt)


def _image_suffix(url: str) -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    return suffix if suffix in {".jpg", ".jpeg", ".png", ".webp"} else ".jpg"


def _target_boxes(annotation_source: Path | str, mapping: dict[str, str]) -> tuple[dict[str, list[tuple[str, float, float, float, float]]], dict[str, set[str]]]:
    boxes_by_image = defaultdict(list)
    candidates_by_class = defaultdict(set)
    with _open_csv(annotation_source) as file:
        for row in csv.DictReader(file):
            label = mapping.get(row.get("LabelName", ""))
            if label is None or row.get("Confidence") != "1":
                continue
            try:
                xmin, xmax = float(row["XMin"]), float(row["XMax"])
                ymin, ymax = float(row["YMin"]), float(row["YMax"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"invalid Open Images box for {row.get('ImageID', '<unknown>')}") from exc
            xmin, xmax = max(0.0, xmin), min(1.0, xmax)
            ymin, ymax = max(0.0, ymin), min(1.0, ymax)
            if xmax <= xmin or ymax <= ymin:
                continue
            image_id = row["ImageID"]
            boxes_by_image[image_id].append((label, xmin, xmax, ymin, ymax))
            candidates_by_class[label].add(image_id)
    return boxes_by_image, candidates_by_class


def build_openimages_subset(
    annotations_source: Path | str,
    image_info_source: Path | str,
    output: Path,
    mapping_path: Path,
    max_images_per_class: int,
    holdout: float = 0.2,
) -> dict:
    """Select safely mapped Open Images boxes and download zero-rotation thumbnails."""
    if max_images_per_class < 1:
        raise ValueError("max_images_per_class must be at least one")
    if not 0 <= holdout < 1:
        raise ValueError("holdout must be >= 0 and < 1")
    mapping = _load_mapping(mapping_path)
    boxes_by_image, candidates_by_class = _target_boxes(annotations_source, mapping)
    selected_ids = set()
    selected_by_class = {}
    for label, image_ids in candidates_by_class.items():
        chosen = sorted(image_ids, key=lambda image_id: _stable_key(label, image_id))[:max_images_per_class]
        selected_ids.update(chosen)
        selected_by_class[label] = len(chosen)
    if not selected_ids:
        raise ValueError("no annotated images found for mapped Open Images classes")

    output.mkdir(parents=True, exist_ok=True)
    by_class = Counter()
    splits = Counter()
    attributions = []
    downloaded_ids = []
    skipped_rotated = 0
    failed_downloads = []
    found_ids = set()
    with _open_csv(image_info_source) as file:
        for row in csv.DictReader(file):
            image_id = row.get("ImageID", "")
            if image_id not in selected_ids:
                continue
            found_ids.add(image_id)
            try:
                rotation = float(row.get("Rotation") or 0)
            except ValueError:
                rotation = 1.0
            if rotation != 0:
                skipped_rotated += 1
                continue
            image_url = row.get("Thumbnail300KURL") or row.get("OriginalURL")
            if not image_url:
                continue
            split = _split(image_id, holdout)
            suffix = _image_suffix(image_url)
            image_path = output / split / "images" / f"{image_id}{suffix}"
            try:
                _download(image_url, image_path)
            except Exception:
                fallback_url = row.get("OriginalURL")
                if fallback_url and fallback_url != image_url:
                    image_url = fallback_url
                    image_path = output / split / "images" / f"{image_id}{_image_suffix(image_url)}"
                    try:
                        _download(image_url, image_path)
                    except Exception:
                        failed_downloads.append(image_id)
                        continue
                else:
                    failed_downloads.append(image_id)
                    continue
            labels = []
            for label, xmin, xmax, ymin, ymax in boxes_by_image[image_id]:
                width, height = xmax - xmin, ymax - ymin
                labels.append(f"{CLASS_IDS[label]} {(xmin + width / 2):.6f} {(ymin + height / 2):.6f} {width:.6f} {height:.6f}")
                by_class[label] += 1
            label_path = output / split / "labels" / f"{image_id}.txt"
            label_path.parent.mkdir(parents=True, exist_ok=True)
            label_path.write_text("\n".join(labels) + "\n", encoding="utf-8")
            splits[split] += 1
            downloaded_ids.append(image_id)
            attributions.append({
                "image_id": image_id,
                "source_url": row.get("OriginalURL"),
                "download_url": image_url,
                "landing_url": row.get("OriginalLandingURL"),
                "license": row.get("License"),
                "author_profile_url": row.get("AuthorProfileURL"),
                "author": row.get("Author"),
                "title": row.get("Title"),
            })
    missing_metadata = sorted(selected_ids - found_ids)
    if not downloaded_ids:
        raise ValueError("selected Open Images IDs have no downloadable zero-rotation image metadata")

    result = {
        "format": "buildwatch-openimages-yolo-v1",
        "source": "Open Images V6",
        "ground_truth": True,
        "classes": list(CLASSES),
        "images": len(downloaded_ids),
        "objects": sum(by_class.values()),
        "by_class": dict(by_class),
        "splits": dict(splits),
        "selected_ids": sorted(downloaded_ids),
        "selected_candidates_by_class": selected_by_class,
        "skipped_rotated_images": skipped_rotated,
        "failed_downloads": sorted(failed_downloads),
        "missing_image_metadata": missing_metadata,
        "annotations_source": str(annotations_source),
        "image_info_source": str(image_info_source),
        "mapping": str(mapping_path),
        "attribution_file": "attribution.json",
    }
    (output / "attribution.json").write_text(json.dumps({"images": attributions}, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "dataset.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--max-images-per-class", type=int, default=500)
    parser.add_argument("--holdout", type=float, default=0.2)
    parser.add_argument("--annotations", default=OFFICIAL_ANNOTATIONS_URL)
    parser.add_argument("--image-info", default=OFFICIAL_IMAGE_INFO_URL)
    args = parser.parse_args()
    result = build_openimages_subset(
        args.annotations, args.image_info, args.output, args.mapping,
        args.max_images_per_class, args.holdout,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
