# -*- coding: utf-8 -*-
"""Audit YOLO train labels with Qwen2.5-VL: classify confusion-prone boxes.

Samples images from a BuildWatch YOLO dataset, crops boxes with given labels
(e.g. truck / dump truck) and asks Qwen2.5-VL to classify the crop. Produces a
corrections report; corrections are NOT applied automatically (see
--apply-min-conf to write a corrections file for the apply step).
"""
from __future__ import annotations

import argparse
import json
import random
import re
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PROMPT = (
    "Look at this cropped photo of one vehicle from a construction site. "
    "Classify it as exactly one of: \"dump truck\" (a heavy truck with an open-box "
    "tilting cargo bed / tipper) or \"truck\" (flatbed truck, box truck, van, "
    "tractor unit, crane truck or other cargo vehicle without a tipper bed). "
    "Answer ONLY with compact JSON: {\"label\": \"dump truck\"|\"truck\", \"confidence\": <0..1>}"
)


def parse_answer(text: str) -> tuple[str, float] | None:
    match = re.search(r"\{[^{}]*\}", text, re.S)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    label = str(data.get("label", "")).strip().lower()
    if label not in {"dump truck", "truck"}:
        return None
    try:
        conf = max(0.0, min(1.0, float(data.get("confidence", 0.0))))
    except (TypeError, ValueError):
        conf = 0.0
    return label, conf


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--split", default="train")
    parser.add_argument("--labels", default="truck,dump truck", help="gt labels to audit")
    parser.add_argument("--max-images", type=int, default=300)
    parser.add_argument("--max-crops-per-image", type=int, default=3)
    parser.add_argument("--margin", type=float, default=0.15)
    parser.add_argument("--model", default="Qwen/Qwen2.5-VL-3B-Instruct")
    parser.add_argument("--output", type=Path, default=ROOT / "context" / "vlm_label_audit" / "report.json")
    args = parser.parse_args()

    import torch
    from PIL import Image
    from transformers import AutoModelForImageTextToText, AutoProcessor

    audit_labels = [label.strip() for label in args.labels.split(",") if label.strip()]
    images = sorted((args.dataset / args.split / "images").glob("*.jpg"))
    random.seed(42)
    random.shuffle(images)
    images = images[: args.max_images]

    device = "cuda" if torch.cuda.is_available() else "cpu"
    processor = AutoProcessor.from_pretrained(args.model)
    model = AutoModelForImageTextToText.from_pretrained(
        args.model, torch_dtype=torch.bfloat16 if device == "cuda" else torch.float32
    ).to(device)
    model.eval()

    report_rows = []
    counts = Counter()
    t0 = time.time()
    crops_done = 0
    for image_path in images:
        label_path = args.dataset / args.split / "labels" / f"{image_path.stem}.txt"
        if not label_path.exists():
            continue
        with Image.open(image_path) as im:
            width, height = im.size
        rows = []
        for line in label_path.read_text().splitlines():
            parts = line.split()
            if len(parts) == 5:
                rows.append((int(parts[0]), *map(float, parts[1:])))
        class_names = {i: name for i, name in enumerate(
            ["excavator", "dump truck", "road roller", "crane manipulator",
             "concrete mixer", "bulldozer", "truck", "mobile crane"])}
        selected = [
            (cls, cx, cy, bw, bh)
            for cls, cx, cy, bw, bh in rows
            if class_names.get(cls) in audit_labels
        ][: args.max_crops_per_image]
        for cls, cx, cy, bw, bh in selected:
            gt_label = class_names[cls]
            x1 = max(0.0, (cx - bw / 2) * (1 + args.margin * 2) - bw * args.margin) * width
            y1 = max(0.0, (cy - bh / 2) * (1 + args.margin * 2) - bh * args.margin) * height
            x2 = min(float(width), (cx + bw / 2) * (1 + args.margin * 2) + bw * args.margin) * width
            y2 = min(float(height), (cy + bh / 2) * (1 + args.margin * 2) + bh * args.margin) * height
            crop = Image.open(image_path).convert("RGB").crop((int(x1), int(y1), int(x2), int(y2)))
            if crop.width < 32 or crop.height < 32:
                crop = crop.resize((max(32, crop.width), max(32, crop.height)))
            conversation = [
                {"role": "user", "content": [{"type": "image"}, {"type": "text", "text": PROMPT}]}
            ]
            text_prompt = processor.apply_chat_template(conversation, add_generation_prompt=True)
            inputs = processor(text=[text_prompt], images=[crop], return_tensors="pt").to(device)
            with torch.no_grad():
                out = model.generate(**inputs, max_new_tokens=40, do_sample=False)
            answer = processor.batch_decode(out[:, inputs["input_ids"].shape[1]:], skip_special_tokens=True)[0].strip()
            parsed = parse_answer(answer)
            crops_done += 1
            if parsed is None:
                counts["unparsed"] += 1
                continue
            vlm_label, conf = parsed
            agree = vlm_label == gt_label
            counts["agree" if agree else "disagree"] += 1
            report_rows.append({
                "image": image_path.name,
                "box": [round(v, 5) for v in ((cx - bw / 2), (cy - bh / 2), bw, bh)],
                "gt_label": gt_label,
                "vlm_label": vlm_label,
                "vlm_confidence": conf,
                "agrees": agree,
                "raw_answer": answer[:120],
            })

    report = {
        "model": args.model,
        "dataset": str(args.dataset.resolve()),
        "split": args.split,
        "audited_labels": audit_labels,
        "images_sampled": len(images),
        "crops_audited": crops_done,
        "elapsed_s": round(time.time() - t0, 1),
        "counts": dict(counts),
        "agreement": round(counts.get("agree", 0) / max(1, counts.get("agree", 0) + counts.get("disagree", 0)), 3),
        "rows": report_rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
