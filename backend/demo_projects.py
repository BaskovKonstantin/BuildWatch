"""Demo portfolio: several construction projects built from the ДГП dataset.

The 17 ДГП screenshots with cached detections are real Moscow construction
sites. They are grouped into projects by what the picture shows (aerial
earthworks, piling, foundation slab, road base, finished frame). Stage names
come from the ЛТЦ work catalog; the calendar dates are a demo plan because the
catalog itself has no dates. Snapshot dates are chosen inside the stage that
matches the picture, so rule warnings reflect detector output, not a broken
plan.

Run standalone to restructure an existing database without losing detections:
    .venv/bin/python backend/demo_projects.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import db

# (kind, name from ЛТЦ catalog, date_from, date_to)
Stage = tuple[str, str, str, str]

PROJECTS: list[dict] = [
    {
        "name": "ЖК «Северный», корп. 12",
        "type": "Жильё",
        "district": "САО",
        "address": "Дмитровское шоссе, вл. 107",
        "description": "Жилой дом на 24 этажа с подземным паркингом.",
        "stages": [
            ("ground", "Обустройство строительной площадки", "2026-02-01", "2026-03-15"),
            ("excavation", "Разработка грунта с креплением котлована", "2026-03-16", "2026-05-10"),
            ("frame", "Устройство надземной части", "2026-05-11", "2026-08-20"),
            ("facade", "Монтаж фасадной системы", "2026-08-21", "2026-10-31"),
            ("roof", "Устройство пирога кровли", "2026-11-01", "2026-12-15"),
        ],
        "snapshots": {
            "Screenshot_20.png": "2026-04-20",
            "Screenshot_65.png": "2026-06-18",
            "Screenshot_1.png": "2026-09-22",
        },
    },
    {
        "name": "Школа на 1 100 мест",
        "type": "Образование",
        "district": "ЮЗАО",
        "address": "ул. Профсоюзная, вл. 56",
        "description": "Общеобразовательная школа с бассейном и стадионом.",
        "stages": [
            ("ground", "Обустройство строительной площадки", "2026-05-01", "2026-06-30"),
            ("excavation", "Разработка грунта с креплением котлована", "2026-07-01", "2026-09-10"),
            ("frame", "Монолитные работы ниже отм. 0", "2026-09-11", "2026-11-30"),
            ("facade", "Монтаж фасадной системы", "2026-12-01", "2027-04-30"),
            ("roof", "Устройство пирога кровли", "2027-05-01", "2027-06-15"),
        ],
        "snapshots": {
            "Screenshot_25.png": "2026-06-15",
            "Screenshot_3.png": "2026-08-05",
            "Screenshot_2.png": "2026-09-18",
        },
    },
    {
        "name": "Поликлиника на 750 посещений",
        "type": "Здравоохранение",
        "district": "ВАО",
        "address": "ул. Первомайская, вл. 42",
        "description": "Взрослая поликлиника с диагностическим центром.",
        "stages": [
            ("ground", "Вынос инженерных сетей", "2026-03-01", "2026-04-30"),
            ("excavation", "Устройство шпунтового ограждения котлована", "2026-05-01", "2026-07-15"),
            ("frame", "Устройство фундаментной плиты", "2026-07-16", "2026-10-15"),
            ("frame", "Монолитные работы выше отм. 0", "2026-10-16", "2027-03-31"),
            ("facade", "Монтаж фасадной системы", "2027-04-01", "2027-07-31"),
        ],
        "snapshots": {
            "Screenshot_75.png": "2026-06-20",
            "Screenshot_80.png": "2026-07-28",
            "Screenshot_100.png": "2026-09-24",
        },
    },
    {
        "name": "ФОК с бассейном",
        "type": "Спорт",
        "district": "ЗелАО",
        "address": "Панфиловский проспект, вл. 9",
        "description": "Физкультурно-оздоровительный комплекс с универсальным залом.",
        "stages": [
            ("ground", "Геодезическая разбивка и ограждение площадки", "2026-04-01", "2026-05-31"),
            ("excavation", "Устройство буронабивных свай", "2026-06-01", "2026-10-20"),
            ("frame", "Устройство фундаментов", "2026-10-21", "2027-01-31"),
            ("frame", "Монтаж металлоконструкций каркаса", "2027-02-01", "2027-06-30"),
        ],
        "snapshots": {
            "Screenshot_10.png": "2026-07-10",
            "Screenshot_35.png": "2026-08-14",
            "Screenshot_40.png": "2026-09-19",
        },
    },
    {
        "name": "Реконструкция Волоколамского шоссе",
        "type": "Дороги",
        "district": "СЗАО",
        "address": "Волоколамское шоссе, участок 2,4 км",
        "description": "Расширение проезжей части и устройство местных проездов.",
        "stages": [
            ("ground", "Устройство временных подъездных дорог", "2026-04-01", "2026-05-31"),
            ("excavation", "Земляное полотно и водоотвод", "2026-06-01", "2026-08-15"),
            ("ground", "Устройство нижнего слоя основания", "2026-08-16", "2026-10-10"),
            ("facade", "Покрытие дорожной одежды", "2026-10-11", "2026-11-20"),
        ],
        "snapshots": {
            "Screenshot_50.png": "2026-07-20",
            "Screenshot_15.png": "2026-08-28",
            "Screenshot_60.png": "2026-09-23",
        },
    },
    {
        "name": "Детский сад на 350 мест",
        "type": "ДОУ",
        "district": "НАО",
        "address": "пос. Коммунарка, квартал 7",
        "description": "Отдельно стоящее здание ДОУ с прогулочными площадками.",
        "stages": [
            ("ground", "Инженерная подготовка территории", "2026-05-01", "2026-06-30"),
            ("excavation", "Устройство котлована", "2026-07-01", "2026-10-15"),
            ("frame", "Монолитный каркас", "2026-10-16", "2027-02-28"),
        ],
        "snapshots": {
            "Screenshot_85.png": "2026-08-10",
            "Screenshot_90.png": "2026-09-15",
        },
    },
]


def stage_status(date_from: str, date_to: str, today: str) -> str:
    if today > date_to:
        return "done"
    if today < date_from:
        return "future"
    return "current"


def _upsert_project(con, project: dict) -> int:
    row = con.execute("SELECT id FROM objects WHERE name=?", (project["name"],)).fetchone()
    values = (project["type"], project["district"], project["address"], project["description"])
    if row:
        object_id = row["id"]
        con.execute(
            "UPDATE objects SET type=?, district=?, address=?, description=? WHERE id=?",
            (*values, object_id),
        )
    else:
        cur = con.execute(
            "INSERT INTO objects(name, type, district, address, description) VALUES (?,?,?,?,?)",
            (project["name"], *values),
        )
        object_id = cur.lastrowid
    return object_id


def apply(con, today: str) -> list[int]:
    """Create/update demo projects and move sample snapshots into them.

    Uploaded snapshots and their detections are untouched; sample snapshots
    keep their detections and only change object/date. Returns object ids
    that need rule re-evaluation.
    """
    touched: set[int] = set()
    for project in PROJECTS:
        object_id = _upsert_project(con, project)
        touched.add(object_id)
        con.execute("DELETE FROM warnings WHERE object_id=?", (object_id,))
        con.execute("DELETE FROM stages WHERE object_id=?", (object_id,))
        for pos, (kind, name, dfrom, dto) in enumerate(project["stages"]):
            con.execute(
                "INSERT INTO stages(object_id, position, kind, name, date_from, date_to, status)"
                " VALUES (?,?,?,?,?,?,?)",
                (object_id, pos, kind, name, dfrom, dto, stage_status(dfrom, dto, today)),
            )
        for filename, captured_at in project["snapshots"].items():
            rows = con.execute(
                "SELECT id, object_id FROM snapshots WHERE src='samples' AND filename=?",
                (filename,),
            ).fetchall()
            for snap in rows:
                touched.add(snap["object_id"])
                con.execute("DELETE FROM warnings WHERE snapshot_id=?", (snap["id"],))
                con.execute(
                    "UPDATE snapshots SET object_id=?, captured_at=? WHERE id=?",
                    (object_id, captured_at, snap["id"]),
                )
    return sorted(touched)


def main() -> None:
    from datetime import date

    from evaluate import evaluate_object

    db.init()
    con = db.connect()
    try:
        touched = apply(con, date.today().isoformat())
        con.commit()
    finally:
        con.close()
    for object_id in touched:
        evaluate_object(object_id)
    print(f"demo projects applied: {len(PROJECTS)}; re-evaluated objects: {touched}")


if __name__ == "__main__":
    main()
