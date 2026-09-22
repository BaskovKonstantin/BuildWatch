# -*- coding: utf-8 -*-
"""Smoke-compare three detectors on Moscow construction screenshots."""
from __future__ import annotations

import json
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(r"D:\Projects\BuildWatch")
SAMPLES = ROOT / "context" / "dgp_extract" / "samples"
OUT = ROOT / "context" / "dgp_extract" / "compare_out"
WEIGHTS = ROOT / "context" / "weights"
REPORT = ROOT / "context" / "detector_compare.json"

# TZ classes + extras seen on Moscow shots
LABELS = [
    "excavator",
    "dump truck",
    "truck",
    "bulldozer",
    "road roller",
    "concrete mixer",
    "mobile crane",
    "tower crane",
    "truck crane",
    "crane manipulator",
    "concrete pump",
    "drilling rig",
]

COLORS = [
    (255, 80, 80),
    (80, 200, 80),
    (80, 140, 255),
    (255, 200, 40),
    (200, 80, 255),
    (40, 220, 220),
    (255, 140, 40),
    (180, 180, 180),
]


def color_for(label: str) -> tuple[int, int, int]:
    return COLORS[abs(hash(label)) % len(COLORS)]


def draw_boxes(image: Image.Image, dets: list[dict]) -> Image.Image:
    im = image.convert("RGB").copy()
    draw = ImageDraw.Draw(im)
    try:
        font = ImageFont.truetype("arial.ttf", 16)
    except OSError:
        font = ImageFont.load_default()
    for d in dets:
        x1, y1, x2, y2 = d["box"]
        c = color_for(d["label"])
        draw.rectangle([x1, y1, x2, y2], outline=c, width=3)
        caption = f"{d['label']} {d['score']:.2f}"
        tw = draw.textlength(caption, font=font)
        draw.rectangle([x1, max(0, y1 - 18), x1 + tw + 6, y1], fill=c)
        draw.text((x1 + 3, max(0, y1 - 17)), caption, fill=(0, 0, 0), font=font)
    return im


def run_yolo_world(images: list[Path], device: str) -> dict:
    from ultralytics import YOLOWorld

    t0 = time.perf_counter()
    model = YOLOWorld("yolov8s-world.pt")
    model.set_classes(LABELS)
    load_s = time.perf_counter() - t0
    rows = []
    infer_s = 0.0
    for path in images:
        t1 = time.perf_counter()
        result = model.predict(str(path), conf=0.15, device=device, verbose=False)[0]
        infer_s += time.perf_counter() - t1
        dets = []
        if result.boxes is not None:
            for box in result.boxes:
                xyxy = box.xyxy[0].tolist()
                cls_id = int(box.cls[0])
                name = result.names.get(cls_id, str(cls_id))
                dets.append(
                    {
                        "label": name,
                        "score": float(box.conf[0]),
                        "box": [float(v) for v in xyxy],
                    }
                )
        rows.append({"image": path.name, "detections": dets})
        out_img = OUT / "yolo_world" / path.name
        out_img.parent.mkdir(parents=True, exist_ok=True)
        draw_boxes(Image.open(path), dets).save(out_img)
    return {
        "model": "yolov8s-world",
        "load_s": load_s,
        "infer_s": infer_s,
        "per_image_s": infer_s / max(len(images), 1),
        "rows": rows,
    }


def run_grounding_dino(images: list[Path], device: int) -> dict:
    from transformers import pipeline

    t0 = time.perf_counter()
    pipe = pipeline(
        "zero-shot-object-detection",
        model="IDEA-Research/grounding-dino-tiny",
        device=device,
    )
    load_s = time.perf_counter() - t0
    rows = []
    infer_s = 0.0
    for path in images:
        image = Image.open(path).convert("RGB")
        t1 = time.perf_counter()
        preds = pipe(image, candidate_labels=LABELS, threshold=0.2)
        infer_s += time.perf_counter() - t1
        dets = []
        for p in preds:
            box = p["box"]
            dets.append(
                {
                    "label": p["label"],
                    "score": float(p["score"]),
                    "box": [float(box["xmin"]), float(box["ymin"]), float(box["xmax"]), float(box["ymax"])],
                }
            )
        rows.append({"image": path.name, "detections": dets})
        out_img = OUT / "grounding_dino" / path.name
        out_img.parent.mkdir(parents=True, exist_ok=True)
        draw_boxes(image, dets).save(out_img)
    return {
        "model": "IDEA-Research/grounding-dino-tiny",
        "load_s": load_s,
        "infer_s": infer_s,
        "per_image_s": infer_s / max(len(images), 1),
        "rows": rows,
    }


def run_uisikdag(images: list[Path], device: str) -> dict:
    from huggingface_hub import hf_hub_download
    from ultralytics import YOLO

    WEIGHTS.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    pt = hf_hub_download(
        "uisikdag/yolo-v5-construction-machine-detection",
        "best.pt",
        local_dir=str(WEIGHTS / "uisikdag"),
    )
    model = YOLO(pt)
    load_s = time.perf_counter() - t0
    rows = []
    infer_s = 0.0
    names = model.names
    for path in images:
        t1 = time.perf_counter()
        result = model.predict(str(path), conf=0.15, device=device, verbose=False)[0]
        infer_s += time.perf_counter() - t1
        dets = []
        if result.boxes is not None:
            for box in result.boxes:
                xyxy = box.xyxy[0].tolist()
                cls_id = int(box.cls[0])
                name = names.get(cls_id, str(cls_id)) if isinstance(names, dict) else str(names[cls_id])
                dets.append(
                    {
                        "label": name,
                        "score": float(box.conf[0]),
                        "box": [float(v) for v in xyxy],
                    }
                )
        rows.append({"image": path.name, "detections": dets})
        out_img = OUT / "uisikdag" / path.name
        out_img.parent.mkdir(parents=True, exist_ok=True)
        draw_boxes(Image.open(path), dets).save(out_img)
    return {
        "model": "uisikdag/yolo-v5-construction-machine-detection",
        "class_names": names,
        "load_s": load_s,
        "infer_s": infer_s,
        "per_image_s": infer_s / max(len(images), 1),
        "rows": rows,
    }


def summarize(pack: dict) -> dict:
    counts: dict[str, int] = {}
    nonempty = 0
    for row in pack["rows"]:
        if row["detections"]:
            nonempty += 1
        for d in row["detections"]:
            counts[d["label"]] = counts.get(d["label"], 0) + 1
    return {
        "images": len(pack["rows"]),
        "images_with_any_box": nonempty,
        "total_boxes": sum(counts.values()),
        "by_class": dict(sorted(counts.items(), key=lambda x: -x[1])),
        "load_s": round(pack["load_s"], 2),
        "infer_s": round(pack["infer_s"], 2),
        "per_image_s": round(pack["per_image_s"], 3),
    }


def main() -> None:
    import torch

    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    dino_device = 0 if torch.cuda.is_available() else -1
    images = sorted(SAMPLES.glob("Screenshot_*.png"), key=lambda p: int("".join(ch for ch in p.stem if ch.isdigit()) or 0))
    if not images:
        raise SystemExit(f"no samples in {SAMPLES}")
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"device={device} images={len(images)}")

    results = {}
    errors = {}

    for name, fn in (
        ("yolo_world", lambda: run_yolo_world(images, device)),
        ("uisikdag", lambda: run_uisikdag(images, device)),
        ("grounding_dino", lambda: run_grounding_dino(images, dino_device)),
    ):
        print(f"=== {name} ===")
        try:
            pack = fn()
            results[name] = {"summary": summarize(pack), "detail": pack}
            print(json.dumps(results[name]["summary"], ensure_ascii=False, indent=2))
        except Exception as exc:
            errors[name] = repr(exc)
            print(f"FAIL {name}: {exc!r}")

    payload = {
        "device": device,
        "cuda": torch.cuda.is_available(),
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "labels": LABELS,
        "results": results,
        "errors": errors,
    }
    REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", REPORT)


if __name__ == "__main__":
    main()
