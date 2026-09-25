# -*- coding: utf-8 -*-
"""Create a train-only view of a BuildWatch YOLO dataset via symlinks.

Used to fold a source's holdout split into train when merging, so the merged
dataset's holdout stays identical to the previous evaluation protocol.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--splits", default="train,holdout,val", help="source splits to fold into train")
    args = parser.parse_args()

    metadata_path = args.source / "dataset.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("ground_truth") is not True:
        raise SystemExit("source dataset is not ground truth")

    out_images = args.output / "train" / "images"
    out_labels = args.output / "train" / "labels"
    out_images.mkdir(parents=True, exist_ok=True)
    out_labels.mkdir(parents=True, exist_ok=True)

    total = 0
    for split in [s.strip() for s in args.splits.split(",") if s.strip()]:
        image_dir = args.source / split / "images"
        label_dir = args.source / split / "labels"
        if not image_dir.is_dir():
            continue
        for image_path in sorted(p for p in image_dir.iterdir() if p.is_file()):
            label_path = label_dir / f"{image_path.stem}.txt"
            if not label_path.exists():
                print(f"missing label: {label_path}", file=sys.stderr)
                continue
            dst_image = out_images / f"{split}__{image_path.name}"
            dst_label = out_labels / f"{split}__{image_path.stem}.txt"
            if not dst_image.exists():
                dst_image.symlink_to(image_path.resolve())
            if not dst_label.exists():
                dst_label.symlink_to(label_path.resolve())
            total += 1

    metadata = dict(metadata)
    metadata["splits"] = {"train": total}
    metadata["derived_from"] = {"dataset": str(args.source.resolve()), "folded_splits": args.splits}
    (args.output / "dataset.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"linked {total} images into {args.output}/train")


if __name__ == "__main__":
    main()
