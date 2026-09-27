"""Create validated construction-equipment annotations with Claude Sonnet Vision.

The API key is read from FREEMODEL_API_KEY or ANTHROPIC_API_KEY and is never
written to output files. Results are saved per image so the command is resumable.
"""
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import re
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.rules import normalize_label

CANONICAL_CLASSES = (
    "excavator", "dump truck", "road roller", "crane manipulator",
    "concrete mixer", "bulldozer", "truck", "mobile crane",
)
CLASS_SET = set(CANONICAL_CLASSES)
PROMPT = """You are assisting with bounding-box annotation for a construction-site dataset.
Inspect the entire image and identify only visible construction equipment from this
closed list: excavator, dump truck, road roller, crane manipulator, concrete mixer,
bulldozer, truck, mobile crane. Do not label buildings, workers, cars, trees, or
other objects. If a crane subtype is uncertain, use mobile crane only when it is
clearly a mobile/vehicle-mounted crane; otherwise omit it and explain in reason.
Return ONLY valid JSON, with no Markdown and no additional keys:
{
  "objects": [
    {
      "label": "one allowed label",
      "box": [x1, y1, x2, y2],
      "visibility": "clear|partial|tiny",
      "needs_review": true,
      "reason": "short explanation"
    }
  ]
}
Coordinates must be absolute pixels in the original image. Use tight boxes.
"""


def extract_json(text: str) -> dict:
    """Parse plain or fenced JSON returned by a vision model."""
    candidate = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", candidate, re.DOTALL | re.IGNORECASE)
    if fenced:
        candidate = fenced.group(1)
    else:
        start, end = candidate.find("{"), candidate.rfind("}")
        if start >= 0 and end > start:
            candidate = candidate[start:end + 1]
    value = json.loads(candidate)
    if not isinstance(value, dict):
        raise ValueError("Sonnet response must be a JSON object")
    return value


def validate_annotation(data: dict, width: int, height: int) -> dict:
    objects = data.get("objects")
    if not isinstance(objects, list):
        raise ValueError("annotation must contain an objects list")
    cleaned = []
    for item in objects:
        if not isinstance(item, dict):
            raise ValueError("each annotation must be an object")
        label = normalize_label(str(item.get("label", "")))
        if label not in CLASS_SET:
            raise ValueError(f"unknown annotation class: {label}")
        box = item.get("box")
        if not isinstance(box, list) or len(box) != 4:
            raise ValueError("annotation box must contain four coordinates")
        try:
            values = [float(value) for value in box]
        except (TypeError, ValueError) as exc:
            raise ValueError("annotation coordinates must be numeric") from exc
        x1, y1, x2, y2 = (
            max(0.0, min(float(width), values[0])),
            max(0.0, min(float(height), values[1])),
            max(0.0, min(float(width), values[2])),
            max(0.0, min(float(height), values[3])),
        )
        if x2 <= x1 or y2 <= y1:
            raise ValueError("annotation box must have positive area")
        cleaned.append({
            "label": label,
            "box": [int(round(x1)), int(round(y1)), int(round(x2)), int(round(y2))],
            "visibility": item.get("visibility", "clear"),
            "needs_review": bool(item.get("needs_review", True)),
            "reason": str(item.get("reason", "")),
            "source": "sonnet",
        })
    return {"objects": cleaned}


def _request(image: Path, width: int, height: int, api_key: str, base_url: str, model: str) -> tuple[dict, dict]:
    media_type = mimetypes.guess_type(image.name)[0] or "image/png"
    encoded = base64.b64encode(image.read_bytes()).decode("ascii")
    body = {
        "model": model,
        "max_tokens": 2048,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": encoded}},
                {"type": "text", "text": f"Image dimensions: {width}x{height}.\n{PROMPT}"},
            ],
        }],
    }
    request = Request(
        base_url.rstrip("/") + "/v1/messages",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    with urlopen(request, timeout=180) as response:
        payload = json.loads(response.read().decode("utf-8"))
    text = "".join(
        block.get("text", "") for block in payload.get("content", [])
        if block.get("type") == "text"
    )
    return validate_annotation(extract_json(text), width, height), {
        "id": payload.get("id"),
        "model": payload.get("model", model),
        "usage": payload.get("usage", {}),
    }


def annotate(image: Path, output: Path, api_key: str, base_url: str, model: str, retries: int = 2) -> None:
    from PIL import Image

    with Image.open(image) as opened:
        width, height = opened.size
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            annotation, meta = _request(image, width, height, api_key, base_url, model)
            result = {"image": image.name, "width": width, "height": height, "annotation": annotation, "meta": meta}
            temporary = output.with_name(output.name + ".tmp")
            temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(output)
            return
        except (HTTPError, URLError, OSError, ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"failed to annotate {image.name}: {last_error}") from last_error


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images", type=Path, required=True, help="directory with PNG/JPEG/WebP images")
    parser.add_argument("--output", type=Path, required=True, help="directory for per-image JSON results")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--model", default=os.getenv("BUILDWATCH_SONNET_MODEL", "claude-sonnet-4-6"))
    parser.add_argument("--base-url", default=os.getenv("BUILDWATCH_SONNET_BASE_URL", "https://claude-n-codex.com:8443"))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    api_key = os.getenv("FREEMODEL_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("Set FREEMODEL_API_KEY or ANTHROPIC_API_KEY; the value is never written to output")
    images = sorted(path for path in args.images.iterdir() if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"})
    if args.limit > 0:
        images = images[:args.limit]
    args.output.mkdir(parents=True, exist_ok=True)
    for image in images:
        output = args.output / f"{image.stem}.json"
        if output.exists() and not args.force:
            print(f"skip {image.name}")
            continue
        try:
            annotate(image, output, api_key, args.base_url, args.model)
            print(f"ok {image.name}")
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)


if __name__ == "__main__":
    main()
