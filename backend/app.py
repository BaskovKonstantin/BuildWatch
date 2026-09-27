"""BuildWatch API (FastAPI). Run: .venv/bin/python -m uvicorn app:app --port 8600

Live detection is queued in SQLite and executed by scripts/worker.py. The worker
can use the Windows CPU environment from WSL and writes a validated result file.
"""
from __future__ import annotations

import io
import uuid
from datetime import date
from pathlib import Path
import mimetypes

from fastapi import Body, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import db
import rules
from evaluate import evaluate_object
import security
import audit
import assistant_service
import plan_import
from detector_config import (
    DEFAULT_MODEL,
    DETECTOR_OUT,
    DETECTOR_PYTHON,
    MODELS,
    ROOT,
    canonical_model,
    detector_available,
)
from detection_service import finalize_detection as persist_detection

SAMPLES = ROOT / "context" / "dgp_extract" / "samples"
UPLOADS = ROOT / "backend" / "media" / "uploads"
UPLOADS.mkdir(parents=True, exist_ok=True)
DETECTOR_OUT.mkdir(parents=True, exist_ok=True)
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
IMAGE_EXTENSIONS = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}

app = FastAPI(title="BuildWatch API")


@app.get("/api/assistant/status")
def assistant_status() -> dict:
    return {"available": assistant_service.zen_key() is not None}


@app.post("/api/assistant/query")
def assistant_query(payload: dict = Body(...)) -> dict:
    object_id = payload.get("object_id")
    if object_id is not None and (type(object_id) is not int or object_id < 1):
        raise HTTPException(422, "Некорректный объект")
    return assistant_service.query(str(payload.get("message", "")), object_id)


@app.post("/api/assistant/proposals/{proposal_id}/confirm")
def assistant_confirm(proposal_id: str, request: Request) -> dict:
    user = security.require_role(request, "admin", "editor")
    return assistant_service.confirm(proposal_id, user["sub"] if user else None)


@app.middleware("http")
async def auth_guard(request, call_next):
    if security.AUTH_REQUIRED and request.url.path.startswith("/api/") and request.url.path not in {"/api/health", "/api/auth/login"}:
        try:
            security.current_user(request)
        except HTTPException as exc:
            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
    return await call_next(request)


@app.on_event("startup")
def initialize_database() -> None:
    """Make a fresh checkout runnable before seed.py is executed."""
    db.init()
@app.post("/api/auth/login")
def auth_login(email: str = Form(...), password: str = Form(...)) -> dict:
    return {"access_token": security.login(email, password), "token_type": "bearer"}


@app.get("/api/metrics")
def metrics() -> str:
    snapshots = db.query("SELECT COUNT(*) AS n FROM snapshots")[0]["n"]
    warnings = db.query("SELECT COUNT(*) AS n FROM warnings WHERE status='open'")[0]["n"]
    jobs = db.query("SELECT COUNT(*) AS n FROM detection_jobs WHERE status IN ('queued','running')")[0]["n"]
    return f"buildwatch_snapshots_total {snapshots}\nbuildwatch_open_warnings {warnings}\nbuildwatch_detection_jobs_active {jobs}\n"


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "service": "buildwatch-api",
        "detector_available": any(detector_available(name) for name in MODELS),
        "detectors": {name: detector_available(name) for name in MODELS},
        "default_detector": DEFAULT_MODEL,
    }


app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)
SAMPLES.mkdir(parents=True, exist_ok=True)
app.mount("/media/samples", StaticFiles(directory=str(SAMPLES)), name="samples")
app.mount("/media/uploads", StaticFiles(directory=str(UPLOADS)), name="uploads")


def snapshot_path(snap: dict) -> Path:
    return (SAMPLES if snap["src"] == "samples" else UPLOADS) / snap["filename"]


def linux_to_windows_path(path: Path) -> str:
    """Backward-compatible wrapper for callers using the old API helper."""
    from detector_config import to_detector_path
    return to_detector_path(path)


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
        "stage_requirements": {
            kind: [{"name": name, "classes": sorted(classes)} for name, classes in groups.items()]
            for kind, groups in rules.STAGE_REQUIRED.items()
        },
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
    """Finalize a detector result using the shared validated persistence path."""
    return persist_detection(snap_id, DETECTOR_OUT)


def _elapsed(date_from: str, date_to: str, today: str) -> float:
    """Share of the planned period that has passed, clamped to 0..1."""
    start, end, now = (date.fromisoformat(str(d)[:10]) for d in (date_from, date_to, today))
    span = (end - start).days
    if span <= 0:
        return 1.0 if now >= end else 0.0
    return max(0.0, min(1.0, (now - start).days / span))


def project_summary(card: dict, today: str) -> dict:
    """Portfolio-card facts: plan progress, current stage, latest evidence."""
    stages = card["stages"]
    stage = rules.active_stage(stages, today) if stages else None
    latest = card["snapshots"][0] if card["snapshots"] else None
    equipment: list[str] = []
    if latest:
        for det in latest["detections"]:
            label = det["label"]
            if (det["score"] >= rules.WARN_BOX_THRESHOLD and label not in rules.PPE_CLASSES
                    and label not in equipment):
                equipment.append(label)
    open_warnings = [w for w in card["warnings"] if w["status"] == "open"]
    return {
        "progress": round(_elapsed(min(st["date_from"] for st in stages),
                                   max(st["date_to"] for st in stages), today), 3)
        if stages else 0.0,
        "planned_finish": str(max(st["date_to"] for st in stages))[:10] if stages else None,
        "stage": {
            "name": stage["name"],
            "kind": stage["kind"],
            "date_from": str(stage["date_from"])[:10],
            "date_to": str(stage["date_to"])[:10],
            "position": stages.index(stage) + 1,
            "progress": round(_elapsed(stage["date_from"], stage["date_to"], today), 3),
        } if stage else None,
        "stages_total": len(stages),
        "last_snapshot": str(latest["captured_at"])[:10] if latest else None,
        "equipment": equipment,
        "violations_open": sum(1 for w in open_warnings if w["severity"] == "violation"),
        "reviews_open": sum(1 for w in open_warnings if w["severity"] != "violation"),
    }


@app.get("/api/objects")
def list_objects() -> list[dict]:
    out = []
    today = date.today().isoformat()
    for obj in db.query("SELECT * FROM objects ORDER BY id"):
        card = object_card(obj["id"])
        out.append({
            **obj,
            **card["counts"],
            **project_summary(card, today),
            "cover": (f"/api/snapshots/{card['snapshots'][0]['id']}/file"
                      if card["snapshots"] else None),
        })
    return out


@app.post("/api/objects")
def create_object(
    name: str = Form(...),
    type: str = Form("\u0416\u0438\u043b\u044c\u0451"),
    district: str = Form(""),
    address: str = Form(""),
) -> dict:
    name = name.strip()
    if not name:
        raise HTTPException(422, "name is required")
    new_id = db.execute(
        "INSERT INTO objects(name, type, district, address) VALUES (?,?,?,?)",
        (name, type.strip() or "\u0416\u0438\u043b\u044c\u0451", district.strip(), address.strip()),
    )
    return {"id": new_id}


@app.get("/api/objects/{object_id}")
def get_object(object_id: int) -> dict:
    card = object_card(object_id)
    return {**card, "summary": project_summary(card, date.today().isoformat())}


@app.post("/api/objects/{object_id}/plan/preview")
async def preview_plan(object_id: int, file: UploadFile = File(...)) -> dict:
    if not db.query("SELECT id FROM objects WHERE id=?", (object_id,)):
        raise HTTPException(404, "object not found")
    content = await file.read(2 * 1024 * 1024 + 1)
    return plan_import.parse_plan(content, file.filename or "")


@app.put("/api/objects/{object_id}/stages")
def save_stages(object_id: int, stages: list[dict]) -> dict:
    if not db.query("SELECT id FROM objects WHERE id=?", (object_id,)):
        raise HTTPException(404, "object not found")
    required = {"kind", "name", "date_from", "date_to", "status"}
    for st in stages:
        if not required.issubset(st):
            raise HTTPException(400, "stage requires kind, name, date_from, date_to and status")
        try:
            start = date.fromisoformat(st["date_from"])
            end = date.fromisoformat(st["date_to"])
        except (TypeError, ValueError) as exc:
            raise HTTPException(400, "stage dates must be YYYY-MM-DD") from exc
        if end < start:
            raise HTTPException(400, "stage date_to must not precede date_from")
        if st["kind"] not in rules.STAGE_ALLOWED:
            raise HTTPException(400, "unknown stage kind")
        if st["status"] not in {"done", "current", "future"}:
            raise HTTPException(400, "unknown stage status")
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
    if not db.query("SELECT id FROM warnings WHERE id=?", (warning_id,)):
        raise HTTPException(404, "warning not found")
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
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type)


@app.post("/api/objects/{object_id}/upload")
async def upload(object_id: int, file: UploadFile = File(...),
                 captured_at: str = Form(date.today().isoformat())) -> dict:
    if not db.query("SELECT id FROM objects WHERE id=?", (object_id,)):
        raise HTTPException(404, "object not found")
    try:
        date.fromisoformat(captured_at)
    except ValueError as exc:
        raise HTTPException(400, "captured_at must be YYYY-MM-DD") from exc

    # Read incrementally so a malicious upload cannot consume unbounded RAM.
    chunks: list[bytes] = []
    size = 0
    while chunk := await file.read(1024 * 1024):
        size += len(chunk)
        if size > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "image exceeds 20 MB")
        chunks.append(chunk)
    data = b"".join(chunks)
    if not data:
        raise HTTPException(400, "empty file")

    from PIL import Image, UnidentifiedImageError
    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
    try:
        with Image.open(io.BytesIO(data)) as im:
            image_format = im.format
            im.verify()
        with Image.open(io.BytesIO(data)) as im:
            w, h = im.size
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise HTTPException(400, "invalid or damaged image") from exc
    if image_format not in IMAGE_EXTENSIONS:
        raise HTTPException(400, "only PNG, JPEG and WebP images are accepted")

    name = f"up_{date.today().isoformat()}_{uuid.uuid4().hex[:12]}{IMAGE_EXTENSIONS[image_format]}"
    target = UPLOADS / name
    target.write_bytes(data)
    try:
        snap_id = db.execute(
            "INSERT INTO snapshots(object_id, filename, src, captured_at, status,"
            " width, height) VALUES (?,?,?,?,?,?,?)",
            (object_id, name, "uploads", captured_at, "new", w, h),
        )
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return {"id": snap_id, "status": "new"}


@app.post("/api/snapshots/{snapshot_id}/detect")
def start_detection(snapshot_id: int, model: str = Form(DEFAULT_MODEL)) -> dict:
    rows = db.query("SELECT * FROM snapshots WHERE id=?", (snapshot_id,))
    if not rows:
        raise HTTPException(404)
    try:
        model_name = canonical_model(model)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    snap = dict(rows[0])
    if snap["status"] == "processing":
        if finalize_detection(snapshot_id):
            return {"ok": True, "status": "detected"}
        return {"ok": True, "status": "processing"}
    if snap["status"] in {"detected", "empty"}:
        return {"ok": True, "status": snap["status"]}
    src = snapshot_path(snap)
    if not src.exists():
        raise HTTPException(404, "file missing")
    if not detector_available(model_name):
        raise HTTPException(503, f"detector runtime for {model_name} is not installed")
    out = DETECTOR_OUT / f"snap_{snapshot_id}.json"
    out.unlink(missing_ok=True)
    (DETECTOR_OUT / f"snap_{snapshot_id}.in.json").unlink(missing_ok=True)
    db.execute("UPDATE snapshots SET status='processing' WHERE id=?", (snapshot_id,))
    db.execute(
        "INSERT INTO detection_jobs(snapshot_id,model,status,attempts,error,started_at,finished_at)"
        " VALUES (?,?,'queued',0,NULL,NULL,NULL)"
        " ON CONFLICT(snapshot_id) DO UPDATE SET model=excluded.model,status='queued',"
        " attempts=0,error=NULL,started_at=NULL,finished_at=NULL",
        (snapshot_id, model_name),
    )
    audit.record("detection.queued", "snapshot", snapshot_id, details={"model": model_name})
    return {"ok": True, "status": "processing", "queue": "detection_jobs", "model": model_name}


@app.post("/api/objects/{object_id}/reevaluate")
def reevaluate(object_id: int) -> dict:
    return {"ok": True, "warnings": evaluate_object(object_id)}


@app.delete("/api/snapshots/{snapshot_id}")
def delete_snapshot(snapshot_id: int) -> dict:
    rows = db.query("SELECT * FROM snapshots WHERE id=?", (snapshot_id,))
    if not rows:
        raise HTTPException(404, "snapshot not found")
    snap = dict(rows[0])
    con = db.connect()
    try:
        con.execute("DELETE FROM detections WHERE snapshot_id=?", (snapshot_id,))
        con.execute("DELETE FROM detection_jobs WHERE snapshot_id=?", (snapshot_id,))
        con.execute("DELETE FROM warnings WHERE snapshot_id=?", (snapshot_id,))
        con.execute("DELETE FROM snapshots WHERE id=?", (snapshot_id,))
        con.commit()
    finally:
        con.close()
    if snap["src"] == "uploads":
        snapshot_path(snap).unlink(missing_ok=True)
    (DETECTOR_OUT / f"snap_{snapshot_id}.json").unlink(missing_ok=True)
    (DETECTOR_OUT / f"snap_{snapshot_id}.in.json").unlink(missing_ok=True)
    return {"ok": True}
