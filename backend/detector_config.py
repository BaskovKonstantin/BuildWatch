"""Shared detector configuration and WSL/Windows path handling."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DETECTOR_OUT = ROOT / "backend" / "media" / "detector"
WINDOWS_PYTHON = ROOT / ".venv-cpu" / "Scripts" / "python.exe"
DETECTOR_PYTHON = WINDOWS_PYTHON if WINDOWS_PYTHON.exists() else Path(os.environ.get("PYTHON", os.sys.executable))


@dataclass(frozen=True)
class DetectorConfig:
    name: str
    script: Path
    weights: Path


MODELS = {
    "equipment": DetectorConfig(
        "equipment",
        ROOT / "scripts" / "detect_equipment_single.py",
        ROOT / "context" / "external" / "equipment_external_v2" / "training_run_m1280" / "runs" / "equipment_v1" / "weights" / "best.pt",
    ),
}
# Legacy detector names (pre-2026-09) are re-routed to the trained detector.
MODEL_ALIASES = {
    "yolo-world": "equipment",
    "yolo_world": "equipment",
    "yoloworld": "equipment",
    "uisikdag": "equipment",
    "thalos": "equipment",
    "ensemble": "equipment",
    "ансамбль": "equipment",
}
DEFAULT_MODEL = os.getenv("BUILDWATCH_DETECTOR_MODEL", "equipment")


def canonical_model(value: str | None) -> str:
    key = (value or DEFAULT_MODEL).strip().lower().replace(" ", "-")
    key = MODEL_ALIASES.get(key, key)
    if key not in MODELS:
        raise ValueError(f"unknown detector model: {value}")
    return key


def model_config(value: str | None) -> DetectorConfig:
    return MODELS[canonical_model(value)]


def to_detector_path(path: Path | str) -> str:
    """Convert a WSL /mnt mount to a path accepted by a Windows process."""
    text = str(path)
    # pathlib on Windows turns Path("/mnt/d/...") into "\\mnt\\d\\...".
    normalized = text.replace("\\", "/")
    if normalized.lower().startswith("/mnt/") and len(normalized) > 6:
        drive = normalized[5].upper()
        return f"{drive}:" + normalized[6:].replace("/", "\\")
    return text


def uses_windows_runtime() -> bool:
    return DETECTOR_PYTHON.suffix.lower() == ".exe"


def runtime_path(path: Path | str) -> str:
    return to_detector_path(path) if uses_windows_runtime() else str(path)


def detector_available(value: str | None = None) -> bool:
    key = canonical_model(value)
    if key == "ensemble":
        return all(detector_available(name) for name in MODELS)
    config = MODELS[key]
    return DETECTOR_PYTHON.exists() and config.script.exists() and config.weights.exists()
