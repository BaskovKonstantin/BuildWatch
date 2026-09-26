"""Persistent queue worker for CPU detector jobs."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import db
from backend.detection_service import finalize_detection, mark_detection_failed
from backend.detector_config import (
    DEFAULT_MODEL,
    DETECTOR_OUT,
    DETECTOR_PYTHON,
    ROOT,
    model_config,
    runtime_path,
)

OUT = DETECTOR_OUT
DETECTOR_PY = DETECTOR_PYTHON
_DEFAULT_CONFIG = model_config(DEFAULT_MODEL)
SCRIPT = _DEFAULT_CONFIG.script
WEIGHTS = _DEFAULT_CONFIG.weights
MAX_ATTEMPTS = 3
STALE_AFTER_SECONDS = 1800


def recover_interrupted_jobs() -> None:
    """Return jobs left running by a crashed worker to the retry queue."""
    cutoff = datetime.utcnow() - timedelta(seconds=STALE_AFTER_SECONDS)
    for row in db.query("SELECT id,started_at FROM detection_jobs WHERE status='running'"):
        started = row["started_at"]
        try:
            parsed = datetime.fromisoformat(str(started)) if started else None
        except ValueError:
            parsed = None
        if parsed is not None and parsed.tzinfo is not None:
            parsed = parsed.replace(tzinfo=None)
        if parsed is None or parsed < cutoff:
            db.execute(
                "UPDATE detection_jobs SET status='queued',error='worker restarted',started_at=NULL"
                " WHERE id=? AND status='running'",
                (row["id"],),
            )


def _detector_paths(model: str) -> tuple[Path, Path]:
    config = model_config(model)
    if model == DEFAULT_MODEL:
        return SCRIPT, WEIGHTS
    return config.script, config.weights


def _failure(job_id: int, snapshot_id: int, attempts: int, error: str) -> None:
    message = str(error).strip()[-2000:] or "detector failed"
    if attempts < MAX_ATTEMPTS:
        db.execute(
            "UPDATE detection_jobs SET status='queued',error=?,finished_at=CURRENT_TIMESTAMP WHERE id=?",
            (message, job_id),
        )
    else:
        mark_detection_failed(snapshot_id, message)


def _run_detector(model: str, snapshot_id: int, source: Path, suffix: str = "") -> None:
    script, weights = _detector_paths(model)
    output = OUT / f"snap_{snapshot_id}{suffix}.json"
    input_file = OUT / f"snap_{snapshot_id}{suffix}.in.json"
    output.unlink(missing_ok=True)
    input_file.write_text(json.dumps({
        "image": runtime_path(source),
        "weights": runtime_path(weights),
        "out": runtime_path(output),
        "model": model,
    }, ensure_ascii=False), encoding="utf-8")
    if not DETECTOR_PY.exists() or not script.exists() or not weights.exists():
        raise RuntimeError(f"detector runtime is not installed for {model}")
    result = subprocess.run(
        [runtime_path(DETECTOR_PY), runtime_path(script), runtime_path(input_file)],
        cwd=runtime_path(ROOT),
        timeout=1200,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stdout[-2000:])


def run_once() -> bool:
    rows = db.query("SELECT * FROM detection_jobs WHERE status='queued' ORDER BY id LIMIT 1")
    if not rows:
        return False
    job = dict(rows[0])
    snapshot_id = job["snapshot_id"]
    claimed = db.execute(
        "UPDATE detection_jobs SET status='running',attempts=attempts+1,started_at=CURRENT_TIMESTAMP"
        " WHERE id=? AND status='queued'",
        (job["id"],),
    )
    if not claimed:
        return False
    attempts = int(job["attempts"]) + 1
    try:
        snap = db.query("SELECT * FROM snapshots WHERE id=?", (snapshot_id,))
        if not snap:
            raise RuntimeError("snapshot missing")
        model = job.get("model") or DEFAULT_MODEL
        source = (
            ROOT / "context" / "dgp_extract" / "samples" / snap[0]["filename"]
            if snap[0]["src"] == "samples"
            else ROOT / "backend" / "media" / "uploads" / snap[0]["filename"]
        )
        _run_detector(model, snapshot_id, source)
        if not finalize_detection(snapshot_id, OUT):
            raise RuntimeError("detector did not produce a valid result")
    except Exception as exc:
        _failure(job["id"], snapshot_id, attempts, exc)
    return True


if __name__ == "__main__":
    db.init()
    recover_interrupted_jobs()
    while True:
        if not run_once():
            time.sleep(2)
