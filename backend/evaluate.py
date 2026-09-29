"""Recompute warnings for an object: joined-model detections × rules."""
from __future__ import annotations

import json
from collections import defaultdict

try:
    from . import db, rules
except ImportError:  # direct execution from backend/ remains supported
    import db
    import rules


def evaluate_object(object_id: int) -> int:
    con = db.connect()
    try:
        object_row = con.execute("SELECT type FROM objects WHERE id=?", (object_id,)).fetchone()
        object_type = object_row["type"] if object_row else None
        stages = [dict(r) for r in con.execute(
            "SELECT * FROM stages WHERE object_id=? ORDER BY position", (object_id,))]

        # Manual decisions survive re-evaluation when the same rule still fires.
        keep = {
            (r["snapshot_id"], r["rule"]): r["status"]
            for r in con.execute(
                "SELECT snapshot_id, rule, status FROM warnings WHERE object_id=?"
                " AND status IN ('confirmed','dismissed')", (object_id,))
        }

        con.execute("DELETE FROM warnings WHERE object_id=?", (object_id,))

        dets_by_snap: dict[int, list[dict]] = defaultdict(list)
        for row in con.execute(
            "SELECT d.snapshot_id, d.model, d.label, d.score, d.x1, d.y1, d.x2, d.y2, d.verdict"
            " FROM detections d JOIN snapshots s ON s.id = d.snapshot_id"
            " WHERE s.object_id = ? AND d.score >= ?",
            (object_id, rules.BOX_THRESHOLD),
        ):
            dets_by_snap[row["snapshot_id"]].append(dict(row))

        zones = _load_zones(con, object_id)
        snaps = [
            dict(row) for row in con.execute(
                "SELECT * FROM snapshots WHERE object_id=? ORDER BY captured_at, id",
                (object_id,),
            )
        ]
        for snap in snaps:
            snap["detections"] = dets_by_snap.get(snap["id"], [])

        created = 0
        pending = []
        for snap in snaps:
            pending.extend(rules.evaluate_snapshot(
                snap, snap["detections"], stages, object_type, zones,
            ))
        pending.extend(rules.evaluate_series(snaps))
        for warning in pending:
            status = keep.get((warning["snapshot_id"], warning["rule"]), "open")
            con.execute(
                "INSERT INTO warnings(object_id, snapshot_id, rule, title,"
                " body, why, source, status, severity) VALUES (?,?,?,?,?,?,?,?,?)",
                (object_id, warning["snapshot_id"], warning["rule"], warning["title"],
                 warning["body"], warning["why"], warning["source"], status, warning["severity"]),
            )
            created += 1
        con.commit()
        return created
    finally:
        con.close()


def _load_zones(con, object_id: int) -> list[dict]:
    zones = []
    for row in con.execute(
        "SELECT id, name, kind, polygon_json FROM site_zones WHERE object_id=? ORDER BY id",
        (object_id,),
    ):
        try:
            polygon = json.loads(row["polygon_json"])
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(polygon, list) and len(polygon) >= 3:
            zones.append({
                "id": row["id"], "name": row["name"], "kind": row["kind"], "polygon": polygon,
            })
    return zones
