# -*- coding: utf-8 -*-
"""Label downloaded images into a YOLO dataset using Grounding DINO + Qwen2.5-VL.

Pipeline per image:
  1. Grounding DINO (zero-shot) proposes boxes for the canonical class prompts.
  2. Each crop is verified by Qwen2.5-VL (single-class yes/no + confidence).
  3. Verified boxes are written as YOLO labels; images without verified boxes
     are marked "negative" (background).

This is pseudo-labeling: every label file carries a review_status sidecar.
"""
from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CLASSES = [
    "excavator", "dump truck", "road roller", "crane manipulator",
    "concrete mixer", "bulldozer", "truck", "mobile crane",
]

# Grounding DINO works best with short concrete phrases
DINO_PROMPTS = {
    "excavator": "excavator . digging machine .",
    "dump truck": "dump truck . tipper truck .",
    "road roller": "road roller . steamroller .",
    "crane manipulator": "truck mounted loader crane . knuckle boom crane .",
    "concrete mixer": "concrete mixer truck .",
    "bulldozer": "bulldozer . crawler dozer .",
    "truck": "cargo truck . box truck .",
    "mobile crane": "mobile crane . truck crane .",
}

# Qwen binary-verify prompt per class
QWEN_PROMPTS = {
    "excavator": "Does this photo show an excavator (digger with a boom, dipper and bucket)?",
    "dump truck": "Does this photo show a dump truck (a truck with an open-box tilting tipper bed)?",
    "road roller": "Does this photo show a road roller (compactor with a large front drum)?",
    "crane manipulator": "Does this photo show a truck with a small loader crane (knuckle-boom crane) mounted on its bed?",
    "concrete mixer": "Does this photo show a concrete mixer truck (truck with a rotating drum)?",
    "bulldozer": "Does this photo show a bulldozer (tracked machine with a large front blade)?",
    "truck": "Does this photo show a cargo truck (box truck, flatbed or van body, not a tipper)?",
    "mobile crane": "Does this photo show a mobile crane (truck or crawler with a long lattice/telescopic crane boom)?",
}

VERIFY_PROMPT_TAIL = (
    " Answer only with compact JSON: {\"yes\": true|false, \"confidence\": <0..1>}."
)


def parse_json_answer(text: str) -> dict | None:
    match = re.search(r"\{[^{}]*\}", text, re.S)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=ROOT / "context" / "external" / "web_scrape_v1" / "raw")
    parser.add_argument("--output", type=Path, default=ROOT / "context" / "external" / "web_labeled_v1")
    parser.add_argument("--dino-model", default="IDEA-Research/grounding-dino-tiny")
    parser.add_argument("--vlm-model", default="Qwen/Qwen2.5-VL-3B-Instruct")
    parser.add_argument("--dino-threshold", type=float, default=0.30)
    parser.add_argument("--verify-min-conf", type=float, default=0.75, help="min VLM confidence to accept a box")
    parser.add_argument("--max-per-folder", type=int, default=200)
    parser.add_argument("--skip-verified", action="store_true", help="reuse existing labels, only process new images")
    args = parser.parse_args()

    import torch
    from PIL import Image
    from transformers import AutoModelForImageTextToText, AutoProcessor, pipeline

    device = "cuda" if torch.cuda.is_available() else "cpu"
    stats = Counter()
    t0 = time.time()

    label_root = args.output / "dataset"
    label_root.mkdir(parents=True, exist_ok=True)

    dino = pipeline("zero-shot-object-detection", model=args.dino_model, device=device)
    processor = AutoProcessor.from_pretrained(args.vlm_model)
    vlm = AutoModelForImageTextToText.from_pretrained(
        args.vlm_model, torch_dtype=torch.bfloat16 if device == "cuda" else torch.float32
    ).to(device)
    vlm.eval()

    def vlm_verify(crop: Image.Image, label: str) -> tuple[bool, float]:
        prompt = QWEN_PROMPTS[label] + VERIFY_PROMPT_TAIL
        conversation = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": prompt}]}]
        text_prompt = processor.apply_chat_template(conversation, add_generation_prompt=True)
        inputs = processor(text=[text_prompt], images=[crop], return_tensors="pt").to(device)
        with torch.no_grad():
            out = vlm.generate(**inputs, max_new_tokens=30, do_sample=False)
        answer = processor.batch_decode(out[:, inputs["input_ids"].shape[1]:], skip_special_tokens=True)[0]
        data = parse_json_answer(answer)
        if not data:
            return False, 0.0
        try:
            return bool(data.get("yes")), max(0.0, min(1.0, float(data.get("confidence", 0.0))))
        except (TypeError, ValueError):
            return False, 0.0

    for folder in sorted(args.raw.iterdir()):
        if not folder.is_dir():
            continue
        meta_of = {}
        for sidecar in folder.glob("*.json"):
            try:
                meta_of[sidecar.stem] = json.loads(sidecar.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        images = [p for p in sorted(folder.iterdir()) if p.suffix.lower() in {".jpg", ".jpeg", ".png"}][: args.max_per_folder]
        if not images:
            continue
        folder_label = meta_of.get(images[0].stem, {}).get("label")
        if not folder_label:
            print(f"{folder.name}: no label metadata, skip", flush=True)
            continue
        class_id = CLASSES.index(folder_label)
        out_images = label_root / folder_label.replace(" ", "_") / "images"
        out_labels = label_root / folder_label.replace(" ", "_") / "labels"
        out_images.mkdir(parents=True, exist_ok=True)
        out_labels.mkdir(parents=True, exist_ok=True)
        print(f"== {folder.name} -> {folder_label} ({len(images)} images)", flush=True)

        for image_path in images:
            dst_image = out_images / image_path.name
            dst_label = out_labels / f"{image_path.stem}.txt"
            if dst_image.exists() and (dst_label.exists() or args.skip_verified):
                if dst_label.exists():
                    stats["skipped"] += 1
                    continue
            try:
                with Image.open(image_path) as im:
                    image = im.convert("RGB")
                    width, height = image.size
            except Exception as exc:
                print(f"  bad image {image_path.name}: {exc}", flush=True)
                stats["bad_image"] += 1
                continue

            try:
                proposals = dino(image, candidate_labels=[DINO_PROMPTS[folder_label]], threshold=args.dino_threshold)
            except Exception as exc:
                print(f"  dino failed {image_path.name}: {exc}", flush=True)
                continue

            lines = []
            for prop in proposals:
                box = prop["box"]
                score = float(prop.get("score", 0.0))
                x1, y1 = max(0, box["xmin"]), max(0, box["ymin"])
                x2, y2 = min(width, box["xmax"]), min(height, box["ymax"])
                if x2 - x1 < 24 or y2 - y1 < 24:
                    continue
                crop = image.crop((x1, y1, x2, y2))
                if crop.width < 48 or crop.height < 48:
                    scale = 48 / min(crop.width, crop.height)
                    crop = crop.resize((int(crop.width * scale), int(crop.height * scale)))
                ok, conf = vlm_verify(crop, folder_label)
                stats["dino_proposals"] += 1
                if not ok or conf < args.verify_min_conf:
                    stats["vlm_rejected"] += 1
                    continue
                stats["accepted"] += 1
                lines.append(
                    f"{class_id} {(x1 + (x2 - x1) / 2) / width:.6f} {(y1 + (y2 - y1) / 2) / height:.6f} "
                    f"{(x2 - x1) / width:.6f} {(y2 - y1) / height:.6f}"
                )

            if not lines:
                stats["no_boxes"] += 1
                if dst_image.exists():
                    dst_image.unlink()
                continue
            if not dst_image.exists():
                dst_image.write_bytes(image_path.read_bytes())
            dst_label.write_text("\n".join(lines) + "\n", encoding="utf-8")
            sidecar = {
                "source_image": str(image_path),
                "pipeline": ["grounding-dino-tiny", args.vlm_model],
                "verify_min_conf": args.verify_min_conf,
                "review_status": "vlm-pseudo-labels; human review required",
                "boxes": len(lines),
            }
            Path(str(dst_label.with_suffix("")) + ".review.json").write_text(json.dumps(sidecar, ensure_ascii=False, indent=2), encoding="utf-8")
            stats["labeled"] += 1

    summary = {"elapsed_s": round(time.time() - t0, 1), **{k: v for k, v in stats.items()}}
    (args.output / "labeling_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
