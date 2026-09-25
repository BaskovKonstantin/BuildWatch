"""Convert three downloaded external datasets into equipment_extra_v1 (buildwatch-external-yolo-v1).

Sources (context/external/incoming/):
  - kaggle-ppe-heavy-machinery: Pascal VOC-style CSV (absolute pixel coords, 640x640 images)
  - hf-industrial-site-safety: YOLO labels (already normalized), 15 classes
  - kaggle-truck-mixer: YOLO labels (already normalized), class 8 = concrete mixer

Only canonical BuildWatch classes are kept; everything else is ignored.
All images go to train/ (no holdout). Files are copied (not symlinked) with a
source prefix in the name to avoid collisions.
"""
from __future__ import annotations

import csv
import json
import shutil
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INCOMING = ROOT / "context" / "external" / "incoming"
OUTPUT = ROOT / "context" / "external" / "equipment_extra_v1"

CLASSES = (
    "excavator", "dump truck", "road roller", "crane manipulator",
    "concrete mixer", "bulldozer", "truck", "mobile crane",
)
CLASS_IDS = {label: index for index, label in enumerate(CLASSES)}

# ---------------------------------------------------------------------------
# Source 1: kaggle-ppe-heavy-machinery (VOC CSV)
# ---------------------------------------------------------------------------
PPE_CSV = INCOMING / "kaggle-ppe-heavy-machinery" / "extracted" / "FinalDataset" / "final_dataset_normalized.csv"
PPE_IMAGES = PPE_CSV.parent
PPE_PREFIX = "ppe_"
PPE_MAPPING = {
    "road_roller": "road roller",
    "bulldozer": "bulldozer",
    "dump_truck": "dump truck",
    "excavator": "excavator",
    # wheel_loader, PPE classes, human, mask etc. -> ignored
}

# ---------------------------------------------------------------------------
# Source 2: hf-industrial-site-safety (YOLO, 15 classes, data.yaml order)
# ---------------------------------------------------------------------------
HF_ROOT = INCOMING / "hf-industrial-site-safety" / "extracted" / "6thdataset"
HF_PREFIX = "hfsafety_"
HF_NAMES = [
    "backhoe_loader", "bucket", "bucket_empty", "bucket_full", "bulldozer",
    "dump_truck", "excavator", "grader", "person_no_ppe", "person_ppe",
    "road_roller", "safety_barrel", "safety_cone", "trench", "wheel_loader",
]
HF_MAPPING = {
    "road_roller": "road roller",
    "bulldozer": "bulldozer",
    "excavator": "excavator",
    "dump_truck": "dump truck",
    # backhoe_loader / grader / wheel_loader / PPE / trench etc. -> ignored
}

# ---------------------------------------------------------------------------
# Source 3: kaggle-truck-mixer (YOLO, no data.yaml; class 8 = concrete mixer)
# ---------------------------------------------------------------------------
TM_ROOT = INCOMING / "kaggle-truck-mixer" / "extracted"
TM_PREFIX = "truckmixer_"
TM_MAPPING = {"8": "concrete mixer"}  # classes 0 and 9 are ignored


def new_stats() -> dict:
    return {"images": 0, "objects": 0, "by_class": defaultdict(int), "missing_files": 0,
            "ignored_boxes": 0, "images_without_canonical_boxes": 0}


def parse_voc_row(row: dict) -> tuple[str, tuple[float, float, float, float]] | None:
    """Return (label, cx, cy, w, h) normalized tuple or None to skip."""
    label = PPE_MAPPING.get(row["class"].strip())
    if label is None:
        return None
    try:
        width = float(row["width"])
        height = float(row["height"])
        x1, y1, x2, y2 = (float(row[k]) for k in ("xmin", "ymin", "xmax", "ymax"))
    except (KeyError, ValueError):
        return None
    if width <= 0 or height <= 0:
        return None
    # clip to image bounds
    x1, x2 = max(0.0, min(x1, width)), max(0.0, min(x2, width))
    y1, y2 = max(0.0, min(y1, height)), max(0.0, min(y2, height))
    if x2 - x1 <= 1 or y2 - y1 <= 1:
        return None
    return label, ((x1 + x2) / 2 / width, (y1 + y2) / 2 / height,
                   (x2 - x1) / width, (y2 - y1) / height)


def write_entry(dest_name: str, source_file: Path, lines: list[str], stats: dict) -> None:
    image_dir = OUTPUT / "train" / "images"
    label_dir = OUTPUT / "train" / "labels"
    image_dir.mkdir(parents=True, exist_ok=True)
    label_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_file, image_dir / dest_name)
    (label_dir / (Path(dest_name).stem + ".txt")).write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    stats["images"] += 1
    stats["objects"] += len(lines)


def convert_ppe(stats: dict) -> None:
    boxes_by_file: dict[str, list[tuple[str, tuple[float, float, float, float]]]] = defaultdict(list)
    with PPE_CSV.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            parsed = parse_voc_row(row)
            if parsed is not None:
                boxes_by_file[row["filename"].strip()].append(parsed)

    for filename, boxes in sorted(boxes_by_file.items()):
        source_file = PPE_IMAGES / filename
        if not source_file.exists():
            stats["missing_files"] += 1
            continue
        lines = []
        for label, (cx, cy, w, h) in boxes:
            lines.append(f"{CLASS_IDS[label]} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")
            stats["by_class"][label] += 1
        write_entry(PPE_PREFIX + filename, source_file, lines, stats)


def convert_yolo_dir(
    images_dir: Path, labels_dir: Path, prefix: str,
    id_to_label: dict[str, str], stats: dict,
) -> None:
    for label_file in sorted(labels_dir.glob("*.txt")):
        image_file = None
        for ext in (".jpg", ".jpeg", ".png"):
            candidate = images_dir / (label_file.stem + ext)
            if candidate.exists():
                image_file = candidate
                break
        if image_file is None:
            stats["missing_files"] += 1
            continue
        lines = []
        for raw in label_file.read_text(encoding="utf-8").splitlines():
            parts = raw.split()
            if len(parts) != 5:
                continue
            label = id_to_label.get(parts[0])
            if label is None:
                stats["ignored_boxes"] += 1
                continue
            try:
                cx, cy, w, h = (float(v) for v in parts[1:])
            except ValueError:
                continue
            # clip to [0,1]
            x1, x2 = max(0.0, cx - w / 2), min(1.0, cx + w / 2)
            y1, y2 = max(0.0, cy - h / 2), min(1.0, cy + h / 2)
            if x2 - x1 <= 1e-4 or y2 - y1 <= 1e-4:
                continue
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            w, h = x2 - x1, y2 - y1
            lines.append(f"{CLASS_IDS[label]} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")
            stats["by_class"][label] += 1
        if not lines:
            stats["images_without_canonical_boxes"] += 1
            continue
        write_entry(prefix + image_file.name, image_file, lines, stats)


def main() -> None:
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)

    ppe_stats = new_stats()
    hf_stats = new_stats()
    tm_stats = new_stats()

    convert_ppe(ppe_stats)
    for split in ("train", "val"):
        convert_yolo_dir(
            HF_ROOT / "images" / split, HF_ROOT / "labels" / split, HF_PREFIX,
            {str(i): HF_MAPPING[name] for i, name in enumerate(HF_NAMES) if name in HF_MAPPING},
            hf_stats,
        )
    for split in ("train", "valid"):
        convert_yolo_dir(
            TM_ROOT / split / "images", TM_ROOT / split / "labels", TM_PREFIX, TM_MAPPING, tm_stats,
        )

    by_class = defaultdict(int)
    for stats in (ppe_stats, hf_stats, tm_stats):
        for label, count in stats["by_class"].items():
            by_class[label] += count
    total_images = sum(s["images"] for s in (ppe_stats, hf_stats, tm_stats))
    total_objects = sum(s["objects"] for s in (ppe_stats, hf_stats, tm_stats))

    result = {
        "format": "buildwatch-external-yolo-v1",
        "source": "equipment_extra_v1",
        "license": "mixed external sources; see sources[].license",
        "ground_truth": True,
        "classes": list(CLASSES),
        "images": total_images,
        "objects": total_objects,
        "by_class": dict(sorted(by_class.items())),
        "splits": {"train": total_images},
        "sources": [
            {
                "source": "kaggle-ppe-heavy-machinery",
                "source_url": "https://www.kaggle.com/datasets/pablogarcher24/ppe-and-heavy-machinery-detection-balanced",
                "license": "CC0: Public Domain (по карточке Kaggle)",
                "annotation_format": "Pascal VOC-style CSV (absolute pixel coords, 640x640 images)",
                "source_annotations": str(PPE_CSV.relative_to(ROOT)),
                "images": ppe_stats["images"],
                "objects": ppe_stats["objects"],
                "missing_files": ppe_stats["missing_files"],
                "by_class": dict(sorted(ppe_stats["by_class"].items())),
                "mapping": PPE_MAPPING,
                "ignored_classes": ["wheel_loader", "mask", "boots", "gloves", "human",
                                    "helmet", "vest", "glasses", "ear_protection"],
                "filename_prefix": PPE_PREFIX,
            },
            {
                "source": "hf-industrial-site-safety",
                "source_url": "https://huggingface.co/datasets/Chappieut/Industrial-Site-Safety-Detection-v1-DATASET",
                "license": "MIT (заявлена автором карточки); кадры из YouTube, происхождение видео спорное",
                "annotation_format": "YOLO (normalized), 15 classes per data.yaml",
                "source_annotations": str(HF_ROOT.relative_to(ROOT)),
                "images": hf_stats["images"],
                "objects": hf_stats["objects"],
                "missing_files": hf_stats["missing_files"],
                "ignored_boxes": hf_stats["ignored_boxes"],
                "images_without_canonical_boxes": hf_stats["images_without_canonical_boxes"],
                "by_class": dict(sorted(hf_stats["by_class"].items())),
                "mapping": HF_MAPPING,
                "ignored_classes": ["backhoe_loader", "bucket", "bucket_empty", "bucket_full",
                                    "grader", "person_no_ppe", "person_ppe", "safety_barrel",
                                    "safety_cone", "trench", "wheel_loader"],
                "filename_prefix": HF_PREFIX,
            },
            {
                "source": "kaggle-truck-mixer",
                "source_url": "https://www.kaggle.com/datasets/whitetigerpx/truck-mixer",
                "license": "CC0: Public Domain (по карточке Kaggle)",
                "annotation_format": "YOLO (normalized), no data.yaml; class 8 = concrete mixer (confirmed via manifest.json)",
                "source_annotations": str(TM_ROOT.relative_to(ROOT)),
                "images": tm_stats["images"],
                "objects": tm_stats["objects"],
                "missing_files": tm_stats["missing_files"],
                "ignored_boxes": tm_stats["ignored_boxes"],
                "images_without_canonical_boxes": tm_stats["images_without_canonical_boxes"],
                "by_class": dict(sorted(tm_stats["by_class"].items())),
                "mapping": TM_MAPPING,
                "ignored_classes": ["0 (unidentified)", "9 (unidentified)"],
                "filename_prefix": TM_PREFIX,
            },
        ],
    }
    (OUTPUT / "dataset.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()