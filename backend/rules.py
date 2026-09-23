"""Rules engine: snapshot machinery vs. work stages of the object.

Rule codes (referenced in the UI as "Почему: правило R-xx"):
- R-01: machinery class is not allowed on the active stage.
- R-02: low confidence (< 0.5) or conflicting classes on one box — review.
- R-07: crane classes are only allowed on mounting stages (frame/roof).

The work-type vocabulary comes from the ЛТЦ catalog; the stage dates come
from the object plan (stages editor) — the ЛТЦ file itself has no calendar.
"""
from __future__ import annotations

from datetime import date

CONF_THRESHOLD = 0.5
BOX_THRESHOLD = 0.15      # storage / UI display floor
WARN_BOX_THRESHOLD = 0.35 # rules engine floor (cuts low-conf noise)

# uisikdag PPE/people classes — allowed on every stage (ensemble input for
# future PPE rules like «no helmets»); normalize_label maps the typos.
PPE_CLASSES = {"worker", "safety helmet", "vest"}

# Machinery groups
CRANES = {"tower crane", "truck crane", "mobile crane", "crane manipulator"}
ALL_CLASSES = {
    "excavator", "dump truck", "truck", "bulldozer", "road roller",
    "concrete mixer", "mobile crane", "tower crane", "truck crane",
    "crane manipulator", "concrete pump", "drilling rig", *PPE_CLASSES,
}

# Allowed machinery per stage kind (editable vocabulary, ЛТЦ-agnostic)
STAGE_ALLOWED: dict[str, set[str]] = {
    kind: classes | PPE_CLASSES
    for kind, classes in {
        "ground": {"truck", "dump truck", "excavator", "bulldozer", "drilling rig", "road roller"},
        "excavation": {"excavator", "dump truck", "bulldozer", "truck", "drilling rig", "concrete pump", "road roller"},
        "frame": {"tower crane", "truck crane", "mobile crane", "crane manipulator",
                  "concrete mixer", "concrete pump", "truck", "drilling rig", "bulldozer", "excavator"},
        "facade": {"truck", "dump truck", "concrete mixer", "excavator", "bulldozer", "road roller"},
        "roof": {"truck", "dump truck", "mobile crane", "truck crane", "tower crane", "concrete mixer"},
        "other": set(),
    }.items()
}

# uisikdag class typos → canonical labels
LABEL_FIXES = {
    "dumb_truck": "dump truck", "bull_dozer": "bulldozer",
    "road_roller": "road roller", "concrete_mixer": "concrete mixer",
    "mobile_crane": "mobile crane", "tower_crane": "tower crane",
    "truck_crane": "truck crane", "crane_manipulator": "crane manipulator",
    "concrete_pump": "concrete pump", "drilling_rig": "drilling rig",
}


def normalize_label(raw: str) -> str:
    label = raw.strip().lower().replace("_", " ")
    fixed = LABEL_FIXES.get(label.replace(" ", "_"), label)
    # uisikdag synonyms → canonical vocabulary
    return {"roller": "road roller", "loader": "bulldozer"}.get(fixed, fixed)


def active_stage(stages: list[dict], date: str) -> dict | None:
    """Stage whose period contains the snapshot date; fallback by status."""
    for st in stages:
        if st["date_from"] <= date <= st["date_to"]:
            return st
    for st in stages:
        if st["status"] == "current":
            return st
    return None


def iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def group_detections(dets: list[dict]) -> list[dict]:
    """Merge overlapping boxes (IoU>0.85) into single groups."""
    groups: list[dict] = []
    for det in sorted(dets, key=lambda d: -d["score"]):
        box = (det["x1"], det["y1"], det["x2"], det["y2"])
        for group in groups:
            if iou(group["box"], box) > 0.85:
                group["labels"].append((det["label"], det["score"]))
                continue
        else:
            groups.append({"box": box, "labels": [(det["label"], det["score"])]})
    return groups


def evaluate_snapshot(
    snapshot: dict, detections: list[dict], stages: list[dict]
) -> list[dict]:
    """Return warning dicts for one snapshot. detections = joined models."""
    stage = active_stage(stages, snapshot["captured_at"])
    if stage is None:
        return []
    allowed = STAGE_ALLOWED.get(stage["kind"], set())
    warnings: list[dict] = []
    for group in group_detections(detections):
        labels = sorted(group["labels"], key=lambda p: -p[1])
        primary, score = labels[0]
        conf = round(score, 2)
        others = [(lab, sc) for lab, sc in labels if lab != primary]
        if score < WARN_BOX_THRESHOLD and primary not in CRANES:
            continue  # noise floor: only crane flags survive below it
        src = f"боксы {', '.join(l for l, _ in labels)} · правило"
        why_base = (
            f"Активный этап «{stage['name']}» ({stage['date_from']} – {stage['date_to']})."
        )
        if primary not in allowed:
            rule = "R-07" if primary in CRANES and stage["kind"] == "facade" else "R-01"
            low = conf < CONF_THRESHOLD
            title = (
                "Техника не соответствует этапу «%s»" % stage["name"]
                if rule == "R-07"
                else "Техника вне перечня этапа «%s»" % stage["name"]
            )
            body = (
                "На снимке от %s обнаружен %s (уверенность %.2f). "
                "Этап «%s» не предполагает этот класс техники."
                % (snapshot["captured_at"], primary, score, stage["name"])
            )
            why = (
                f"Почему: правило {rule} "
                + ("«крановые классы → этапы монтажа»; " if rule == "R-07" else "")
                + f"класс «{primary}» не входит в перечень допустимых. {why_base}"
                + (f" Уверенность низкая ({conf}) — требуется визуальная проверка." if low else "")
            )
            warnings.append({
                "snapshot_id": snapshot["id"],
                "rule": rule + ("+R-02" if low else ""),
                "title": title,
                "body": body,
                "why": why,
                "source": f"боксы: {', '.join(l for l, _ in labels)} · план объекта + справочник ЛТЦ",
                "severity": "review" if low else "violation",
            })
        elif conf < CONF_THRESHOLD and (others or score < 0.3):
            # R-02 fires on a real class conflict on one box, or a very low score.
            warnings.append({
                "snapshot_id": snapshot["id"],
                "rule": "R-02",
                "title": "Низкая уверенность детекции",
                "body": (
                    "Класс определён на пороге: %s %.2f%s — пересекающиеся боксы на одном объекте."
                    % (primary, score,
                       (" / " + " / ".join(f"{l} {s:.2f}" for l, s in others) if others else ""))
                ),
                "why": (
                    "Почему: правило R-02 — при conf < 0.5 и конфликте классов назначается статус "
                    "«требует проверки», нарушение не выставляется."
                ),
                "source": f"боксы: {', '.join(l for l, _ in labels)} · правило R-02",
                "severity": "review",
            })
    return warnings


def detection_match(detection: dict, stages: list[dict], snapshot_date: str) -> str:
    """ok | mismatch | review for a single detection row."""
    stage = active_stage(stages, snapshot_date)
    allowed = STAGE_ALLOWED.get(stage["kind"], set()) if stage else set()
    if detection["score"] < CONF_THRESHOLD and detection["label"] not in allowed:
        return "mismatch"
    if detection["label"] not in allowed:
        return "mismatch"
    if detection["score"] < CONF_THRESHOLD:
        return "review"
    return "ok"
