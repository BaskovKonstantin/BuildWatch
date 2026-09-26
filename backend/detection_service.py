"""Shared result validation and persistence for detector workers and API."""
from __future__ import annotations

import json
import math
from pathlib import Path

try:
    from . import db, rules
    from .detector_config import canonical_model
    from .evaluate import evaluate_object
except ImportError:  # direct execution from backend/ remains supported
    import db
    import rules
    from detector_config import canonical_model
    from evaluate import evaluate_object


class DetectionResultError(ValueError):
    """Raised when a detector result does not satisfy the JSON contract."""


def _validated_detections(data: object) -> tuple[str, list[tuple]]:
    if not isinstance(data, dict):
        raise DetectionResultError("detector result must be an object")
    try:
        model = canonical_model(str(data["model"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise DetectionResultError("detector result has an unknown model") from exc
    raw_detections = data.get("detections", [])
    if not isinstance(raw_detections, list):
        raise DetectionResultError("detections must be a list")
    rows = []
    for item in raw_detections:
        if not isinstance(item, dict):
            raise DetectionResultError("each detection must be an object")
        label = item.get("label")
        score = item.get("score")
        box = item.get("box")
        if not isinstance(label, str) or not isinstance(box, list) or len(box) != 4:
            raise DetectionResultError("detection requires label, score and four box values")
        try:
            score = float(score)
            coords = tuple(float(value) for value in box)
        except (TypeError, ValueError) as exc:
            raise DetectionResultError("detection score and box must be numeric") from exc
        if not math.isfinite(score) or not 0 <= score <= 1 or not all(math.isfinite(v) for v in coords):
            raise DetectionResultError("detection contains a non-finite or invalid value")
        if coords[2] <= coords[0] or coords[3] <= coords[1]:
            raise DetectionResultError("detection box must have positive area")
        rows.append((model, rules.normalize_label(label), score, *coords))
    return model, rows


def _complete_snapshot(snap_id: int, detections: list[tuple]) -> None:
    con = db.connect()
    try:
        snapshot = con.execute("SELECT object_id FROM snapshots WHERE id=?", (snap_id,)).fetchone()
        if snapshot is None:
            raise DetectionResultError("snapshot missing")
        con.execute("DELETE FROM detections WHERE snapshot_id=?", (snap_id,))
        if detections:
            con.executemany(
                "INSERT INTO detections(snapshot_id,model,label,score,x1,y1,x2,y2)"
                " VALUES (?,?,?,?,?,?,?,?)",
                [(snap_id, *row) for row in detections],
            )
            status = "detected"
        else:
            status = "empty"
        con.execute("UPDATE snapshots SET status=? WHERE id=?", (status, snap_id))
        con.execute(
            "UPDATE detection_jobs SET status='done',error=NULL,finished_at=CURRENT_TIMESTAMP WHERE snapshot_id=?",
            (snap_id,),
        )
        con.commit()
        object_id = snapshot["object_id"]
    finally:
        con.close()
    evaluate_object(object_id)


def finalize_detection(snap_id: int, output_dir: Path) -> bool:
    """Persist one atomic detector result and complete its job."""
    output = output_dir / f"snap_{snap_id}.json"
    if not output.exists():
        return False
    try:
        data = json.loads(output.read_text(encoding="utf-8"))
        _, detections = _validated_detections(data)
        _complete_snapshot(snap_id, detections)
    except (OSError, json.JSONDecodeError, DetectionResultError):
        return False
    output.unlink(missing_ok=True)
    return True


def mark_detection_failed(snap_id: int, error: str) -> None:
    message = str(error).strip()[-2000:] or "detector failed"
    db.execute("UPDATE snapshots SET status='failed' WHERE id=?", (snap_id,))
    db.execute(
        "UPDATE detection_jobs SET status='failed',error=?,finished_at=CURRENT_TIMESTAMP WHERE snapshot_id=?",
        (message, snap_id),
    )
