"""Recompute warnings for an object: joined-model detections × rules."""
from __future__ import annotations

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
            "SELECT d.snapshot_id, d.model, d.label, d.score, d.x1, d.y1, d.x2, d.y2"
            " FROM detections d JOIN snapshots s ON s.id = d.snapshot_id"
            " WHERE s.object_id = ? AND d.score >= ?",
            (object_id, rules.BOX_THRESHOLD),
        ):
            dets_by_snap[row["snapshot_id"]].append(dict(row))

        created = 0
        for snap in con.execute(
            "SELECT * FROM snapshots WHERE object_id=?", (object_id,)
        ):
            for w in rules.evaluate_snapshot(
                dict(snap), dets_by_snap.get(snap["id"], []), stages, object_type
            ):
                status = keep.get((snap["id"], w["rule"]), "open")
                con.execute(
                    "INSERT INTO warnings(object_id, snapshot_id, rule, title,"
                    " body, why, source, status, severity) VALUES (?,?,?,?,?,?,?,?,?)",
                    (object_id, snap["id"], w["rule"], w["title"], w["body"],
                     w["why"], w["source"], status, w["severity"]),
                )
                created += 1
        con.commit()
        return created
    finally:
        con.close()
