"""Schedule forecast, equipment gap, and snapshot dynamics.

These are heuristics over the plan calendar and dated frames. They do not
measure physical readiness and they do not prove that a machine is idle.
"""
from __future__ import annotations

from datetime import date, timedelta

try:
    from . import rules
except ImportError:  # direct execution from backend/ remains supported
    import rules

LAG_COEFF = 0.5
PENALTY_EVERY = 2
WINDOW_DAYS = 30
DISCLAIMER = "Оценка по видимой части площадки. Это не измеренный процент готовности."


def _day(value: str) -> date:
    return date.fromisoformat(str(value)[:10])


def ru_count(number: int, forms: tuple[str, str, str]) -> str:
    count = abs(int(number))
    if 11 <= count % 100 <= 14:
        word = forms[2]
    elif count % 10 == 1:
        word = forms[0]
    elif 2 <= count % 10 <= 4:
        word = forms[1]
    else:
        word = forms[2]
    return f"{count} {word}"


def stage_for_date(stages: list[dict], value: str) -> dict | None:
    day = str(value)[:10]
    for stage in stages:
        if str(stage["date_from"])[:10] <= day <= str(stage["date_to"])[:10]:
            return stage
    return None


def _stage_index(stages: list[dict], stage: dict | None) -> int | None:
    if stage is None:
        return None
    if stage.get("id") is not None:
        for index, item in enumerate(stages):
            if item.get("id") == stage.get("id"):
                return index
    for index, item in enumerate(stages):
        if item.get("name") == stage.get("name") and str(item.get("date_from"))[:10] == str(stage.get("date_from"))[:10]:
            return index
    return None


def _open_schedule_issues(card: dict) -> int:
    count = 0
    for warning in card.get("warnings") or []:
        if warning.get("status") != "open":
            continue
        rule = str(warning.get("rule", ""))
        if rule.startswith("R-01") or rule.startswith("R-03"):
            count += 1
    return count


def _equipment_gap(card: dict, plan: dict | None, recent: list[dict]) -> dict:
    if plan is None:
        return {"window": rules.SERIES_LIMIT, "rows": []}
    required = rules.requirements_for_stage(plan, (card.get("object") or {}).get("type"))
    observed: set[str] = set()
    for snap in recent:
        for det in snap.get("detections") or []:
            if det.get("score", 0) < rules.WARN_BOX_THRESHOLD or det.get("verdict") == "wrong":
                continue
            label = det.get("label")
            if label and label not in rules.PPE_CLASSES:
                observed.add(label)
    rows = []
    for name, classes in required.items():
        seen = not observed.isdisjoint(classes)
        rows.append({"name": name, "seen": seen, "missing": not seen})
    return {"window": min(rules.SERIES_LIMIT, len(recent)) or rules.SERIES_LIMIT, "rows": rows}


def _activity(snapshots: list[dict], missing: bool) -> dict:
    motion = rules.series_motion(snapshots)
    verdict = motion["verdict"]
    labels = {
        "working": "предположительно работает",
        "idle": "вероятный простой",
        "insufficient": "данных мало",
    }
    notes = {
        "working": "Класс техники сместился между снимками. По серии это похоже на работу.",
        "idle": "Один и тот же класс остаётся в одной области кадра. Активность по серии не подтверждена.",
        "insufficient": "Нужны хотя бы два датированных снимка с техникой, чтобы судить о работе или простое.",
    }
    note = notes[verdict]
    if missing:
        note += " На этапе, где техника обязательна, на последних кадрах её не видно."
    return {
        "verdict": verdict,
        "label": labels[verdict],
        "note": note,
        "idle_labels": motion["idle_labels"],
        "moved_labels": motion["moved_labels"],
    }


def forecast_schedule(card: dict, today: str) -> dict:
    """Moderate scenario: calendar lag plus a fixed penalty for open R-01/R-03."""
    stages = list(card.get("stages") or [])
    recent = rules.ready_snapshots(card.get("snapshots") or [])[-rules.SERIES_LIMIT:]
    plan = stage_for_date(stages, today)
    latest = recent[-1] if recent else None
    fact = stage_for_date(stages, latest["captured_at"]) if latest else None
    gap = _equipment_gap(card, plan, recent)
    activity = _activity(card.get("snapshots") or [], any(row["missing"] for row in gap["rows"]))
    base = {
        "fact_stage": fact["name"] if fact else None,
        "plan_stage": plan["name"] if plan else None,
        "disclaimer": DISCLAIMER,
        "equipment_gap": gap,
        "activity": activity,
        "scenario": "умеренный",
    }
    if len(recent) < 2 or plan is None:
        reason = "Мало датированных снимков для прогноза." if len(recent) < 2 else "На сегодня в плане нет этапа."
        return {
            **base,
            "verdict": "unknown",
            "days_delta": None,
            "pace": "unknown",
            "pace_label": "данных мало",
            "confidence": "low",
            "drivers": [reason],
            "headline": "Прогноз: недостаточно данных",
        }

    plan_index = _stage_index(stages, plan)
    fact_index = _stage_index(stages, fact)
    snap_stages = [stage_for_date(stages, snap["captured_at"]) for snap in recent]
    kinds = {stage["kind"] for stage in snap_stages if stage}
    all_same = len(kinds) == 1 and all(stage is not None for stage in snap_stages)
    drivers: list[str] = []
    days = 0

    if fact_index is not None and plan_index is not None and fact_index > plan_index and fact is not None:
        pace, pace_label = "ahead", "опережает"
        start = _day(fact["date_from"])
        today_day = _day(today)
        ahead_days = max(1, (start - today_day).days) if start > today_day else max(1, fact_index - plan_index)
        days = -ahead_days
        drivers.append(f"По датам снимков этап «{fact['name']}» впереди планового «{plan['name']}».")
    elif all_same and fact is not None and fact_index is not None and plan_index is not None and fact_index < plan_index:
        pace, pace_label = "stuck", "этап не сдвинулся"
        overdue = (_day(today) - _day(fact["date_to"])).days
        if overdue > 0:
            days = overdue
            drivers.append(
                f"Последние снимки остаются на этапе «{fact['name']}», план уже на «{plan['name']}». "
                f"Просрочка {ru_count(overdue, ('день', 'дня', 'дней'))}."
            )
        else:
            on_stage = max(0, (_day(today) - _day(fact["date_from"])).days)
            days = max(1, int(round(on_stage * LAG_COEFF)))
            drivers.append(f"За последние снимки этап не сменился, хотя по плану уже «{plan['name']}».")
    elif all_same and fact is not None and _day(fact["date_to"]) < _day(today):
        pace, pace_label = "stuck", "этап не сдвинулся"
        days = (_day(today) - _day(fact["date_to"])).days
        drivers.append(f"Этап «{fact['name']}» должен был завершиться {fact['date_to']}, снимки с него не ушли.")
    else:
        changed = len(kinds) > 1
        pace, pace_label = ("moved", "сдвинулся") if changed else ("steady", "без смены этапа")
        drivers.append("По датам снимков этап сменился." if changed else "Снимки и план на одном этапе.")

    issues = _open_schedule_issues(card)
    penalty = issues // PENALTY_EVERY
    if penalty:
        days += penalty
        drivers.append(f"Открытые R-01/R-03: {issues}, штраф +{ru_count(penalty, ('день', 'дня', 'дней'))}.")

    if days > 0:
        verdict = "behind"
        headline = f"Прогноз: отставание ~{ru_count(days, ('день', 'дня', 'дней'))} (сценарий умеренный)"
    elif days < 0:
        verdict = "ahead"
        headline = f"Прогноз: опережение ~{ru_count(days, ('день', 'дня', 'дней'))} (сценарий умеренный)"
    else:
        verdict = "on_track"
        headline = "Прогноз: по графику (сценарий умеренный)"

    return {
        **base,
        "verdict": verdict,
        "days_delta": days,
        "pace": pace,
        "pace_label": pace_label,
        "confidence": "medium" if len(recent) <= rules.SERIES_LIMIT else "high",
        "drivers": drivers,
        "headline": headline,
    }


def _week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def build_dynamics(card: dict, today: str, window_days: int = WINDOW_DAYS) -> dict:
    end = _day(today)
    start = end - timedelta(days=window_days)
    stages = list(card.get("stages") or [])
    snaps = [
        snap for snap in rules.ready_snapshots(card.get("snapshots") or [])
        if start <= _day(snap["captured_at"]) <= end
    ]
    buckets: dict[date, dict] = {}
    for snap in snaps:
        week = _week_start(_day(snap["captured_at"]))
        bucket = buckets.setdefault(week, {
            "date": week.isoformat(),
            "snapshots": 0,
            "stage_kind": None,
            "stage_name": None,
            "violations": 0,
            "reviews": 0,
            "equipment_present": [],
        })
        bucket["snapshots"] += 1
        stage = stage_for_date(stages, snap["captured_at"])
        if stage:
            bucket["stage_kind"] = stage.get("kind")
            bucket["stage_name"] = stage.get("name")
        seen = set(bucket["equipment_present"])
        for det in snap.get("detections") or []:
            label = det.get("label")
            if not label or label in rules.PPE_CLASSES or det.get("score", 0) < rules.WARN_BOX_THRESHOLD:
                continue
            if det.get("verdict") == "wrong":
                continue
            seen.add(label)
        bucket["equipment_present"] = sorted(seen)

    for warning in card.get("warnings") or []:
        captured = warning.get("captured_at")
        if warning.get("status") != "open" or not captured:
            continue
        captured_day = _day(captured)
        if not (start <= captured_day <= end):
            continue
        bucket = buckets.get(_week_start(captured_day))
        if bucket is None:
            continue
        if warning.get("severity") == "violation":
            bucket["violations"] += 1
        else:
            bucket["reviews"] += 1

    points = [buckets[key] for key in sorted(buckets)]
    stage_names = {point["stage_name"] for point in points if point["stage_name"]}
    if not snaps:
        stage_phrase = "снимков нет"
    elif len(stage_names) <= 1:
        stage_phrase = "этап не менялся"
    else:
        stage_phrase = "этап менялся"
    repeats: dict[str, int] = {}
    for warning in card.get("warnings") or []:
        captured = warning.get("captured_at")
        if not captured or not (start <= _day(captured) <= end):
            continue
        rule = str(warning.get("rule") or "")
        repeats[rule] = repeats.get(rule, 0) + 1
    repeated = sum(1 for count in repeats.values() if count >= 2)
    if repeated == 0:
        repeat_phrase = "повторов нарушений нет"
    elif repeated == 1:
        repeat_phrase = "1 нарушение повторяется"
    else:
        repeat_phrase = f"{ru_count(repeated, ('нарушение', 'нарушения', 'нарушений'))} повторяются"
    if not snaps:
        sentence = f"За {window_days} дней снимков нет — тренд не строится."
    else:
        sentence = (
            f"За {window_days} дней: {ru_count(len(snaps), ('снимок', 'снимка', 'снимков'))}, "
            f"{stage_phrase}, {repeat_phrase}."
        )
    return {"window_days": window_days, "points": points, "sentence": sentence}


def recognition_quality(card: dict) -> dict:
    rows = [det for snap in card.get("snapshots") or [] for det in snap.get("detections") or []]
    correct = sum(1 for det in rows if det.get("verdict") == "correct")
    wrong = sum(1 for det in rows if det.get("verdict") == "wrong")
    pending = sum(1 for det in rows if not det.get("verdict"))
    rated = correct + wrong
    return {
        "correct": correct,
        "wrong": wrong,
        "pending": pending,
        "total": len(rows),
        "rated": rated,
        "correct_share": round(correct / rated, 3) if rated else None,
        "note": "Оценки инспектора, не метрика модели",
    }
