# -*- coding: utf-8 -*-
"""Download freely-licensed images from Wikimedia Commons categories.

Targets deficit classes of the equipment detector (road roller, bulldozer,
crane manipulator, etc.). No annotations are fetched — images are meant to be
labeled by the VLM pipeline (see vlm_label_dataset.py).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import defaultdict
from pathlib import Path

import requests

HEADERS = {"User-Agent": "BuildWatch-research/1.0 (contact: dev@buildwatch.local)"}
API = "https://commons.wikimedia.org/w/api.php"

# Commons category -> our canonical label
CATEGORIES = {
    "Road rollers": "road roller",
    "Steamrollers": "road roller",
    "Bulldozers": "bulldozer",
    "Loader cranes": "crane manipulator",
    "Crane trucks": "crane manipulator",
    "Truck cranes": "mobile crane",
    "Mobile cranes": "mobile crane",
    "Concrete mixers": "concrete mixer",
    "Dump trucks": "dump truck",
    "Excavators": "excavator",
    "Crawler excavators": "excavator",
}


def api(params: dict, attempts: int = 3) -> dict | None:
    for attempt in range(attempts):
        try:
            response = requests.get(API, params=params, headers=HEADERS, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            print(f"  api error ({exc}), retry {attempt + 1}/{attempts}", flush=True)
            time.sleep(5 * (attempt + 1))
    return None


def list_category_files(category: str, limit: int) -> list[dict]:
    files: dict[str, dict] = {}
    continue_token = {}
    while len(files) < limit:
        data = api({
            "action": "query",
            "generator": "categorymembers",
            "gcmtitle": f"Category:{category}",
            "gcmtype": "file",
            "gcmlimit": 100,
            "prop": "imageinfo",
            "iiprop": "url|size|mime|extmetadata",
            "iiurlwidth": 1280,
            "format": "json",
            **continue_token,
        })
        if not data or "query" not in data:
            break
        for page in data["query"].get("pages", {}).values():
            info = (page.get("imageinfo") or [{}])[0]
            if info.get("mime") not in {"image/jpeg", "image/png"}:
                continue
            if (info.get("width") or 0) < 640 or (info.get("height") or 0) < 480:
                continue
            files[page["title"]] = info
        if "continue" not in data:
            break
        continue_token = data["continue"]
        time.sleep(0.5)
    return list(files.values())[:limit]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "context" / "external" / "web_scrape_v1",
    )
    parser.add_argument("--per-category", type=int, default=150)
    parser.add_argument("--per-subcategory", type=int, default=50, help="max images per nested subcategory")
    args = parser.parse_args()

    manifest = defaultdict(list)
    for category, label in CATEGORIES.items():
        target = args.output / "raw" / category.replace(" ", "_")
        target.mkdir(parents=True, exist_ok=True)
        info_list = list_category_files(category, args.per_category)
        saved = 0
        for info in info_list:
            url = info.get("thumburl") or info.get("url")
            if not url:
                continue
            title = info.get("url", url).rsplit("/", 1)[-1]
            digest = hashlib.sha1(title.encode()).hexdigest()[:10]
            ext = ".png" if info.get("mime") == "image/png" else ".jpg"
            destination = target / f"{digest}{ext}"
            if destination.exists():
                saved += 1
                continue
            try:
                response = requests.get(url, headers=HEADERS, timeout=60)
                response.raise_for_status()
                destination.write_bytes(response.content)
            except requests.RequestException as exc:
                print(f"  download failed {url}: {exc}", flush=True)
                continue
            metadata = {
                "url": info.get("url"),
                "title": title,
                "width": info.get("thumbwidth") or info.get("width"),
                "height": info.get("thumbheight") or info.get("height"),
                "license": (info.get("extmetadata", {}).get("LicenseShortName", {}) or {}).get("value"),
                "label": label,
                "category": category,
            }
            Path(str(destination) + ".json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
            saved += 1
            time.sleep(0.3)
        manifest[label].append({"category": category, "saved": saved})
        print(f"{category}: saved {saved}", flush=True)

    (args.output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: sum(i["saved"] for i in v) for k, v in manifest.items()}, indent=2))


if __name__ == "__main__":
    main()
