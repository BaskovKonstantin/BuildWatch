"""Seed the BuildWatch database from the ДГП dataset artifacts.

Sources:
- context/dgp_extract/samples/*.png            — 100 test snapshots
- context/detector_compare.json                — cached detections (yolo_world, uisikdag)
- context/dgp_extract/Сводный перечень...xlsx  — ЛТЦ work-type catalog (no dates!)

Run: .venv/bin/python seed.py [--force]
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import openpyxl
from PIL import Image

import db
import demo_projects
import rules

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "context" / "dgp_extract" / "samples"
COMPARE = ROOT / "context" / "detector_compare.json"
XLSX = ROOT / "context" / "dgp_extract" / "Сводный перечень строительных работ_ЛТЦ.xlsx"

DEMO_OBJECT = (demo_projects.PROJECTS[0]["name"], demo_projects.PROJECTS[0]["type"])


def import_catalog(con: sqlite3.Connection) -> int:
    ws = openpyxl.load_workbook(XLSX).active
    rows = list(ws.iter_rows(values_only=True))
    # Header row: ('№ п/п', 'Вид работ', 'Жильё', ...)
    type_cols = [i for i, c in enumerate(rows[2]) if isinstance(c, str) and c not in (None, "№ п/п", "Вид работ")]
    section = None
    count = 0
    for row in rows[3:]:
        code_raw, name = row[0], row[1]
        if not isinstance(name, str) or not name.strip():
            continue
        # The xlsx format bug: section codes like "10.1" become datetime.
        # Restore the code from the date (day.month pattern of the bug).
        if isinstance(code_raw, datetime):
            section = f"{code_raw.day}.{code_raw.month}."
        elif isinstance(code_raw, str) and re.match(r"^\d+\.$", code_raw.strip()):
            section = code_raw.strip()
        else:
            section = section or ""
        applies = [str(row[i]).strip() in ("˅", "v", "V", "✓") for i in type_cols]
        con.execute(
            "INSERT INTO catalog(code, name, applies) VALUES (?,?,?)",
            (section, name.strip(), ",".join(t for t, ok in zip(
                [rows[2][i] for i in type_cols], applies) if ok)),
        )
        count += 1
    return count


def assign_dates() -> dict[str, str]:
    """Snapshot dates: the 17 cached-detection shots follow the mockup story
    (15.07 → 17.06), the rest spread evenly over June — early July."""
    known = ["Screenshot_1.png", "Screenshot_2.png", "Screenshot_3.png",
             "Screenshot_10.png", "Screenshot_15.png", "Screenshot_20.png",
             "Screenshot_25.png", "Screenshot_35.png", "Screenshot_40.png",
             "Screenshot_50.png", "Screenshot_60.png", "Screenshot_65.png",
             "Screenshot_75.png", "Screenshot_80.png", "Screenshot_85.png",
             "Screenshot_90.png", "Screenshot_100.png"]
    detected_dates = {
        "Screenshot_1.png": "2026-07-15", "Screenshot_2.png": "2026-07-08",
        "Screenshot_3.png": "2026-07-01", "Screenshot_10.png": "2026-06-24",
        "Screenshot_15.png": "2026-06-17",
    }
    rest = [n for n in known if n not in detected_dates]
    base = date(2026, 6, 16)
    for i, name in enumerate(rest):
        detected_dates[name] = (base - timedelta(days=2 * i)).isoformat()
    dates = dict(detected_dates)
    undetected = [f"Screenshot_{i}.png" for i in range(1, 101)
                  if f"Screenshot_{i}.png" not in dates]
    base_u = date(2026, 7, 15)
    for i, name in enumerate(undetected):
        dates[name] = (base_u - timedelta(days=3 * (i % 15))).isoformat()
    return dates


def main() -> None:
    con = db.connect()
    con.executescript(db.SCHEMA)
    con.execute("DELETE FROM detections")
    con.execute("DELETE FROM warnings")
    con.execute("DELETE FROM snapshots")
    con.execute("DELETE FROM stages")
    con.execute("DELETE FROM objects")
    con.execute("DELETE FROM catalog")

    n_catalog = import_catalog(con)

    compare = json.loads(COMPARE.read_text())
    dates = assign_dates()

    # Snapshots land in the first demo project; demo_projects.apply() then
    # distributes them across the portfolio and writes per-project stages.
    cur = con.execute("INSERT INTO objects(name, type) VALUES (?,?)", DEMO_OBJECT)
    object_id = cur.lastrowid

    for path in sorted(SAMPLES.glob("Screenshot_*.png")):
        with Image.open(path) as im:
            w, h = im.size
        cur = con.execute(
            "INSERT INTO snapshots(object_id, filename, src, captured_at, status, width, height)"
            " VALUES (?,?,?,?,?,?,?)",
            (object_id, path.name, "samples", dates[path.name], "new", w, h),
        )
        snap_id = cur.lastrowid
        dets = []
        for model in ("yolo_world", "uisikdag"):
            rows = compare["results"].get(model, {}).get("detail", {}).get("rows", [])
            for row in rows:
                if row["image"] != path.name:
                    continue
                for det in row["detections"]:
                    label = rules.normalize_label(det["label"])
                    dets.append((model, label, det["score"], *det["box"]))
        if dets:
            con.executemany(
                "INSERT INTO detections(snapshot_id, model, label, score, x1, y1, x2, y2)"
                " VALUES (?,?,?,?,?,?,?,?)",
                [(snap_id, m, l, s, x1, y1, x2, y2) for m, l, s, x1, y1, x2, y2 in dets],
            )
            con.execute("UPDATE snapshots SET status='detected' WHERE id=?", (snap_id,))
        else:
            con.execute("UPDATE snapshots SET status='empty' WHERE id=?", (snap_id,))

    object_ids = demo_projects.apply(con, date.today().isoformat())
    con.commit()
    con.close()

    # Rules evaluation needs the API layer (evaluate_object); do it inline here.
    from evaluate import evaluate_object  # noqa: E402
    for oid in object_ids:
        evaluate_object(oid)
    print(f"catalog rows: {n_catalog}, projects: {len(object_ids)}")


def evaluate_object(object_id: int) -> None:
    from evaluate import evaluate_object as _ev
    _ev(object_id)


if __name__ == "__main__":
    db.init()
    main()
