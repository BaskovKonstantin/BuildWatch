"use client";

import { FormEvent, KeyboardEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { NavBar } from "@/components/NavBar";
import { Decision, ReviewQueue, SignalGroup, groupSignals, relatedDetectionIds } from "@/components/ReviewQueue";
import {
  IconBan, IconCalendar, IconCheck, IconChevronLeft, IconChevronRight, IconClose, IconPin, IconPlus, IconQuestion, IconUpload, IconWarning,
} from "@/components/Icons";
import { apiFetch } from "@/lib/api";
import { useThemeId } from "@/lib/themes";
import { equipmentRu, shortDate, typeTint } from "@/lib/format";

type Detection = {
  id: number;
  model: string;
  label: string;
  score: number;
  x1: number; y1: number; x2: number; y2: number;
  match: "ok" | "mismatch" | "review";
};
type Snapshot = {
  id: number;
  filename: string;
  captured_at: string;
  status: string;
  width: number;
  height: number;
  detections: Detection[];
};
type Stage = {
  id: number;
  kind: string;
  name: string;
  date_from: string;
  date_to: string;
  status: string;
};
type Warning = {
  id: number;
  snapshot_id: number;
  rule: string;
  title: string;
  body: string;
  why: string;
  source: string;
  status: string;
  severity: string;
  captured_at: string | null;
};
type HumanEvent = {
  id: number;
  object_id: number;
  stage_id: number | null;
  snapshot_id: number | null;
  event_type: "human";
  title: string;
  body: string;
  event_date: string;
  created_at: string;
};
type TimelineEvent = {
  id: string;
  kind: "snapshot" | "problem" | "question" | "human";
  date: string;
  title: string;
  body: string;
  snapshotId?: number;
  stageId?: number;
  warningId?: number;
  tone: string;
};
type Summary = {
  progress: number;
  planned_finish: string | null;
  stage: { name: string; position: number; progress: number; date_to: string } | null;
  stages_total: number;
  last_snapshot: string | null;
  violations_open: number;
  reviews_open: number;
};
type Card = {
  object: { id: number; name: string; type: string; district?: string; address?: string; description?: string };
  summary?: Summary;
  stages: Stage[];
  stage_kinds: string[];
  stage_requirements: Record<string, { name: string; classes: string[] }[]>;
  snapshots: Snapshot[];
  warnings: Warning[];
  events?: HumanEvent[];
  counts: { snapshots: number; warnings_open: number; warnings_total: number };
  conf_threshold: number;
};

const MODEL_LABELS: Record<string, string> = { equipment: "Equipment v2" };
const KIND_RU: Record<string, string> = {
  ground: "подготовка", excavation: "котлован", frame: "каркас",
  facade: "фасады", roof: "кровля", other: "прочее",
};

function fmt(d: string) {
  if (!d) return "Дата не задана";
  const [y, m, dd] = d.split("-");
  return `${dd}.${m}.${y}`;
}

function timelineClass(snap: Snapshot): string {
  if (snap.status === "processing") return "processing";
  if (snap.status === "failed") return "bad";
  const violations = snap.detections.filter((d) => d.match === "mismatch");
  const reviews = snap.detections.filter((d) => d.match === "review");
  if (violations.length) return "bad";
  if (snap.status === "new" || snap.status === "empty") return "new";
  if (reviews.length) return "warn";
  return "ok";
}

export default function Page() {
  const params = useParams<{ id: string }>();
  return <ObjectCard id={params.id} />;
}

function ObjectCard({ id }: { id: string }) {
  const deepLinkApplied = useRef(false);
  const deepLinkScrolled = useRef(false);
  const [card, setCard] = useState<Card | null>(null);
  const [snapId, setSnapId] = useState<number | null>(null);
  const [model] = useState("equipment");
  const [conf, setConf] = useState(0.2);
  const [showBoxes, setShowBoxes] = useState(true);
  const [hlBox, setHlBox] = useState<string | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [error, setError] = useState("");
  const [humanEvents, setHumanEvents] = useState<HumanEvent[]>([]);
  const [eventView, setEventView] = useState<"timeline" | "calendar">("timeline");
  const [eventFormOpen, setEventFormOpen] = useState(false);
  const [eventTitle, setEventTitle] = useState("");
  const [eventBody, setEventBody] = useState("");
  const [eventDate, setEventDate] = useState(new Date().toISOString().slice(0, 10));
  const [eventStageId, setEventStageId] = useState("");
  const [eventSaving, setEventSaving] = useState(false);
  const [detectionDecisions, setDetectionDecisions] = useState<Record<number, "confirm" | "dismiss">>({});
  const [collapsedStages, setCollapsedStages] = useState<Record<number, boolean>>({});
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const [nextObject, setNextObject] = useState<{ id: number; name: string; open: number } | null>(null);

  const load = useCallback(async () => {
    const res = await apiFetch(`/api/objects/${id}`);
    if (!res.ok) return;
    const data: Card = await res.json();
    setCard(data);
    const eventsResponse = await apiFetch(`/api/objects/${id}/events`);
    if (eventsResponse.ok) setHumanEvents(await eventsResponse.json());
    const requestedSnapshot = !deepLinkApplied.current && typeof window !== "undefined" ? Number(new URLSearchParams(window.location.search).get("snapshot")) : 0;
    deepLinkApplied.current = true;
    setSnapId((cur) =>
      requestedSnapshot && data.snapshots.some((s) => s.id === requestedSnapshot)
        ? requestedSnapshot
        :
      cur && data.snapshots.some((s) => s.id === cur)
        ? cur
        : (data.snapshots[0]?.id ?? null),
    );
  }, [id]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    const refresh = (event: Event) => {
      if ((event as CustomEvent<{ objectId: number }>).detail?.objectId === Number(id)) void load();
    };
    window.addEventListener("buildwatch:plan-updated", refresh);
    return () => window.removeEventListener("buildwatch:plan-updated", refresh);
  }, [id, load]);

  const snap = useMemo(
    () => card?.snapshots.find((s) => s.id === snapId) ?? null,
    [card, snapId],
  );
  const warnings = useMemo(
    () => (card ? card.warnings.filter((w) => w.snapshot_id === snapId) : []),
    [card, snapId],
  );
  const signalGroups = useMemo(() => groupSignals(card?.warnings ?? []), [card]);
  const openGroupCount = signalGroups.filter((g) => g.open.length > 0).length;

  const activateGroup = useCallback((key: string) => {
    setActiveKey(key);
    const group = signalGroups.find((g) => g.key === key);
    if (group) setSnapId(group.snapshotId);
  }, [signalGroups]);

  useEffect(() => {
    if (deepLinkScrolled.current || !card) return;
    deepLinkScrolled.current = true;
    const params = new URLSearchParams(window.location.search);
    const warningId = Number(params.get("warning"));
    const target = signalGroups.find((g) => g.items.some((w) => w.id === warningId))
      ?? signalGroups.find((g) => g.open.length > 0);
    if (target) activateGroup(target.key);
    if (warningId || params.has("review")) {
      requestAnimationFrame(() => document.getElementById("review-desk")?.scrollIntoView({ block: "start", behavior: "smooth" }));
    }
  }, [card, signalGroups, activateGroup]);

  useEffect(() => {
    if (!card || openGroupCount > 0) { setNextObject(null); return; }
    let cancelled = false;
    apiFetch("/api/objects").then(async (res) => {
      if (!res.ok || cancelled) return;
      const list: { id: number; name: string; violations_open: number; reviews_open: number }[] = await res.json();
      const next = list
        .filter((p) => p.id !== card.object.id && p.violations_open + p.reviews_open > 0)
        .sort((a, b) => b.violations_open + b.reviews_open - (a.violations_open + a.reviews_open))[0];
      if (!cancelled) setNextObject(next ? { id: next.id, name: next.name, open: next.violations_open + next.reviews_open } : null);
    }).catch(() => undefined);
    return () => { cancelled = true; };
  }, [card, openGroupCount]);

  const resolveGroup = useCallback(async (group: SignalGroup, decision: Decision) => {
    const targets = decision === "reopen" ? group.items : group.open;
    const status = { confirm: "confirmed", dismiss: "dismissed", reopen: "open" }[decision];
    const ids = new Set(targets.map((w) => w.id));
    if (decision !== "reopen") {
      const order = signalGroups.filter((g) => g.open.length > 0);
      const idx = order.findIndex((g) => g.key === group.key);
      const next = order[idx + 1] ?? order[idx - 1];
      if (next && next.key !== group.key) activateGroup(next.key);
    }
    setCard((cur) => cur && { ...cur, warnings: cur.warnings.map((w) => ids.has(w.id) ? { ...w, status } : w) });
    try {
      await Promise.all(targets.map((w) => {
        const body = new FormData();
        body.set("action", decision);
        return apiFetch(`/api/warnings/${w.id}`, { method: "POST", body });
      }));
    } catch {
      setError("Не удалось сохранить решение. Обновите страницу и повторите.");
    }
    void load();
  }, [signalGroups, activateGroup, load]);

  const activeGroup = signalGroups.find((g) => g.key === activeKey) ?? null;
  const focusIds = useMemo(
    () => relatedDetectionIds(activeGroup && activeGroup.snapshotId === snapId ? activeGroup : null, snap?.detections ?? []),
    [activeGroup, snapId, snap],
  );
  const visibleDets = useMemo(() => {
    if (!snap) return [];
    return snap.detections.filter((d) => d.score >= conf);
  }, [snap, conf]);
  const planStage = useMemo(() => {
    if (!card || !snap) return null;
    const day = snap.captured_at.slice(0, 10);
    return card.stages.find((stage) => stage.date_from.slice(0, 10) <= day && day <= stage.date_to.slice(0, 10)) ?? null;
  }, [card, snap]);
  const observed = useMemo(() => new Set(
    (snap?.detections ?? []).filter((d) => d.score >= 0.35).map((d) => d.label),
  ), [snap]);
  const requirements = planStage ? card?.stage_requirements?.[String(planStage.id)] ?? [] : [];
  const timelineEvents = useMemo<TimelineEvent[]>(() => {
    if (!card) return [];
    const stageForDate = (value: string) => card.stages.find((stage) => {
      const day = value.slice(0, 10);
      return stage.date_from.slice(0, 10) <= day && day <= stage.date_to.slice(0, 10);
    });
    const snapshotEvents: TimelineEvent[] = card.snapshots.map((item) => {
      const violation = item.detections.filter((d) => d.match === "mismatch").length;
      const review = item.detections.filter((d) => d.match === "review").length;
      const stage = stageForDate(item.captured_at);
      return {
        id: `snapshot-${item.id}`,
        kind: "snapshot",
        date: item.captured_at,
        title: "Снимок и анализ",
        body: item.status === "processing" ? "Распознавание выполняется" : item.status === "failed" ? "Распознавание завершилось ошибкой" : `${item.detections.length} объектов · ${violation ? `${violation} проблем` : review ? `${review} вопросов` : "соответствие проверено"}`,
        snapshotId: item.id,
        stageId: stage?.id,
        tone: violation ? "bad" : review ? "warn" : timelineClass(item),
      };
    });
    const warningEvents: TimelineEvent[] = card.warnings.map((warning) => {
      const stage = stageForDate(warning.captured_at ?? "");
      return {
        id: `warning-${warning.id}`,
        kind: warning.severity === "violation" ? "problem" : "question",
        date: warning.captured_at ?? "",
        title: warning.title,
        body: warning.status === "open" ? warning.body : `${warning.body} · ${warning.status === "confirmed" ? "подтверждено" : "отклонено"}`,
        snapshotId: warning.snapshot_id,
        stageId: stage?.id,
        warningId: warning.id,
        tone: warning.severity === "violation" ? "bad" : "warn",
      };
    });
    const manualEvents: TimelineEvent[] = humanEvents.map((event) => ({
      id: `human-${event.id}`, kind: "human", date: event.event_date, title: event.title,
      body: event.body || "Событие добавлено инспектором", stageId: event.stage_id ?? undefined, snapshotId: event.snapshot_id ?? undefined, tone: "human",
    }));
    return [...manualEvents, ...warningEvents, ...snapshotEvents].sort((a, b) => b.date.localeCompare(a.date) || b.id.localeCompare(a.id));
  }, [card, humanEvents]);
  const todayKey = new Date().toISOString().slice(0, 10);

  const warningCountsByStage = useMemo(() => {
    const counts = new Map<number, { problems: number; questions: number }>();
    if (!card) return counts;
    const stageForDate = (value: string) => card.stages.find((stage) => {
      const day = value.slice(0, 10);
      return stage.date_from.slice(0, 10) <= day && day <= stage.date_to.slice(0, 10);
    });
    card.warnings.filter((warning) => warning.status === "open").forEach((warning) => {
      const stage = stageForDate(warning.captured_at ?? "");
      if (!stage) return;
      const current = counts.get(stage.id) ?? { problems: 0, questions: 0 };
      if (warning.severity === "violation") current.problems += 1;
      else current.questions += 1;
      counts.set(stage.id, current);
    });
    return counts;
  }, [card]);

  async function resolveWarning(warningId: number, action: "confirm" | "dismiss" | "reopen") {
    const body = new FormData();
    body.set("action", action);
    await apiFetch(`/api/warnings/${warningId}`, { method: "POST", body });
    load();
  }

  async function toggleStageComplete(stage: Stage) {
    if (!card) return;
    const nextStatus = stage.status === "done" ? "current" : "done";
    try {
      const response = await apiFetch(`/api/objects/${id}/stages`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(card.stages.map((item) => ({
          kind: item.kind, name: item.name, date_from: item.date_from, date_to: item.date_to,
          status: item.id === stage.id ? nextStatus : item.status,
        }))),
      });
      if (!response.ok) throw new Error((await response.json()).detail || "Не удалось обновить этап");
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Не удалось обновить этап");
    }
  }

  async function createHumanEvent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!eventTitle.trim() || eventSaving) return;
    setEventSaving(true);
    setError("");
    try {
      const response = await apiFetch(`/api/objects/${id}/events`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: eventTitle.trim(), body: eventBody.trim(), event_date: eventDate,
          stage_id: eventStageId ? Number(eventStageId) : null,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Не удалось создать событие");
      setHumanEvents((current) => [data, ...current]);
      setEventTitle(""); setEventBody(""); setEventFormOpen(false);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Не удалось создать событие");
    } finally {
      setEventSaving(false);
    }
  }

  async function reviewDetection(detection: Detection, action: "confirm" | "dismiss") {
    setDetectionDecisions((current) => ({ ...current, [detection.id]: action }));
    const related = warnings.find((warning) => warning.status === "open" && (
      warning.body.toLowerCase().includes(detection.label.toLowerCase())
      || warning.title.toLowerCase().includes(equipmentRu(detection.label).toLowerCase())
    ));
    if (related) await resolveWarning(related.id, action);
  }

  async function uploadFile(file: File) {
    const body = new FormData();
    body.set("file", file);
    const res = await apiFetch(`/api/objects/${id}/upload`, { method: "POST", body });
    if (res.ok) load();
  }

  async function startDetect(snapshotId: number) {
    try {
      const body = new FormData();
      body.set("model", model);
      const res = await apiFetch(`/api/snapshots/${snapshotId}/detect`, { method: "POST", body });
      if (!res.ok) throw new Error((await res.json()).detail || "Не удалось запустить распознавание");
      await load();
    } catch (e) { setError(e instanceof Error ? e.message : "Не удалось запустить распознавание"); }
  }

  useEffect(() => {
    if (!card?.snapshots.some((s) => s.status === "processing")) return;
    const timer = window.setInterval(() => { load().catch(() => setError("Refresh failed")); }, 5000);
    return () => window.clearInterval(timer);
  }, [card, load]);

  const theme = useThemeId();

  if (!card) {
    return (
      <main className={`page v-${theme}`}>
        <NavBar wide title="Объект" back={{ href: "/", label: "Объекты" }} />
        <div className="content"><div className="hero skeleton" /></div>
      </main>
    );
  }

  const summary = card.summary;
  const tint = typeTint(card.object.type);
  const location = [card.object.district, card.object.address].filter(Boolean).join(" · ");
  const progressValue = Math.round((summary?.progress ?? 0) * 100);
  const currentStageIndex = Math.max(0, card.stages.findIndex((stage) => stage.status === "current"));
  const stageTrackInset = card.stages.length ? 50 / card.stages.length : 0;
  const stageTrackWidth = card.stages.length > 1 ? 100 - 100 / card.stages.length : 0;
  const stageTrackProgress = card.stages.length > 1 ? (currentStageIndex / (card.stages.length - 1)) * 100 : 0;
  const currentSnapshotIndex = card.snapshots.findIndex((item) => item.id === snapId);
  const setAdjacentSnapshot = (offset: number) => {
    const next = currentSnapshotIndex + offset;
    if (next >= 0 && next < card.snapshots.length) setSnapId(card.snapshots[next].id);
  };

  return (
    <main className={`page v-${theme}`}>
      <NavBar
        wide
        title={card.object.name}
        back={{ href: "/", label: "Объекты" }}
        right={
          <>
            <Link className="mini report-nav-link" href={`/objects/${id}/report`}>Отчёт</Link>
            <label className="btn small" style={{ cursor: "pointer" }}>
              <IconUpload size={16} />
              <span className="hide-sm">Загрузить снимок</span>
              <input
                type="file"
                accept="image/*"
                style={{ display: "none" }}
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) uploadFile(f);
                  e.target.value = "";
                }}
              />
            </label>
          </>
        }
      />

      {error && <div className="toast error" role="alert">{error} <button onClick={() => setError("")} aria-label="Закрыть"><IconClose size={14} /></button></div>}
      <div className="content wide">
      <section className="hero">
        <div className="hero-main">
          <span className="glass-pill solid"><i className={`dot tint-${tint}`} />{card.object.type}</span>
          <h1>{card.object.name}</h1>
          {location && <div className="hero-addr"><IconPin size={15} />{location}</div>}
          {card.object.description && <p className="hero-desc">{card.object.description}</p>}
        </div>
        <div className="hero-stats">
          <div className="stat stat-progress">
            <div className="stat-progress-head"><span className="stat-label">Ход работ</span><span className="stat-value">{progressValue}<small>%</small></span></div>
            <div className="bar" role="progressbar" aria-label="Общий прогресс работ" aria-valuemin={0} aria-valuemax={100} aria-valuenow={progressValue}><i style={{ width: `${progressValue}%` }} /></div>
            <div className="stage-line" aria-label="Этапы работ">
              <span className="stage-line-track" aria-hidden="true" style={{ left: `${stageTrackInset}%`, width: `${stageTrackWidth}%` }}><i style={{ width: `${stageTrackProgress}%` }} /></span>
              {card.stages.map((stage, index) => {
                const stageSnapshot = card.snapshots.find((item) => item.captured_at.slice(0, 10) >= stage.date_from.slice(0, 10) && item.captured_at.slice(0, 10) <= stage.date_to.slice(0, 10));
                const stageAlerts = warningCountsByStage.get(stage.id) ?? { problems: 0, questions: 0 };
                const alertCount = stageAlerts.problems + stageAlerts.questions;
                return <button key={stage.id} type="button" className={`stage-line-step ${stage.status} ${summary?.stage?.name === stage.name ? "current" : ""} ${alertCount ? "has-alert" : ""}`} aria-current={summary?.stage?.name === stage.name ? "step" : undefined} aria-label={`Этап ${index + 1}: ${stage.name}${summary?.stage?.name === stage.name ? ", текущий" : ""}${alertCount ? `, ${stageAlerts.problems} проблем, ${stageAlerts.questions} вопросов` : ""}`} onClick={() => stageSnapshot && setSnapId(stageSnapshot.id)} title={`${index + 1}. ${stage.name}${alertCount ? ` · ${stageAlerts.problems} проблем, ${stageAlerts.questions} вопросов` : ""}`}><i><IconCheck size={11} /></i>{alertCount > 0 && <b className={`stage-line-alert ${stageAlerts.problems ? "problem" : "question"}`}>{alertCount}</b>}<span>{index + 1}</span></button>;
              })}
            </div>
            <span className="stat-note">Текущий этап: <b>{summary?.stage ? summary.stage.name : "не задан"}</b>{summary?.stage ? ` · ${summary.stage.position} из ${summary.stages_total} · до ${shortDate(summary.stage.date_to)}` : ""}</span>
          </div>
          <div className="timeline-summary" aria-label="Проблемы и вопросы по этапам">
            <div className={`timeline-summary-item problem ${(summary?.violations_open ?? 0) > 0 ? "has-open" : ""}`}><span className="timeline-summary-icon"><IconWarning size={15} /></span><span className="timeline-summary-copy"><strong>Проблемы</strong><small>Несоответствие плану или этапу</small></span><b>{summary?.violations_open ?? 0}</b></div>
            <div className={`timeline-summary-item question ${(summary?.reviews_open ?? 0) > 0 ? "has-open" : ""}`}><span className="timeline-summary-icon"><IconQuestion size={15} /></span><span className="timeline-summary-copy"><strong>Вопросы</strong><small>Нужна ручная проверка</small></span><b>{summary?.reviews_open ?? 0}</b></div>
          </div>
        </div>
      </section>
      <section className="desk" id="review-desk" aria-label="Рабочее место инспектора">
        <div className="desk-viewer">
          <div className="stagebar">
            <div className="desk-snap-title">
              <span className="rq-kicker">Снимок {currentSnapshotIndex >= 0 ? `${currentSnapshotIndex + 1} из ${card.snapshots.length}` : ""}</span>
              <strong>{snap ? fmt(snap.captured_at) : "Снимок не выбран"}</strong>
            </div>
            <span style={{ flex: 1 }} />
            <label className="tgl">
              <input type="checkbox" checked={showBoxes} onChange={(e) => setShowBoxes(e.target.checked)} />
              Боксы
            </label>
            <div className="conf">
              Порог
              <input type="range" min={10} max={90} value={conf * 100} style={{ width: 88 }}
                onChange={(e) => setConf(Number(e.target.value) / 100)} aria-label="Порог уверенности" />
              <b className="mono">{conf.toFixed(2)}</b>
            </div>
          </div>
          {snap ? (
            <div className="imgwrap">
              <div className={`canvas ${focusIds.size ? "focused" : ""}`}>
                <img src={`/api/snapshots/${snap.id}/file`} alt={`Снимок ${snap.captured_at}`} />
                {showBoxes && visibleDets.map((d) => {
                  const left = (d.x1 / snap.width) * 100;
                  const top = (d.y1 / snap.height) * 100;
                  const w = ((d.x2 - d.x1) / snap.width) * 100;
                  const h = ((d.y2 - d.y1) / snap.height) * 100;
                  const on = focusIds.has(d.id) || hlBox === `${d.id}`;
                  return (
                    <div key={d.id} className={`box b-${d.match} ${on ? "hl" : ""}`}
                      style={{ left: `${left}%`, top: `${top}%`, width: `${w}%`, height: `${h}%` }}>
                      <span className="tag">{equipmentRu(d.label)} · {d.score.toFixed(2)}</span>
                    </div>
                  );
                })}
                {snap.status === "processing" && <div className="canvas-state">Идёт распознавание…</div>}
              </div>
            </div>
          ) : (
            <div className="empty">Загрузите снимок, чтобы начать анализ</div>
          )}
          <div className="legend">
            <span><i className="lg-ok" />Совпадает с этапом</span>
            <span><i className="lg-review" />Требует проверки</span>
            <span><i className="lg-bad" />Не соответствует</span>
            {snap && <span className="meta">{snap.width}×{snap.height} · {visibleDets.length} объектов</span>}
          </div>
          {card.snapshots.length > 1 && (
            <div className="filmstrip" role="listbox" aria-label="Снимки объекта">
              {card.snapshots.map((s) => (
                <button key={s.id} type="button" role="option" aria-selected={s.id === snapId}
                  className={`film ${timelineClass(s)} ${s.id === snapId ? "on" : ""}`}
                  onClick={() => { setSnapId(s.id); setActiveKey(null); }}>
                  <img src={`/api/snapshots/${s.id}/file`} alt="" loading="lazy" />
                  <span>{fmt(s.captured_at).slice(0, 5)}</span>
                </button>
              ))}
            </div>
          )}
        </div>
        <ReviewQueue groups={signalGroups} activeKey={activeKey} onActivate={activateGroup}
          onResolve={(g, d) => void resolveGroup(g, d)} nextObject={nextObject} />
      </section>
      <section className="plan-fact" aria-label="План и наблюдение по выбранному снимку">
        <div className="plan-fact-heading">
          <div>
            <span className="plan-fact-kicker">ПЛАН / НАБЛЮДЕНИЕ</span>
          </div>
          <div className="plan-fact-side">
            <span className="plan-fact-date">{snap ? fmt(snap.captured_at) : "Снимок не выбран"}</span>
            <span className="plan-current-stage">Текущий этап: <b>{summary?.stage?.name ?? "не задан"}</b></span>
          </div>
        </div>
        <div className="plan-fact-grid">
          <div><span className="plan-fact-label">Этап по плану</span><strong>{planStage?.name ?? "На дату снимка этап не задан"}</strong><small>{planStage ? `${fmt(planStage.date_from)} — ${fmt(planStage.date_to)}` : "Уточните календарный план"}</small></div>
          <div><span className="plan-fact-label">Ожидается техника</span><strong>{requirements.length ? requirements.map((item) => item.name).join(", ") : "Правило не задано"}</strong><small>{requirements.length ? "По методике для этого этапа" : "Добавьте правило для анализа"}</small></div>
          <div><span className="plan-fact-label">Обнаружено на кадре</span><strong>{snap?.status === "processing" ? "Идёт распознавание" : snap?.status === "failed" ? "Ошибка распознавания" : observed.size ? [...observed].map(equipmentRu).join(", ") : "Техника не найдена"}</strong><small>{snap ? `Снимок №${snap.id} · модель CV` : "Загрузите снимок"}</small></div>
          <div><span className="plan-fact-label">Вывод</span><strong>{!snap || snap.status === "new" || snap.status === "processing" || snap.status === "failed" ? "Недостаточно данных" : !planStage ? "Нужна привязка к плану" : !requirements.length ? "Правило не задано" : requirements.some((item) => !item.classes.some((cls) => observed.has(cls))) ? "Требуется проверка" : "На кадре соответствует плану"}</strong><small>{requirements.length && (snap?.status === "detected" || snap?.status === "empty") ? `На кадре не найдено: ${requirements.filter((item) => !item.classes.some((cls) => observed.has(cls))).map((item) => item.name).join(", ") || "все ожидаемые группы найдены"}` : "Вывод касается только видимой части кадра"}</small></div>
        </div>
        <div className="plan-fact-actions">
          <div className="plan-snapshot-nav" aria-label="Навигация по снимкам">
            <button type="button" className="icon-btn" onClick={() => setAdjacentSnapshot(-1)} disabled={currentSnapshotIndex <= 0} aria-label="Предыдущий снимок"><IconChevronLeft size={16} /></button>
            <span>{currentSnapshotIndex >= 0 ? `${currentSnapshotIndex + 1} из ${card.snapshots.length}` : "—"}</span>
            <button type="button" className="icon-btn" onClick={() => setAdjacentSnapshot(1)} disabled={currentSnapshotIndex < 0 || currentSnapshotIndex >= card.snapshots.length - 1} aria-label="Следующий снимок"><IconChevronRight size={16} /></button>
          </div>
          <span style={{ flex: 1 }} />
          <button type="button" className="mini" onClick={() => { setEventFormOpen(true); document.getElementById("plan-pane")?.scrollIntoView({ behavior: "smooth", block: "center" }); }}><IconPlus size={14} /> Добавить событие</button>
          <button type="button" className="mini tinted" onClick={() => document.getElementById("plan-pane")?.scrollIntoView({ behavior: "smooth", block: "center" })}>Открыть план</button>
        </div>
      </section>
      <div className="wrap">
        {/* LEFT: plan + events grouped by stage */}
        <div className="pane plan-pane" id="plan-pane">
          <div className="pane-h timeline-pane-head">
            <div>
              <span>План объекта · единая хронология</span>
              <small>Этапы, снимки, проблемы, вопросы и решения на одной линии</small>
            </div>
            <div className="timeline-head-actions">
              <div className="event-view-toggle" role="tablist" aria-label="Представление хронологии">
                <button type="button" className={eventView === "timeline" ? "on" : ""} onClick={() => setEventView("timeline")}>Диаграмма</button>
                <button type="button" className={eventView === "calendar" ? "on" : ""} onClick={() => setEventView("calendar")}><IconCalendar size={13} /> Календарь</button>
              </div>
              <button type="button" className="mini" onClick={() => setEventFormOpen((open) => !open)}><IconPlus size={13} /> Событие</button>
              <button type="button" className="mini" onClick={() => setEditorOpen(true)}>Редактор</button>
            </div>
          </div>
          <div className="timeline-note">Виды работ — из справочника ЛТЦ. Плановые даты задаёт инспектор в редакторе.</div>
          {eventFormOpen && (
            <form className="event-form" onSubmit={createHumanEvent}>
              <div className="event-form-title"><strong>Новое событие инспектора</strong><span>Подкрепите решение контекстом</span></div>
              <input value={eventTitle} onChange={(event) => setEventTitle(event.target.value)} placeholder="Например: выезд на объект" maxLength={160} aria-label="Название события" required />
              <textarea value={eventBody} onChange={(event) => setEventBody(event.target.value)} placeholder="Что произошло или что нужно проверить?" maxLength={1200} rows={3} aria-label="Описание события" />
              <div className="event-form-row"><label>Дата <input type="date" value={eventDate} onChange={(event) => setEventDate(event.target.value)} /></label><label>Этап <select value={eventStageId} onChange={(event) => setEventStageId(event.target.value)}><option value="">Без этапа</option>{card.stages.map((stage) => <option value={stage.id} key={stage.id}>{stage.name}</option>)}</select></label></div>
              <div className="event-form-actions"><button type="button" className="mini" onClick={() => setEventFormOpen(false)}>Отмена</button><button type="submit" className="mini pri" disabled={eventSaving || !eventTitle.trim()}>{eventSaving ? "Сохраняю…" : "Добавить событие"}</button></div>
            </form>
          )}
          {card.stages.length === 0 && (
            <div className="empty">План не задан. Нажмите «Редактор», чтобы добавить этапы.</div>
          )}
          {eventView === "calendar" ? <EventCalendar events={timelineEvents} onSelectSnapshot={setSnapId} selectedId={snapId} /> : <div className="object-timeline" aria-label="Диаграмма последовательности этапов и событий">
            {card.stages.map((st) => {
              const stageEvents = timelineEvents.filter((event) => event.stageId === st.id);
              const stageProblems = stageEvents.filter((event) => event.kind === "problem").length;
              const stageQuestions = stageEvents.filter((event) => event.kind === "question").length;
              const overdue = st.status !== "done" && st.date_to < todayKey;
              const collapsed = collapsedStages[st.id] ?? false;
              return <section className={`timeline-stage ${st.status} ${overdue ? "overdue" : ""} ${collapsed ? "collapsed" : ""}`} key={st.id}>
                <div className="timeline-stage-axis"><i /></div>
                <div className="timeline-stage-body">
                  <div className="timeline-stage-head">
                    <button type="button" className="timeline-stage-toggle" aria-expanded={!collapsed} onClick={() => setCollapsedStages((current) => ({ ...current, [st.id]: !collapsed }))}>
                      <span className="timeline-stage-kicker">Фаза {card.stages.indexOf(st) + 1}</span><strong>{st.name}</strong><small>{fmt(st.date_from)} – {fmt(st.date_to)} · {KIND_RU[st.kind] ?? st.kind}</small>
                      <span className="timeline-stage-flags">{stageProblems > 0 && <b className="problem">{stageProblems} проблем</b>}{stageQuestions > 0 && <b className="question">{stageQuestions} вопросов</b>}{overdue && <b className="overdue">Просрочен</b>}</span>
                    </button>
                    <button type="button" className={`stage-complete ${st.status === "done" ? "is-done" : ""}`} onClick={() => void toggleStageComplete(st)} aria-label={st.status === "done" ? `Вернуть этап «${st.name}» в работу` : `Отметить этап «${st.name}» завершённым`} aria-pressed={st.status === "done"}>{st.status === "done" ? <IconCheck size={14} /> : <span aria-hidden="true">○</span>}</button>
                  </div>
                  {!collapsed && <div className="timeline-stage-events">
                    {stageEvents.length ? stageEvents.map((event) => <div className={`timeline-event ${event.tone} ${event.kind}`} id={event.warningId ? `warning-${event.warningId}` : undefined} key={event.id}>
                      <span className="timeline-event-node" aria-hidden="true" />
                      <button type="button" className="timeline-event-main" onClick={() => event.snapshotId && setSnapId(event.snapshotId)}><time>{fmt(event.date)}</time><strong>{event.title}</strong><small>{event.body}</small><em>{event.kind === "human" ? "Событие инспектора" : event.kind === "problem" ? "Проблема · несоответствие" : event.kind === "question" ? "Вопрос · нужна ручная проверка" : "Снимок · анализ CV"}</em></button>
                    </div>) : <span className="timeline-empty">Событий пока нет</span>}
                  </div>}
                </div>
              </section>;
            })}
            {timelineEvents.some((event) => !event.stageId) && <section className="timeline-stage unassigned"><div className="timeline-stage-axis"><i /></div><div className="timeline-stage-body"><div className="timeline-stage-head"><strong>Без привязки к этапу</strong></div><div className="timeline-stage-events">{timelineEvents.filter((event) => !event.stageId).map((event) => <div className={`timeline-event ${event.tone} ${event.kind}`} key={event.id}><span className="timeline-event-node" aria-hidden="true" /><button type="button" className="timeline-event-main" onClick={() => event.snapshotId && setSnapId(event.snapshotId)}><time>{fmt(event.date)}</time><strong>{event.title}</strong><small>{event.body}</small></button></div>)}</div></div></section>}
          </div>}

        </div>

        <div className="pane">
          <div className="pane-h det-pane-head">
            <span>Детекции на снимке</span>
            <span className="det-model">{MODEL_LABELS[model] ?? model}</span>
          </div>
          {snap ? (
            <>
              <div className="table-scroll"><table className="det-table">
                <thead>
                  <tr><th>Объект</th><th>Уверенность</th><th>Соответствие этапу</th><th>Действие</th></tr>
                </thead>
                <tbody>
                  {visibleDets.length === 0 ? (
                    <tr>
                      <td colSpan={4}>
                        {snap.status === "new" ? (
                          <span>
                            Снимок не разобран.{" "}
                            <button className="mini pri" onClick={() => startDetect(snap.id)}>
                              Запустить распознавание
                            </button>
                          </span>
                        ) : snap.status === "processing" ? (
                          "Идёт распознавание. Результат появится автоматически."
                        ) : snap.status === "failed" ? (
                          <span>
                            Распознавание завершилось ошибкой. {" "}
                            <button className="mini pri" onClick={() => startDetect(snap.id)}>
                              Повторить
                            </button>
                          </span>
                        ) : (
                          "Ниже порога уверенности объектов нет"
                        )}
                      </td>
                    </tr>
                  ) : (
                    visibleDets.map((d) => {
                      const decision = detectionDecisions[d.id];
                      return <tr key={d.id}>
                        <td><b>{equipmentRu(d.label)}</b> <span className="mono" style={{ color: "var(--ink3)" }}>{d.label} #{d.id}</span></td>
                        <td className="mono">{d.score.toFixed(2)}</td>
                        <td>
                          <span className={`badge ${d.match}`}>
                            {d.match === "ok"
                              ? "этапу соответствует"
                              : d.match === "review"
                                ? "низкая уверенность · проверка"
                                : "не соответствует этапу"}
                          </span>
                        </td>
                         <td>
                           <div className="det-actions">
                             <button className="mini" onClick={() => { setHlBox(`${d.id}`); setActiveKey(null); document.getElementById("review-desk")?.scrollIntoView({ behavior: "smooth", block: "start" }); }}>Показать</button>
                             <button type="button" className={`det-action confirm ${decision === "confirm" ? "selected" : ""}`} onClick={() => void reviewDetection(d, "confirm")} aria-label={`Подтвердить ${equipmentRu(d.label)}`} title="Подтвердить"><IconCheck size={15} /></button>
                             <button type="button" className={`det-action dismiss ${decision === "dismiss" ? "selected" : ""}`} onClick={() => void reviewDetection(d, "dismiss")} aria-label={`Отклонить ${equipmentRu(d.label)}`} title="Отклонить"><IconClose size={15} /></button>
                           </div>
                         </td>
                      </tr>;
                    })
                  )}
                </tbody>
              </table></div>
            </>
          ) : (
            <div className="empty">Выберите снимок на таймлайне</div>
          )}
        </div>

      </div>
      </div>

      {editorOpen && (
        <StagesEditor
          card={card}
          onClose={() => setEditorOpen(false)}
          onSaved={() => { setEditorOpen(false); load(); }}
        />
      )}
    </main>
  );
}

function EventCalendar({
  events, onSelectSnapshot, selectedId,
}: { events: TimelineEvent[]; onSelectSnapshot: (id: number) => void; selectedId: number | null }) {
  const monthKey = events[0]?.date?.slice(0, 7) ?? new Date().toISOString().slice(0, 7);
  const [year, month] = monthKey.split("-").map(Number);
  const firstDay = (new Date(year, month - 1, 1).getDay() + 6) % 7;
  const days = new Date(year, month, 0).getDate();
  const byDay = new Map<string, TimelineEvent[]>();
  events.forEach((event) => {
    const key = event.date.slice(0, 10);
    if (!key) return;
    byDay.set(key, [...(byDay.get(key) ?? []), event]);
  });
  const monthLabel = new Intl.DateTimeFormat("ru-RU", { month: "long", year: "numeric" }).format(new Date(year, month - 1, 1));
  return (
    <div className="event-calendar">
      <div className="calendar-title"><strong>{monthLabel}</strong><span>{events.length} событий</span></div>
      <div className="calendar-weekdays">{["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"].map((day) => <span key={day}>{day}</span>)}</div>
      <div className="calendar-grid">
        {Array.from({ length: firstDay }).map((_, index) => <span className="calendar-empty" key={`empty-${index}`} />)}
        {Array.from({ length: days }, (_, index) => {
          const day = index + 1;
          const key = `${monthKey}-${String(day).padStart(2, "0")}`;
          const dayEvents = byDay.get(key) ?? [];
          const active = dayEvents.some((event) => event.snapshotId === selectedId);
          const dayTone = dayEvents.some((event) => event.kind === "problem") ? "bad" : dayEvents.some((event) => event.kind === "question") ? "warn" : dayEvents.some((event) => event.kind === "human") ? "human" : "ok";
          return <button type="button" key={key} aria-label={`${day}. ${dayEvents.length ? `${dayEvents.length} событий` : "нет событий"}`} className={`calendar-day ${dayEvents.length ? "has-events" : ""} ${active ? "active" : ""}`} onClick={() => dayEvents.find((event) => event.snapshotId)?.snapshotId && onSelectSnapshot(dayEvents.find((event) => event.snapshotId)!.snapshotId!)}><span>{day}</span>{dayEvents.length > 0 && <><b>{dayEvents.length}</b><i className={dayTone} /></>}</button>;
        })}
      </div>
      <div className="calendar-agenda">
        {events.map((event) => <button type="button" key={`agenda-${event.id}`} onClick={() => event.snapshotId && onSelectSnapshot(event.snapshotId)}><span className={`calendar-agenda-dot ${event.tone}`} /><span><b>{fmt(event.date)}</b><strong>{event.title}</strong><small>{event.kind === "problem" ? "Проблема · несоответствие" : event.kind === "question" ? "Вопрос · нужна ручная проверка" : event.kind === "human" ? "Событие инспектора" : "Снимок · анализ CV"}</small></span></button>)}
      </div>
    </div>
  );
}

type EditorStage = {
  kind: string;
  name: string;
  date_from: string;
  date_to: string;
  status: string;
};

function StagesEditor({
  card, onClose, onSaved,
}: { card: Card; onClose: () => void; onSaved: () => void }) {
  const [rows, setRows] = useState<EditorStage[]>(
    card.stages.map(({ kind, name, date_from, date_to, status }) => ({
      kind, name, date_from, date_to, status,
    })),
  );
  const [saving, setSaving] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importNote, setImportNote] = useState("");
  const [importIssues, setImportIssues] = useState<string[]>([]);
  const [editorError, setEditorError] = useState("");
  const dialog = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const previousFocus = document.activeElement as HTMLElement | null;
    dialog.current?.querySelector<HTMLButtonElement>("button")?.focus();
    return () => previousFocus?.focus();
  }, []);

  function dialogKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") { onClose(); return; }
    if (event.key !== "Tab" || !dialog.current) return;
    const focusable = Array.from(dialog.current.querySelectorAll<HTMLElement>(
      "button:not([disabled]), input:not([disabled]), select:not([disabled])",
    ));
    if (!focusable.length) return;
    if (event.shiftKey && document.activeElement === focusable[0]) {
      event.preventDefault(); focusable[focusable.length - 1].focus();
    } else if (!event.shiftKey && document.activeElement === focusable[focusable.length - 1]) {
      event.preventDefault(); focusable[0].focus();
    }
  }

  async function importPlan(file: File) {
    if (file.size > 2 * 1024 * 1024) {
      setEditorError("Файл должен быть не больше 2 МБ");
      return;
    }
    setImporting(true);
    setEditorError("");
    setImportNote("");
    setImportIssues([]);
    try {
      const body = new FormData();
      body.set("file", file);
      const response = await apiFetch(`/api/objects/${card.object.id}/plan/preview`, { method: "POST", body });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Не удалось прочитать план");
      const today = new Date().toISOString().slice(0, 10);
      setRows((data.stages as EditorStage[]).map((stage) => ({
        ...stage, status: stage.date_to < today ? "done" : stage.date_from <= today ? "current" : "future",
      })));
      setImportNote(`Загружено ${data.stages.length} этапов. Проверьте типы работ и даты перед сохранением.`);
      setImportIssues(data.issues ?? []);
    } catch (cause) {
      setEditorError(cause instanceof Error ? cause.message : "Не удалось прочитать план");
    } finally {
      setImporting(false);
    }
  }

  async function save() {
    setSaving(true);
    setEditorError("");
    try {
      const response = await apiFetch(`/api/objects/${card.object.id}/stages`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(rows),
      });
      if (!response.ok) throw new Error((await response.json()).detail || "Не удалось сохранить план");
      onSaved();
    } catch (cause) {
      setEditorError(cause instanceof Error ? cause.message : "Не удалось сохранить план");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="modal-back" onClick={onClose}>
      <div className="modal" ref={dialog} role="dialog" aria-modal="true" aria-labelledby="plan-editor-title"
        onKeyDown={dialogKeyDown} onClick={(e) => e.stopPropagation()}>
        <div className="pane-h" style={{ padding: "0 0 12px" }}>
          <span id="plan-editor-title">Редактор этапов · план объекта</span>
          <button className="mini" onClick={onClose}>Закрыть</button>
        </div>
        <div className="hint" style={{ padding: "0 0 10px" }}>
          Виды работ выбираются из справочника ЛТЦ; плановые даты задаёт
          инспектор. После сохранения предупреждения пересчитываются.
        </div>
        <div className="plan-import">
          <div><strong>Импорт календарного плана</strong><p>CSV или XLSX со столбцами «Этап», «Дата начала», «Дата окончания». Сначала откроется предпросмотр.</p></div>
          <label className="mini pri plan-import-picker" style={{ cursor: importing ? "wait" : "pointer" }}>
            {importing ? "Чтение…" : "Выбрать файл"}
            <input type="file" accept=".csv,.xlsx" disabled={importing} aria-label="Выбрать календарный план CSV или XLSX"
              onChange={(event) => { const file = event.target.files?.[0]; if (file) void importPlan(file); event.target.value = ""; }} />
          </label>
        </div>
        {importNote && <p className="plan-import-ok" role="status">{importNote}</p>}
        {importIssues.length > 0 && <div className="plan-import-issues"><strong>Пропущено строк: {importIssues.length}</strong>{importIssues.slice(0, 3).map((issue) => <p key={issue}>{issue}</p>)}</div>}
        {editorError && <p className="plan-import-error" role="alert">{editorError}</p>}
        {rows.map((st, i) => (
          <div className="stage-row" key={i}>
            <input
              aria-label={`Название этапа ${i + 1}`}
              value={st.name}
              onChange={(e) => setRows(rows.map((r, j) => j === i ? { ...r, name: e.target.value } : r))}
            />
            <select
              aria-label={`Вид работ этапа ${i + 1}`}
              value={st.kind}
              onChange={(e) => setRows(rows.map((r, j) => j === i ? { ...r, kind: e.target.value } : r))}
            >
              {card.stage_kinds.map((k) => (
                <option key={k} value={k}>{KIND_RU[k] ?? k}</option>
              ))}
            </select>
            <input
              type="date"
              aria-label={`Дата начала этапа ${i + 1}`}
              value={st.date_from}
              onChange={(e) => setRows(rows.map((r, j) => j === i ? { ...r, date_from: e.target.value } : r))}
            />
            <input
              type="date"
              aria-label={`Дата окончания этапа ${i + 1}`}
              value={st.date_to}
              onChange={(e) => setRows(rows.map((r, j) => j === i ? { ...r, date_to: e.target.value } : r))}
            />
            <select
              aria-label={`Статус этапа ${i + 1}`}
              value={st.status}
              onChange={(e) => setRows(rows.map((r, j) => j === i ? { ...r, status: e.target.value } : r))}
            >
              <option value="done">завершён</option>
              <option value="current">текущий</option>
              <option value="future">ожидается</option>
            </select>
            <button
              className="mini"
              aria-label={`Удалить этап ${i + 1}`}
              onClick={() => setRows(rows.filter((_, j) => j !== i))}
            >
              ✕
            </button>
          </div>
        ))}
        <div className="warn-act">
          <button
            className="mini"
            onClick={() => setRows([...rows, {
              kind: "other", name: "Новый этап", date_from: card.snapshots[0]?.captured_at ?? "2026-07-01",
              date_to: "2026-12-31", status: "future",
            }])}
          >
            + Этап
          </button>
          <span style={{ flex: 1 }} />
          <button className="mini pri" disabled={saving} onClick={save}>
            {saving ? "Сохранение…" : "Сохранить план"}
          </button>
        </div>
      </div>
    </div>
  );
}
