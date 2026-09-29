"""Rules engine: snapshot machinery vs. work stages of the object.

Rule codes (referenced in the UI as "Почему: правило R-xx"):
- R-01: machinery class is not allowed on the active stage.
- R-02: low confidence (< 0.5) or conflicting classes on one box — review.

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


IDLE_IOU = 0.55
SERIES_LIMIT = 3
ZONE_KINDS = {"work", "danger", "storage"}


def evaluate_snapshot(
    snapshot: dict,
    detections: list[dict],
    stages: list[dict],
    object_type: str | None = None,
    zones: list[dict] | None = None,
) -> list[dict]:
    """Return warning dicts for one snapshot. detections = joined models."""
    stage = active_stage(stages, snapshot["captured_at"])
    zone_warnings = _zone_warnings(snapshot, detections, stage, zones or [])
    if stage is None:
        return zone_warnings
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
            rule = "R-01"
            low = conf < CONF_THRESHOLD
            title = "Техника вне перечня этапа «%s»" % stage["name"]
            body = (
                "На снимке от %s обнаружен %s (уверенность %.2f). "
                "Этап «%s» не предполагает этот класс техники."
                % (snapshot["captured_at"], primary, score, stage["name"])
            )
            why = (
                f"Почему: правило {rule} "
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
    warnings.extend(zone_warnings)
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


def ready_snapshots(snapshots: list[dict]) -> list[dict]:
    """Detected frames, oldest first, so a series can be compared in time order."""
    ready = [snap for snap in snapshots if snap.get("status") in {"detected", "empty"}]
    ready.sort(key=lambda snap: (str(snap.get("captured_at", ""))[:10], int(snap.get("id") or 0)))
    return ready


def _boxes_by_label(snapshot: dict) -> dict[str, list[tuple[float, float, float, float]]]:
    width = float(snapshot.get("width") or 0)
    height = float(snapshot.get("height") or 0)
    grouped: dict[str, list[tuple[float, float, float, float]]] = {}
    if width <= 0 or height <= 0:
        return grouped
    for det in snapshot.get("detections") or []:
        if det.get("score", 0) < WARN_BOX_THRESHOLD or det.get("verdict") == "wrong":
            continue
        label = det.get("label")
        if not label or label in PPE_CLASSES:
            continue
        grouped.setdefault(label, []).append((
            float(det["x1"]) / width,
            float(det["y1"]) / height,
            float(det["x2"]) / width,
            float(det["y2"]) / height,
        ))
    return grouped


def series_motion(snapshots: list[dict]) -> dict:
    """Compare the last few frames. High IoU means the machine did not visibly move."""
    recent = ready_snapshots(snapshots)[-SERIES_LIMIT:]
    idle: dict[str, float] = {}
    moved: set[str] = set()
    for left, right in zip(recent, recent[1:]):
        left_boxes = _boxes_by_label(left)
        right_boxes = _boxes_by_label(right)
        for label in set(left_boxes) & set(right_boxes):
            score = max(iou(a, b) for a in left_boxes[label] for b in right_boxes[label])
            if score >= IDLE_IOU:
                idle[label] = max(idle.get(label, 0.0), score)
            else:
                moved.add(label)
    moved -= set(idle)
    if len(recent) < 2:
        verdict = "insufficient"
    elif idle:
        verdict = "idle"
    elif moved:
        verdict = "working"
    else:
        verdict = "insufficient"
    return {
        "verdict": verdict,
        "idle_labels": sorted(idle),
        "moved_labels": sorted(moved),
        "frames": len(recent),
    }


def evaluate_series(snapshots: list[dict]) -> list[dict]:
    """R-08: same class stays in one place across a short dated series."""
    motion = series_motion(snapshots)
    if motion["verdict"] != "idle":
        return []
    recent = ready_snapshots(snapshots)[-SERIES_LIMIT:]
    latest = recent[-1]
    labels = ", ".join(motion["idle_labels"])
    return [{
        "snapshot_id": latest["id"],
        "rule": "R-08",
        "title": "Техника на месте, активность по кадрам не подтверждена",
        "body": (
            "На последних снимках %s остаётся в одной области кадра. "
            "По серии это похоже на простой, но один кадр этого не доказывает."
            % labels
        ),
        "why": (
            "Почему: правило R-08 — если боксы одного класса почти совпадают "
            "(IoU > %.2f) на серии датированных снимков, активность не подтверждена. "
            "Нужен ещё кадр или выезд."
            % IDLE_IOU
        ),
        "source": "серия снимков · правило R-08",
        "severity": "review",
    }]


def point_in_polygon(x: float, y: float, polygon: list) -> bool:
    inside = False
    count = len(polygon)
    if count < 3:
        return False
    previous = count - 1
    for index in range(count):
        xi, yi = float(polygon[index][0]), float(polygon[index][1])
        xj, yj = float(polygon[previous][0]), float(polygon[previous][1])
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi):
            inside = not inside
        previous = index
    return inside


def _box_center(det: dict, snapshot: dict) -> tuple[float, float] | None:
    width = float(snapshot.get("width") or 0)
    height = float(snapshot.get("height") or 0)
    if width <= 0 or height <= 0:
        return None
    return (
        (float(det["x1"]) + float(det["x2"])) / 2 / width,
        (float(det["y1"]) + float(det["y2"])) / 2 / height,
    )


def _is_mounting(stage: dict | None) -> bool:
    if not stage:
        return False
    if stage.get("kind") in {"frame", "roof"}:
        return True
    return "монтаж" in str(stage.get("name", "")).lower()


def _zone_warnings(
    snapshot: dict, detections: list[dict], stage: dict | None, zones: list[dict]
) -> list[dict]:
    if not zones:
        return []
    danger: list[str] = []
    stored_cranes: list[str] = []
    for det in detections:
        if det.get("score", 0) < WARN_BOX_THRESHOLD or det.get("verdict") == "wrong":
            continue
        label = det.get("label")
        if not label or label in PPE_CLASSES:
            continue
        center = _box_center(det, snapshot)
        if center is None:
            continue
        for zone in zones:
            polygon = zone.get("polygon") or []
            if not point_in_polygon(center[0], center[1], polygon):
                continue
            kind = zone.get("kind")
            if kind == "danger" and label not in danger:
                danger.append(label)
            if kind == "storage" and label in CRANES and _is_mounting(stage) and label not in stored_cranes:
                stored_cranes.append(label)
    warnings: list[dict] = []
    if danger:
        warnings.append({
            "snapshot_id": snapshot["id"],
            "rule": "R-09",
            "title": "Техника в опасной зоне",
            "body": "На снимке от %s в опасной зоне: %s." % (snapshot["captured_at"], ", ".join(danger)),
            "why": (
                "Почему: правило R-09 — центр бокса техники попал в полигон «опасная зона», "
                "заданный в долях кадра. %s"
                % (f"Этап «{stage['name']}»." if stage else "Этап по дате снимка не найден.")
            ),
            "source": "зоны площадки · правило R-09",
            "severity": "violation",
        })
    if stored_cranes:
        stage_name = stage["name"] if stage else "монтаж"
        warnings.append({
            "snapshot_id": snapshot["id"],
            "rule": "R-10",
            "title": "Кран в зоне складирования на этапе монтажа",
            "body": "На этапе «%s» в зоне складирования: %s." % (stage_name, ", ".join(stored_cranes)),
            "why": (
                "Почему: правило R-10 — крановый класс в полигоне «склад» при этапе монтажа. "
                "Это вопрос инспектору, не подтверждённый простой."
            ),
            "source": "зоны площадки · правило R-10",
            "severity": "review",
        })
    return warnings
