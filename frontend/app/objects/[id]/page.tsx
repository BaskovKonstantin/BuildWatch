"use client";

import { KeyboardEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { NavBar } from "@/components/NavBar";
import {
  IconBan, IconCalendar, IconCamera, IconClose, IconPin, IconQuestion, IconUpload, IconWarning,
} from "@/components/Icons";
import { apiFetch } from "@/lib/api";
import { useThemeId } from "@/lib/themes";
import { equipmentRu, longDate, plural, shortDate, typeTint } from "@/lib/format";

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
  counts: { snapshots: number; warnings_open: number; warnings_total: number };
  conf_threshold: number;
};

const MODELS = ["equipment"];
const MODEL_LABELS: Record<string, string> = { equipment: "Equipment v2" };
const KIND_RU: Record<string, string> = {
  ground: "подготовка", excavation: "котлован", frame: "каркас",
  facade: "фасады", roof: "кровля", other: "прочее",
};

function fmt(d: string) {
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
  const [model, setModel] = useState("equipment");
  const [conf, setConf] = useState(0.2);
  const [showBoxes, setShowBoxes] = useState(true);
  const [hlBox, setHlBox] = useState<string | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [showAllSnapshots, setShowAllSnapshots] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    const res = await apiFetch(`/api/objects/${id}`);
    if (!res.ok) return;
    const data: Card = await res.json();
    setCard(data);
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
  useEffect(() => {
    if (deepLinkScrolled.current || !card) return;
    const warningId = Number(new URLSearchParams(window.location.search).get("warning"));
    if (!warningId || !warnings.some((warning) => warning.id === warningId)) return;
    deepLinkScrolled.current = true;
    requestAnimationFrame(() => document.getElementById(`warning-${warningId}`)?.scrollIntoView({ block: "center" }));
  }, [card, warnings]);
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
  const requirements = planStage ? card?.stage_requirements?.[planStage.kind] ?? [] : [];

  async function resolveWarning(warningId: number, action: "confirm" | "dismiss" | "reopen") {
    const body = new FormData();
    body.set("action", action);
    await apiFetch(`/api/warnings/${warningId}`, { method: "POST", body });
    load();
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
  const snapDates = card.snapshots.map((s) => s.captured_at).sort();

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
          <div className="stat">
            <span className="stat-label">Прошло времени по плану</span>
            <span className="stat-value">{Math.round((summary?.progress ?? 0) * 100)}%</span>
            <div className="bar"><i style={{ width: `${(summary?.progress ?? 0) * 100}%` }} /></div>
          </div>
          <div className="stat">
            <span className="stat-label">Текущий этап</span>
            <span className="stat-value sm">{summary?.stage ? summary.stage.name : "не задан"}</span>
            <span className="stat-note">{summary?.stage ? `${summary.stage.position} из ${summary.stages_total} · до ${shortDate(summary.stage.date_to)}` : "откройте редактор этапов"}</span>
          </div>
          <div className="stat">
            <span className="stat-label"><IconWarning size={14} /> Проблемы и риски</span>
            <span className={`stat-value ${summary?.violations_open ? "red" : "green"}`}>{summary?.violations_open ?? 0}</span>
            <span className="stat-note">{summary?.reviews_open ?? 0} требуют внимания</span>
          </div>
          <div className="stat">
            <span className="stat-label"><IconCamera size={14} /> Снимки</span>
            <span className="stat-value">{card.counts.snapshots}</span>
            <span className="stat-note">{summary?.last_snapshot ? `последний ${shortDate(summary.last_snapshot)}` : "загрузите первый"}</span>
          </div>
          <div className="stat">
            <span className="stat-label"><IconCalendar size={14} /> Завершение</span>
            <span className="stat-value sm">{summary?.planned_finish ? longDate(summary.planned_finish) : "—"}</span>
            <span className="stat-note">по плану объекта</span>
          </div>
        </div>
      </section>
      <section className="plan-fact" aria-labelledby="plan-fact-heading">
        <div className="plan-fact-heading">
          <div>
            <span className="plan-fact-kicker">ПЛАН / НАБЛЮДЕНИЕ</span>
            <h2 id="plan-fact-heading">Что можно сказать по выбранному снимку</h2>
          </div>
          <span className="plan-fact-date">{snap ? fmt(snap.captured_at) : "Снимок не выбран"}</span>
        </div>
        <div className="plan-fact-grid">
          <div><span className="plan-fact-label">Этап по плану</span><strong>{planStage?.name ?? "На дату снимка этап не задан"}</strong><small>{planStage ? `${fmt(planStage.date_from)} — ${fmt(planStage.date_to)}` : "Уточните календарный план"}</small></div>
          <div><span className="plan-fact-label">Ожидается техника</span><strong>{requirements.length ? requirements.map((item) => item.name).join(", ") : "Правило не задано"}</strong><small>{requirements.length ? "По методике для этого этапа" : "Добавьте правило для анализа"}</small></div>
          <div><span className="plan-fact-label">Обнаружено на кадре</span><strong>{snap?.status === "processing" ? "Идёт распознавание" : snap?.status === "failed" ? "Ошибка распознавания" : observed.size ? [...observed].map(equipmentRu).join(", ") : "Техника не найдена"}</strong><small>{snap ? `Снимок №${snap.id} · модель CV` : "Загрузите снимок"}</small></div>
          <div><span className="plan-fact-label">Вывод</span><strong>{!snap || snap.status === "new" || snap.status === "processing" || snap.status === "failed" ? "Недостаточно данных" : !planStage ? "Нужна привязка к плану" : !requirements.length ? "Правило не задано" : requirements.some((item) => !item.classes.some((cls) => observed.has(cls))) ? "Требуется проверка" : "На кадре соответствует плану"}</strong><small>{requirements.length && (snap?.status === "detected" || snap?.status === "empty") ? `На кадре не найдено: ${requirements.filter((item) => !item.classes.some((cls) => observed.has(cls))).map((item) => item.name).join(", ") || "все ожидаемые группы найдены"}` : "Вывод касается только видимой части кадра"}</small></div>
        </div>
        <p className="plan-fact-caveat">Камера и зона покрытия для этих снимков не заданы. Отсутствие техники в кадре само по себе не доказывает простой или отставание.</p>
      </section>
      <div className="wrap">
        {/* LEFT: stages + warnings */}
        <div className="pane">
          <div className="pane-h">
            Этапы работ · план объекта
            <button className="mini" onClick={() => setEditorOpen(true)}>
              Редактор
            </button>
          </div>
          <div className="stages-note">
            Виды работ — из справочника ЛТЦ. Плановые даты задаёт инспектор в
            редакторе: справочник ЛТЦ не содержит календаря.
          </div>
          {card.stages.length === 0 && (
            <div className="empty">План не задан. Нажмите «Редактор», чтобы добавить этапы.</div>
          )}
          {card.stages.map((st) => {
            const progress = st.status === "current"
              ? Math.min(100, Math.max(4, (summary?.stage?.name === st.name ? summary.stage.progress : 0) * 100))
              : 0;
            return (
              <div className="stage" key={st.id}>
                <div className="row">
                  <span className="name">{st.name}</span>
                  <span className={`pill ${st.status}`}>
                    {st.status === "done" ? "✓" : st.status === "current" ? "текущий" : "ожидается"}
                  </span>
                </div>
                <div className="sub">
                  {fmt(st.date_from)} – {fmt(st.date_to)} ·{" "}
                  {KIND_RU[st.kind] ?? st.kind}
                </div>
                {st.status === "current" && (
                  <div className="bar"><i style={{ width: `${progress}%` }} /></div>
                )}
              </div>
            );
          })}

          <div className="pane-h" style={{ borderTop: "1px solid var(--line2)" }}>
            Проблемы для проверки
          </div>
          {warnings.length === 0 ? (
            <div className="empty">{snap?.status === "new" || snap?.status === "processing" || snap?.status === "failed" ? "Снимок ещё не оценён" : "Для этого снимка проблем нет"}</div>
          ) : (
            warnings.map((w) => (
              <div
                key={w.id}
                id={`warning-${w.id}`}
                className={`warn-card ${w.severity} ${w.status}`}
                onClick={() => setHlBox(null)}
              >
                <div className="warn-t">
                  <span className="ic" style={{ color: w.severity === "violation" ? "var(--bad)" : "var(--warn)" }}>
                    {w.severity === "violation" ? <IconBan size={17} /> : <IconQuestion size={17} />}
                  </span>
                  <span>{w.title}</span>
                </div>
                <div className="warn-body">{w.body}</div>
                <div className="warn-why">
                  <b>Почему:</b> {w.why.replace(/^Почему:\s*/, "")}
                </div>
                {w.status === "open" ? (
                  <div className="warn-act">
                    {w.severity === "violation" && (
                      <button
                        className="mini pri"
                        onClick={async (e) => {
                          e.stopPropagation();
                          const body = new FormData();
                          body.set("action", "confirm");
                          await apiFetch(`/api/warnings/${w.id}`, { method: "POST", body });
                          load();
                        }}
                      >
                        Подтвердить нарушение
                      </button>
                    )}
                    <button
                      className="mini"
                      onClick={async (e) => {
                        e.stopPropagation();
                        const body = new FormData();
                        body.set("action", "dismiss");
                        await apiFetch(`/api/warnings/${w.id}`, { method: "POST", body });
                        load();
                      }}
                    >
                      Отклонить
                    </button>
                  </div>
                ) : (
                  <div className="warn-act">
                    <span className="chip" style={{ fontSize: 10.5 }}>
                      {w.status === "confirmed" ? "Подтверждено" : "Отклонено"}
                    </span>
                    <button
                      className="mini"
                      onClick={async (e) => {
                        e.stopPropagation();
                        const body = new FormData();
                        body.set("action", "reopen");
                        await apiFetch(`/api/warnings/${w.id}`, { method: "POST", body });
                        load();
                      }}
                    >
                      Вернуть
                    </button>
                  </div>
                )}
                <div className="src">{w.source}</div>
              </div>
            ))
          )}
        </div>

        {/* CENTER: snapshot */}
        <div className="pane">
          <div className="stagebar">
            <div className="seg">
              {MODELS.map((m) => (
                <button
                  key={m}
                  className={model === m ? "on" : ""}
                  onClick={() => setModel(m)}
                >
                  {MODEL_LABELS[m] ?? m}
                </button>
              ))}
            </div>
            <label className="tgl">
              <input
                type="checkbox"
                checked={showBoxes}
                onChange={(e) => setShowBoxes(e.target.checked)}
              />
              Боксы
            </label>
            <div className="conf">
              Порог
              <input
                type="range"
                min={10}
                max={90}
                value={conf * 100}
                style={{ width: 88 }}
                onChange={(e) => setConf(Number(e.target.value) / 100)}
              />
              <b className="mono">{conf.toFixed(2)}</b>
            </div>
          </div>
          {snap ? (
            <>
              <div className="imgwrap">
                <div className="canvas">
                  <img
                    src={`/api/snapshots/${snap.id}/file`}
                    alt={`Снимок ${snap.captured_at}`}
                  />
                  {showBoxes &&
                    visibleDets.map((d) => {
                      const left = (d.x1 / snap.width) * 100;
                      const top = (d.y1 / snap.height) * 100;
                      const w = ((d.x2 - d.x1) / snap.width) * 100;
                      const h = ((d.y2 - d.y1) / snap.height) * 100;
                      const key = `${d.id}`;
                      return (
                        <div
                          key={key}
                          className={`box b-${d.match} ${hlBox === key ? "hl" : ""}`}
                          style={{ left: `${left}%`, top: `${top}%`, width: `${w}%`, height: `${h}%` }}
                        >
                          <span className="tag">
                            {equipmentRu(d.label)} · {d.score.toFixed(2)}
                          </span>
                        </div>
                      );
                    })}
                </div>
              </div>
              <div className="legend">
                <span><i style={{ background: "#30B0C7" }} />Совпадает с этапом</span>
                <span><i style={{ background: "#FF9500" }} />Требует проверки</span>
                <span><i style={{ background: "#FF3B30" }} />Не соответствует</span>
                <span className="meta">
                  {snap.width}×{snap.height} · {fmt(snap.captured_at)} ·{" "}
                  {snap.status === "processing" ? "распознавание…" : snap.status}
                </span>
              </div>
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
                    visibleDets.map((d) => (
                      <tr key={d.id}>
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
                          <button className="mini" onClick={() => setHlBox(`${d.id}`)}>
                            Показать
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table></div>
            </>
          ) : (
            <div className="empty">Выберите снимок на таймлайне</div>
          )}
        </div>

        {/* RIGHT: timeline */}
        <div className="pane">
          <div className="pane-h">
            Хронология
            {snapDates.length > 0 && (
              <span className="pane-h-note">
                {snapDates.length} {plural(snapDates.length, ["снимок", "снимка", "снимков"])}
                {snapDates.length > 1 ? ` · ${shortDate(snapDates[0])} – ${shortDate(snapDates[snapDates.length - 1])}` : ""}
              </span>
            )}
          </div>
          <div className="tl">
            {(card?.snapshots ?? []).slice(0, showAllSnapshots ? undefined : 12).map((s, i) => {
              const cls = timelineClass(s);
              const violation = s.detections.filter((d) => d.match === "mismatch").length;
              const review = s.detections.filter((d) => d.match === "review").length;
              return (
                <div
                  key={s.id}
                  className={`tl-item ${cls} ${s.id === snapId ? "active" : ""}`}
                  style={{ animationDelay: `${i * 0.05}s` }}
                  onClick={() => setSnapId(s.id)}
                >
                  <div>
                    <div className="d">{fmt(s.captured_at)}</div>
                    <div className="s">
                      {s.status === "processing"
                        ? "распознавание…"
                        : s.status === "failed"
                          ? "ошибка распознавания"
                          : s.detections.length === 0
                            ? "не разобран"
                            : `${s.detections.length} объектов`}
                    </div>
                  </div>
                  <span className="n">
                    {violation ? String(violation) : review ? String(review) : s.status === "empty" ? "✓" : s.status === "failed" ? "!" : "—"}
                  </span>
                </div>
              );
            })}
            {!showAllSnapshots && (card?.snapshots.length ?? 0) > 12 && (
              <button className="tl-more" onClick={() => setShowAllSnapshots(true)}>
                Показать все {card!.snapshots.length} ↓
              </button>
            )}
          </div>
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
