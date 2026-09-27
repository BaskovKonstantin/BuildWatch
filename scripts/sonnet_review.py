"""Review disagreement crops with Claude Sonnet Vision."""
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.rules import normalize_label
from scripts.sonnet_annotate import CANONICAL_CLASSES, extract_json

PROMPT_TEMPLATE = """You are reviewing one cropped construction-equipment object.
The original image crop includes a small context margin. Choose the best label
from this closed list: {classes}.
Sonnet's previous label: {sonnet_label}.
Other detector candidates: {candidates}.
Return ONLY JSON:
{{"decision":"accept|correct|reject|uncertain", "label":"allowed label or null", "reason":"short reason"}}
Use reject if the crop is not construction equipment. Use uncertain if the
object is too small, occluded, or the class cannot be distinguished reliably.
"""


def validate_review(data: dict) -> dict:
    if not isinstance(data, dict):
        raise ValueError("review must be an object")
    decision = data.get("decision")
    if decision not in {"accept", "correct", "reject", "uncertain"}:
        raise ValueError("invalid review decision")
    label = data.get("label")
    if label is not None:
        label = normalize_label(str(label))
        if label not in set(CANONICAL_CLASSES):
            raise ValueError(f"invalid review label: {label}")
    if decision in {"accept", "correct"} and not label:
        raise ValueError("accept/correct review requires a label")
    return {"decision": decision, "label": label, "reason": str(data.get("reason", ""))}


def _call(image_path: Path, prompt: str, api_key: str, base_url: str, model: str) -> dict:
    media_type = mimetypes.guess_type(image_path.name)[0] or "image/png"
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    body = {
        "model": model,
        "max_tokens": 512,
        "messages": [{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": encoded}},
            {"type": "text", "text": prompt},
        ]}],
    }
    request = Request(
        base_url.rstrip("/") + "/v1/messages",
        data=json.dumps(body).encode("utf-8"),
        headers={"content-type": "application/json", "x-api-key": api_key, "anthropic-version": "2023-06-01"},
        method="POST",
    )
    with urlopen(request, timeout=180) as response:
        payload = json.loads(response.read().decode("utf-8"))
    text = "".join(block.get("text", "") for block in payload.get("content", []) if block.get("type") == "text")
    return validate_review(extract_json(text))


def review_image(image: Path, objects: list[dict], output: Path, api_key: str, base_url: str, model: str, margin: float) -> None:
    from PIL import Image

    with Image.open(image) as source:
        width, height = source.size
        reviews = []
        for index, obj in enumerate(objects):
            x1, y1, x2, y2 = obj["box"]
            pad_x, pad_y = (x2 - x1) * margin, (y2 - y1) * margin
            crop_box = (
                max(0, int(x1 - pad_x)), max(0, int(y1 - pad_y)),
                min(width, int(x2 + pad_x)), min(height, int(y2 + pad_y)),
            )
            crop = source.crop(crop_box)
            crop_path = output.with_name(output.stem + f".crop_{index}.png")
            crop.save(crop_path, format="PNG")
            candidates = ", ".join(sorted({m["label"] for m in obj.get("detector_matches", [])})) or "none"
            prompt = PROMPT_TEMPLATE.format(
                classes=", ".join(CANONICAL_CLASSES),
                sonnet_label=obj["label"],
                candidates=candidates,
            )
            last_error = None
            for attempt in range(3):
                try:
                    review = _call(crop_path, prompt, api_key, base_url, model)
                    break
                except (OSError, ValueError, json.JSONDecodeError) as exc:
                    last_error = exc
                    if attempt < 2:
                        time.sleep(2 ** attempt)
            else:
                review = {"decision": "uncertain", "label": None, "reason": str(last_error)}
            reviews.append({"object_index": obj.get("_manifest_index", index), **review, "crop_box": list(crop_box), "source": "sonnet_crop"})
            crop_path.unlink(missing_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    temporary.write_text(json.dumps({"image": image.name, "reviews": reviews}, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--margin", type=float, default=0.2)
    parser.add_argument("--model", default=os.getenv("BUILDWATCH_SONNET_MODEL", "claude-sonnet-4-6"))
    parser.add_argument("--base-url", default=os.getenv("BUILDWATCH_SONNET_BASE_URL", "https://claude-n-codex.com:8443"))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    api_key = os.getenv("FREEMODEL_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("Set FREEMODEL_API_KEY or ANTHROPIC_API_KEY")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    args.output.mkdir(parents=True, exist_ok=True)
    targets = [image for image in manifest["images"] if any(obj.get("review_status") == "disagreement" for obj in image.get("objects", []))]
    if args.limit > 0:
        targets = targets[:args.limit]
    for item in targets:
        output = args.output / f"{Path(item['image']).stem}.json"
        if output.exists() and not args.force:
            print(f"skip {item['image']}")
            continue
        image = args.images / item["image"]
        disagreement = [
            {**obj, "_manifest_index": index}
            for index, obj in enumerate(item.get("objects", []))
            if obj.get("review_status") == "disagreement"
        ]
        review_image(image, disagreement, output, api_key, args.base_url, args.model, args.margin)
        print(f"ok {item['image']}")


if __name__ == "__main__":
    main()
