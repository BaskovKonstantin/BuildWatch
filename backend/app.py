"""BuildWatch API (FastAPI). Run: .venv/bin/python -m uvicorn app:app --port 8600

Live detection of uploaded/unknown snapshots runs through the Windows venv
(torch, CPU) via WSL interop; a background poller watches the result files.
"""
from __future__ import annotations

import json
import subprocess
import threading
import time
import uuid
from datetime import date
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import db
import rules
from evaluate import evaluate_object

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "context" / "dgp_extract" / "samples"
UPLOADS = Path(__file__).resolve().parent / "media" / "uploads"
UPLOADS.mkdir(parents=True, exist_ok=True)
DETECTOR_OUT = Path(__file__).resolve().parent / "media" / "detector"
DETECTOR_OUT.mkdir(parents=True, exist_ok=True)
WIN_PY = ROOT / ".venv-cpu" / "Scripts" / "python.exe"
DETECT_SCRIPT = ROOT / "scripts" / "detect_single.py"
WEIGHTS = ROOT / "yolov8s-world.pt"

app = FastAPI(title="BuildWatch API")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)
SAMPLES.mkdir(parents=True, exist_ok=True)
app.mount("/media/samples", StaticFiles(directory=str(SAMPLES)), name="samples")
app.mount("/media/uploads", StaticFiles(directory=str(UPLOADS)), name="uploads")


def snapshot_path(snap: dict) -> Path:
    return (SAMPLES if snap["src"] == "samples" else UPLOADS) / snap["filename"]


def linux_to_windows_path(path: Path) -> str:
    """WSL path → Windows path for the detector subprocess."""
    text = str(path)
    if text.startswith("/mnt/"):
        drive = text[5].upper()
        return f"{drive}:" + text[6:].replace("/", "\\")
    return text


def object_card(object_id: int) -> dict:
    rows = db.query("SELECT * FROM objects WHERE id=?", (object_id,))
    if not rows:
        raise HTTPException(404, "object not found")
    # Auto-recover snapshots stuck in 'processing' whose result file already
    # exists (covers a silently dead detector worker).
    for r in db.query(
        "SELECT id FROM snapshots WHERE object_id=? AND status='processing'",
        (object_id,),
    ):
        finalize_detection(r["id"])
    obj = dict(rows[0])
    stages = [dict(r) for r in db.query(
        "SELECT * FROM stages WHERE object_id=? ORDER BY position", (object_id,))]
    snapshots = [dict(r) for r in db.query(
        "SELECT * FROM snapshots WHERE object_id=? ORDER BY captured_at DESC, id",
        (object_id,))]
    warnings = [dict(r) for r in db.query(
        "SELECT * FROM warnings WHERE object_id=? ORDER BY id", (object_id,))]

    dets: dict[int, list[dict]] = {}
    for row in db.query(
        "SELECT d.* FROM detections d JOIN snapshots s ON s.id=d.snapshot_id"
        " WHERE s.object_id=? AND d.score>=? ORDER BY d.score DESC",
        (object_id, rules.BOX_THRESHOLD),
    ):
        dets.setdefault(row["snapshot_id"], []).append(dict(row))

    snap_list = []
    for snap in snapshots:
        det_rows = []
        for det in dets.get(snap["id"], []):
            det_rows.append({
                **det,
                "match": rules.detection_match(det, stages, snap["captured_at"]),
            })
        snap_list.append({**snap, "detections": det_rows})

    warns_out = []
    for w in warnings:
        snap = next((s for s in snapshots if s["id"] == w["snapshot_id"]), None)
        warns_out.append({
            **w,
            "snapshot_filename": snap["filename"] if snap else None,
            "captured_at": snap["captured_at"] if snap else None,
        })

    return {
        "object": obj,
        "stages": stages,
        "stage_kinds": sorted(rules.STAGE_ALLOWED.keys()),
        "snapshots": snap_list,
        "warnings": warns_out,
        "counts": {
            "snapshots": len(snap_list),
            "warnings_open": sum(1 for w in warns_out if w["status"] == "open"),
            "warnings_total": len(warns_out),
        },
        "box_threshold": rules.BOX_THRESHOLD,
        "conf_threshold": rules.CONF_THRESHOLD,
    }


def finalize_detection(snap_id: int) -> bool:
    """Read the detector result file (if present) and update the snapshot."""
    out = DETECTOR_OUT / f"snap_{snap_id}.json"
    if not out.exists():
        return False
    try:
        data = json.loads(out.read_text())
    except (OSError, ValueError):
        return False
    con = db.connect()
    try:
        con.execute("DELETE FROM detections WHERE snapshot_id=?", (snap_id,))
        rows = [
            (snap_id, "yolo_world", rules.normalize_label(det["label"]),
             det["score"], *det["box"])
            for det in data.get("detections", [])
        ]
        if rows:
            con.executemany(
                "INSERT INTO detections(snapshot_id, model, label, score,"
                " x1, y1, x2, y2) VALUES (?,?,?,?,?,?,?,?)", rows)
            con.execute("UPDATE snapshots SET status='detected' WHERE id=?", (snap_id,))
        else:
            con.execute("UPDATE snapshots SET status='empty' WHERE id=?", (snap_id,))
        con.commit()
    finally:
        con.close()
    obj = db.query("SELECT object_id FROM snapshots WHERE id=?", (snap_id,))
    evaluate_object(obj[0]["object_id"])
    out.unlink(missing_ok=True)
    return True


def _poll_detector() -> None:
    """Watch detector result files; finalize snapshot status and warnings."""
    deadline = time.time() + 1200  # covers the cold model load (~5 min CPU)
    pending = {snap["id"] for snap in db.query(
        "SELECT id FROM snapshots WHERE status='processing'")}
    while pending and time.time() < deadline:
        for snap_id in list(pending):
            if finalize_detection(snap_id):
                pending.discard(snap_id)
        time.sleep(2)


@app.get("/api/objects")
def list_objects() -> list[dict]:
    out = []
    for obj in db.query("SELECT * FROM objects ORDER BY id"):
        card = object_card(obj["id"])
        out.append({
            **obj,
            **card["counts"],
            "cover": (f"/api/snapshots/{card['snapshots'][0]['id']}/file"
                      if card["snapshots"] else None),
        })
    return out


@app.post("/api/objects")
def create_object(name: str = Form(...), type: str = Form("Жильё")) -> dict:
    new_id = db.execute("INSERT INTO objects(name, type) VALUES (?,?)", (name, type))
    return {"id": new_id}


@app.get("/api/objects/{object_id}")
def get_object(object_id: int) -> dict:
    return object_card(object_id)


@app.put("/api/objects/{object_id}/stages")
def save_stages(object_id: int, stages: list[dict]) -> dict:
    for st in stages:
        date.fromisoformat(st["date_from"])
        date.fromisoformat(st["date_to"])
    con = db.connect()
    try:
        con.execute("DELETE FROM stages WHERE object_id=?", (object_id,))
        for pos, st in enumerate(stages):
            con.execute(
                "INSERT INTO stages(object_id, position, kind, name, date_from,"
                " date_to, status) VALUES (?,?,?,?,?,?,?)",
                (object_id, pos, st["kind"], st["name"], st["date_from"],
                 st["date_to"], st["status"]),
            )
        con.commit()
    finally:
        con.close()
    created = evaluate_object(object_id)
    return {"ok": True, "warnings_recomputed": created}


@app.post("/api/warnings/{warning_id}")
def resolve_warning(warning_id: int, action: str = Form(...)) -> dict:
    if action not in ("confirm", "dismiss", "reopen"):
        raise HTTPException(400, "action must be confirm|dismiss|reopen")
    status = {"confirm": "confirmed", "dismiss": "dismissed", "reopen": "open"}[action]
    db.execute("UPDATE warnings SET status=? WHERE id=?", (status, warning_id))
    return {"ok": True}


@app.get("/api/catalog")
def get_catalog(q: str = "") -> list[dict]:
    if q:
        return [dict(r) for r in db.query(
            "SELECT * FROM catalog WHERE name LIKE ? ORDER BY id LIMIT 50",
            (f"%{q}%",))]
    return [dict(r) for r in db.query("SELECT * FROM catalog ORDER BY id")]


@app.get("/api/snapshots/{snapshot_id}")
def get_snapshot(snapshot_id: int) -> dict:
    rows = db.query("SELECT * FROM snapshots WHERE id=?", (snapshot_id,))
    if not rows:
        raise HTTPException(404)
    snap = dict(rows[0])
    dets = [dict(r) for r in db.query(
        "SELECT * FROM detections WHERE snapshot_id=? AND score>=?",
        (snapshot_id, rules.BOX_THRESHOLD))]
    return {**snap, "detections": dets}


@app.get("/api/snapshots/{snapshot_id}/file")
def snapshot_file(snapshot_id: int) -> FileResponse:
    rows = db.query("SELECT * FROM snapshots WHERE id=?", (snapshot_id,))
    if not rows:
        raise HTTPException(404)
    path = snapshot_path(dict(rows[0]))
    if not path.exists():
        raise HTTPException(404, "file missing")
    return FileResponse(path, media_type="image/png")


@app.post("/api/objects/{object_id}/upload")
async def upload(object_id: int, file: UploadFile = File(...),
                 captured_at: str = Form(date.today().isoformat())) -> dict:
    if not file.filename or not file.filename.lower().endswith(
            (".png", ".jpg", ".jpeg", ".webp")):
        raise HTTPException(400, "only image files are accepted")
    data = await file.read()
    import io

    from PIL import Image

    ext = Path(file.filename).suffix.lower()
    name = f"up_{date.today().isoformat()}_{uuid.uuid4().hex[:8]}{ext}"
    (UPLOADS / name).write_bytes(data)
    with Image.open(io.BytesIO(data)) as im:
        w, h = im.size
    snap_id = db.execute(
        "INSERT INTO snapshots(object_id, filename, src, captured_at, status,"
        " width, height) VALUES (?,?,?,?,?,?,?)",
        (object_id, name, "uploads", captured_at, "new", w, h),
    )
    evaluate_object(object_id)
    return {"id": snap_id, "status": "new"}


@app.post("/api/snapshots/{snapshot_id}/detect")
def start_detection(snapshot_id: int) -> dict:
    rows = db.query("SELECT * FROM snapshots WHERE id=?", (snapshot_id,))
    if not rows:
        raise HTTPException(404)
    snap = dict(rows[0])
    if snap["status"] == "processing":
        # Maybe a previous run already finished — pick up its result.
        if finalize_detection(snapshot_id):
            return {"ok": True, "status": "detected"}
        return {"ok": True, "status": "processing"}
    src = snapshot_path(snap)
    if not src.exists():
        raise HTTPException(404, "file missing")
    out = DETECTOR_OUT / f"snap_{snapshot_id}.json"
    out.unlink(missing_ok=True)
    db.execute("UPDATE snapshots SET status='processing' WHERE id=?", (snapshot_id,))
    input_json = DETECTOR_OUT / f"snap_{snapshot_id}.in.json"
    input_json.write_text(json.dumps({
        "image": linux_to_windows_path(src),
        "weights": linux_to_windows_path(WEIGHTS),
        "out": linux_to_windows_path(out),
    }))
    subprocess.Popen(
        [str(WIN_PY), linux_to_windows_path(DETECT_SCRIPT),
         linux_to_windows_path(input_json)],
        cwd=str(ROOT),
        stdout=open(DETECTOR_OUT / "detect.log", "ab"),
        stderr=subprocess.STDOUT,
    )
    threading.Thread(target=_poll_detector, daemon=True).start()
    return {"ok": True, "status": "processing"}


@app.post("/api/objects/{object_id}/reevaluate")
def reevaluate(object_id: int) -> dict:
    return {"ok": True, "warnings": evaluate_object(object_id)}


@app.delete("/api/snapshots/{snapshot_id}")
def delete_snapshot(snapshot_id: int) -> dict:
    db.execute("DELETE FROM detections WHERE snapshot_id=?", (snapshot_id,))
    db.execute("DELETE FROM warnings WHERE snapshot_id=?", (snapshot_id,))
    db.execute("DELETE FROM snapshots WHERE id=?", (snapshot_id,))
    return {"ok": True}
