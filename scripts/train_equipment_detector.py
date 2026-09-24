"""Prepare and optionally train a compact equipment detector."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def prepare_dataset(dataset: Path, output: Path, allow_pseudo: bool) -> Path:
    metadata_path = dataset / "dataset.json"
    if not metadata_path.exists():
        raise ValueError(f"missing dataset metadata: {metadata_path}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("ground_truth") is not True and not allow_pseudo:
        raise ValueError("dataset is pseudo-label data; pass --allow-pseudo only for an exploratory run")
    classes = metadata.get("classes")
    if not isinstance(classes, list) or not classes:
        raise ValueError("dataset metadata must contain non-empty classes")
    train_images = dataset / "train" / "images"
    train_labels = dataset / "train" / "labels"
    val_split = "holdout" if (dataset / "holdout").exists() else "val"
    val_images = dataset / val_split / "images"
    val_labels = dataset / val_split / "labels"
    for path in (train_images, train_labels, val_images, val_labels):
        if not path.exists():
            raise ValueError(f"missing dataset directory: {path}")
    output.mkdir(parents=True, exist_ok=True)
    yaml_path = output / "equipment.yaml"
    yaml_path.write_text(
        "path: " + _yaml_string(dataset.resolve()) + "\n"
        "train: train/images\n"
        f"val: {val_split}/images\n"
        "names:\n"
        + "".join(f"  {index}: {_yaml_string(label)}\n" for index, label in enumerate(classes)),
        encoding="utf-8",
    )
    return yaml_path


def _yaml_string(value: object) -> str:
    text = str(value).replace("\\", "/").replace("'", "''")
    return f"'{text}'"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base-model", default="yolov8s.pt")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=-1)
    parser.add_argument("--device", default="0")
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--allow-pseudo", action="store_true")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--export-onnx", action="store_true")
    args = parser.parse_args()
    yaml_path = prepare_dataset(args.dataset, args.output, args.allow_pseudo)
    print(f"dataset_yaml={yaml_path}")
    if args.prepare_only:
        return

    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise SystemExit("Install ultralytics in the GPU environment before training") from exc

    model = YOLO(args.base_model)
    result = model.train(
        data=str(yaml_path),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        project=str(args.output.resolve() / "runs"),
        name="equipment_v1_exploratory" if args.allow_pseudo else "equipment_v1",
        exist_ok=False,
        workers=args.workers,
    )
    save_dir = Path(result.save_dir)
    best = save_dir / "weights" / "best.pt"
    print(f"best_weights={best}")
    if args.export_onnx:
        trained = YOLO(str(best))
        exported = trained.export(format="onnx", imgsz=args.imgsz, device="cpu")
        print(f"onnx={exported}")


if __name__ == "__main__":
    main()
