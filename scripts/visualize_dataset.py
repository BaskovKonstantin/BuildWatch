# -*- coding: utf-8 -*-
"""Draw YOLO bounding boxes on random dataset images for manual verification.

Usage:
  python scripts/visualize_dataset.py --dataset /root/buildwatch_v4 --count 9 --out dataset_preview
  python scripts/visualize_dataset.py --source-filter web --count 5
"""
from __future__ import annotations

import argparse
import random
from pathlib import Path

NAMES = {0: 'excavator', 1: 'dump truck', 2: 'road roller', 3: 'crane manipulator',
         4: 'concrete mixer', 5: 'bulldozer', 6: 'truck', 7: 'mobile crane'}
COLORS = [(255, 80, 80), (80, 200, 80), (80, 140, 255), (255, 200, 40),
          (200, 80, 255), (40, 220, 220), (255, 140, 40), (230, 230, 230)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, default=Path('/root/buildwatch_v4'))
    parser.add_argument('--split', default='train')
    parser.add_argument('--count', type=int, default=9)
    parser.add_argument('--out', type=Path, default=Path('dataset_preview'))
    parser.add_argument('--source-filter', default='', help='substring of filename, e.g. web, mocs, kaggle')
    parser.add_argument('--seed', type=int, default=None)
    args = parser.parse_args()

    random.seed(args.seed)
    images_dir = args.dataset / args.split / 'images'
    labels_dir = args.dataset / args.split / 'labels'
    files = sorted(p for p in images_dir.iterdir()
                   if p.suffix.lower() in {'.jpg', '.jpeg', '.png'}
                   and (not args.source_filter or args.source_filter.lower() in p.name.lower())
                   and (labels_dir / f'{p.stem}.txt').exists())
    skipped = len([p for p in images_dir.iterdir()
                   if p.suffix.lower() in {'.jpg', '.jpeg', '.png'}
                   and (not args.source_filter or args.source_filter.lower() in p.name.lower())]) - len(files)
    if not files:
        raise SystemExit('no labeled images matched')
    if skipped:
        print(f'note: {skipped} images without label files excluded from sampling')

    picked = random.sample(files, min(args.count, len(files)))
    args.out.mkdir(parents=True, exist_ok=True)
    generated = 0
    for path in picked:
        label_path = labels_dir / f'{path.stem}.txt'
        rows = [line.split() for line in label_path.read_text().splitlines() if line.strip()]
        if not rows:
            print(f'skipped (empty labels): {path.name}')
            continue
        from PIL import Image, ImageDraw, ImageFont
        with Image.open(path) as im:
            im = im.convert('RGB')
        width, height = im.size
        draw = ImageDraw.Draw(im)
        labels = []
        try:
            font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 18)
        except OSError:
            font = ImageFont.load_default()
        for row in rows:
            cls = int(row[0])
            cx, cy, bw, bh = map(float, row[1:5])
            box = [(cx - bw / 2) * width, (cy - bh / 2) * height,
                   (cx + bw / 2) * width, (cy + bh / 2) * height]
            color = COLORS[cls % len(COLORS)]
            draw.rectangle(box, outline=color, width=max(3, width // 400))
            label = NAMES.get(cls, str(cls))
            labels.append(label)
            text_box = draw.textbbox((box[0], box[1] - 22), f' {label} ', font=font)
            draw.rectangle([text_box[0] - 2, text_box[1] - 2, text_box[2] + 2, text_box[3] + 2], fill=color)
            draw.text((text_box[0], text_box[1]), f' {label} ', fill=(0, 0, 0), font=font)
        out_path = args.out / f'{path.stem}__annotated.jpg'
        im.save(out_path, quality=85)
        generated += 1
        print(f'{out_path}  <- {path.name}: {", ".join(labels)}')
    if generated < args.count:
        print(f'warning: requested {args.count}, generated {generated} (not enough labeled images)')


if __name__ == '__main__':
    main()
