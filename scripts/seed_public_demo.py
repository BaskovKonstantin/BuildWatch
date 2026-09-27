"""Create a copyright-safe synthetic object when organizer data is unavailable."""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend import db  # noqa: E402
from backend.evaluate import evaluate_object  # noqa: E402

NAME = 'Синтетическая демонстрационная площадка'
IMAGE_NAME = 'synthetic_excavation.png'


def draw_image(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new('RGB', (1280, 720), '#e9edf7')
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 455, 1280, 720), fill='#b6a48d')
    draw.rectangle((0, 475, 1280, 505), fill='#7d6b61')
    draw.rectangle((85, 355, 250, 455), fill='#8b83d1', outline='#310f53', width=6)
    draw.rectangle((220, 390, 490, 455), fill='#ff0053', outline='#310f53', width=6)
    draw.ellipse((115, 435, 205, 525), fill='#310f53')
    draw.ellipse((380, 435, 470, 525), fill='#310f53')
    draw.line((245, 355, 450, 210, 620, 330), fill='#310f53', width=24)
    draw.polygon(((615, 325), (672, 360), (612, 392)), fill='#310f53')
    draw.text((55, 45), 'SYNTHETIC DEMO — not a camera image', fill='#310f53')
    image.save(path)


def main() -> None:
    if db.DATABASE_URL:
        raise RuntimeError('Synthetic demo seeding is supported for SQLite only')
    db.init()
    existing = db.query('SELECT id FROM objects WHERE name=?', (NAME,))
    if existing:
        print(f'Synthetic demo already exists: object {existing[0]["id"]}')
        return
    sample = ROOT / 'context/dgp_extract/samples' / IMAGE_NAME
    if not sample.exists():
        draw_image(sample)
    object_id = db.execute('INSERT INTO objects(name,type,district,description) VALUES (?,?,?,?)',
                           (NAME, 'Жильё', 'Демо', 'Синтетический пример без данных ДГП'))
    db.execute('INSERT INTO stages(object_id,position,kind,name,date_from,date_to,status) VALUES (?,?,?,?,?,?,?)',
               (object_id, 0, 'excavation', 'Устройство котлована', '2026-01-01', '2026-12-31', 'current'))
    snapshot_id = db.execute(
        'INSERT INTO snapshots(object_id,filename,src,captured_at,status,width,height) VALUES (?,?,?,?,?,?,?)',
        (object_id, IMAGE_NAME, 'samples', '2026-09-27', 'detected', 1280, 720),
    )
    db.execute('INSERT INTO detections(snapshot_id,model,label,score,x1,y1,x2,y2) VALUES (?,?,?,?,?,?,?,?)',
               (snapshot_id, 'synthetic_demo', 'excavator', 0.83, 85, 210, 672, 525))
    # The prefilled detection demonstrates rule R-03; it is not model output.
    evaluate_object(object_id)
    print(f'Created synthetic demo object {object_id}')


if __name__ == '__main__':
    main()
