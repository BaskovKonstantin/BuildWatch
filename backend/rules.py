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
    "excavator", "dump truck", "truck", "bulldozer", "loader", "grader", "road roller",
    "concrete mixer", "mobile crane", "tower crane", "truck crane",
    "crane manipulator", "concrete pump", "drilling rig", *PPE_CLASSES,
}

# Allowed machinery per stage kind (editable vocabulary, ЛТЦ-agnostic)
STAGE_ALLOWED: dict[str, set[str]] = {
    kind: classes | PPE_CLASSES
    for kind, classes in {
        "ground": {"truck", "dump truck", "excavator", "bulldozer", "loader", "drilling rig", "road roller"},
        "excavation": {"excavator", "dump truck", "bulldozer", "loader", "truck", "drilling rig", "concrete pump", "road roller"},
        "frame": {"tower crane", "truck crane", "mobile crane", "crane manipulator",
                  "concrete mixer", "concrete pump", "truck", "drilling rig", "bulldozer", "excavator"},
        "facade": {"truck", "dump truck", "concrete mixer", "excavator", "bulldozer",
                   "road roller", *CRANES},
        "roof": {"truck", "dump truck", "mobile crane", "truck crane", "tower crane", "concrete mixer"},
        "other": set(),
    }.items()
}

# uisikdag class typos → canonical labels
# Minimum expected capabilities for a stage. Each named requirement is
# satisfied by at least one class from its alternatives. This avoids brittle
# rules such as requiring a tower crane when a mobile crane is valid too.
STAGE_REQUIRED: dict[str, dict[str, set[str]]] = {
    "ground": {
        "земляная техника": {"excavator", "bulldozer", "loader"},
        "транспорт": {"truck", "dump truck"},
    },
    "excavation": {
        "экскаватор": {"excavator"},
        "самосвал": {"dump truck"},
    },
    "frame": {
        "кран": set(CRANES),
        "бетонная техника": {"concrete mixer", "concrete pump"},
    },
    "facade": {
        "транспорт для доставки": {"truck", "dump truck"},
    },
    "roof": {"кран": set(CRANES)},
    "other": {},
}

# Refine broad plan kinds using the exact work names from the ДГП / ЛТЦ test
# catalog. Snapshot detectors only report visible objects, so these are
# minimum evidence groups rather than a claim that every machine must appear
# in every camera frame.
STAGE_REQUIRED_BY_NAME: dict[str, dict[str, set[str]]] = {
    "Монтаж фасадной системы": {
        "подъёмная или доставочная техника": {"truck", "dump truck", *CRANES},
    },
    "Монтаж металлоконструкций каркаса": {
        "кран": set(CRANES),
    },
    "Монолитный каркас": {
        "бетонная техника": {"concrete mixer", "concrete pump"},
        "кран": set(CRANES),
    },
    "Устройство буронабивных свай": {
        "буровая установка": {"drilling rig"},
        "транспорт": {"truck", "dump truck"},
    },
    "Устройство фундаментной плиты": {
        "бетонная техника": {"concrete mixer", "concrete pump"},
    },
    "Устройство фундаментов": {
        "бетонная техника": {"concrete mixer", "concrete pump"},
    },
    "Монолитные работы ниже отм. 0": {
        "бетонная техника": {"concrete mixer", "concrete pump"},
    },
    "Монолитные работы выше отм. 0": {
        "бетонная техника": {"concrete mixer", "concrete pump"},
    },
    "Покрытие дорожной одежды": {
        "дорожная техника": {"grader", "road roller", "bulldozer"},
        "транспорт": {"truck", "dump truck"},
    },
    "Устройство нижнего слоя основания": {
        "уплотняющая техника": {"road roller"},
        "транспорт": {"truck", "dump truck"},
    },
}


def requirements_for_stage(stage: dict, object_type: str | None = None) -> dict[str, set[str]]:
    """Return evidence groups for an exact plan stage, with kind fallback."""
    del object_type  # reserved for object-type-specific catalog extensions
    return STAGE_REQUIRED_BY_NAME.get(
        stage.get("name", ""), STAGE_REQUIRED.get(stage.get("kind", "other"), {})
    )


def allowed_for_stage(stage: dict, object_type: str | None = None) -> set[str]:
    """Equipment classes accepted for the active work; refine road surfacing."""
    del object_type
    if stage.get("name") == "Покрытие дорожной одежды":
        return {"truck", "dump truck", "bulldozer", "loader", "grader", "road roller"} | PPE_CLASSES
    return STAGE_ALLOWED.get(stage.get("kind", "other"), set())

LABEL_FIXES = {
    "dumb_truck": "dump truck", "bull_dozer": "bulldozer",
    "road_roller": "road roller", "concrete_mixer": "concrete mixer",
    "mobile_crane": "mobile crane", "tower_crane": "tower crane",
    "truck_crane": "truck crane", "crane_manipulator": "crane manipulator",
    "concrete_pump": "concrete pump", "drilling_rig": "drilling rig",
    "backhoe_loader": "loader", "wheel_loader": "loader",
    "compactor": "road roller", "concrete_mixer_truck": "concrete mixer",
    "dozer": "bulldozer", "dump_truck": "dump truck",
    "grader": "grader",
}


def normalize_label(raw: str) -> str:
    label = raw.strip().lower().replace("_", " ")
    fixed = LABEL_FIXES.get(label.replace(" ", "_"), label)
    # UISikDag keeps loader as its own class; it is not a bulldozer.
    return {"roller": "road roller"}.get(fixed, fixed)


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
    """Group duplicate boxes, including the same object seen by two models."""
    groups: list[dict] = []
    for det in sorted(dets, key=lambda d: -d["score"]):
        box = (det["x1"], det["y1"], det["x2"], det["y2"])
        model = det.get("model", "unknown")
        matched = False
        for group in groups:
            overlap = iou(group["box"], box)
            cross_model = model not in group["models"]
            if overlap > 0.85 or (cross_model and overlap > 0.5):
                group["labels"].append((det["label"], det["score"]))
                group["models"].add(model)
                matched = True
                break
        if not matched:
            groups.append({"box": box, "labels": [(det["label"], det["score"])], "models": {model}})
    return groups


def evaluate_snapshot(
    snapshot: dict, detections: list[dict], stages: list[dict], object_type: str | None = None
) -> list[dict]:
    """Return warning dicts for one snapshot. detections = joined models."""
    stage = active_stage(stages, snapshot["captured_at"])
    if stage is None:
        return []
    allowed = allowed_for_stage(stage, object_type)
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
    # R-03: required equipment is not visible in this detector result. A
    # single frame cannot prove that equipment is absent from the site, so it
    # is a human-review question, not a confirmed plan violation.
    required = requirements_for_stage(stage, object_type)
    if required and snapshot.get("status") in {"detected", "empty"}:
        observed = {
            d["label"] for d in detections
            if d["score"] >= WARN_BOX_THRESHOLD and d["label"] in ALL_CLASSES
        }
        missing = sorted(
            name for name, alternatives in required.items()
            if observed.isdisjoint(alternatives)
        )
        if missing:
            warnings.append({
                "snapshot_id": snapshot["id"],
                "rule": "R-03",
                "title": "Не подтверждена обязательная техника",
                "body": (
                    "На снимке для этапа «%s» не распознано: %s. "
                    "Проверьте, попадает ли нужная зона в кадр и присутствует ли техника на площадке."
                    % (stage["name"], ", ".join(missing))
                ),
                "why": (
                    "Почему: правило R-03 — отсутствие детекции на одном снимке "
                    "не доказывает отсутствие техники; классы сверяются выше порога %.2f. Этап «%s»."
                    % (WARN_BOX_THRESHOLD, stage["name"])
                ),
                "source": "план объекта + методика «этап → обязательная техника»",
                "severity": "review",
            })
    return warnings


def detection_match(detection: dict, stages: list[dict], snapshot_date: str, object_type: str | None = None) -> str:
    """ok | mismatch | review for a single detection row."""
    stage = active_stage(stages, snapshot_date)
    allowed = allowed_for_stage(stage, object_type) if stage else set()
    if detection["score"] < CONF_THRESHOLD and detection["label"] not in allowed:
        return "review"
    if detection["label"] not in allowed:
        return "mismatch"
    if detection["score"] < CONF_THRESHOLD:
        return "review"
    return "ok"
