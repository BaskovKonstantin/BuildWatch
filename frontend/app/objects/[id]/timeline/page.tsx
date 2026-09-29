"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { NavBar } from "@/components/NavBar";
import { EventCalendar } from "@/components/EventCalendar";
import { StagesEditor } from "@/components/StagesEditor";
import { IconCalendar, IconCheck, IconClose, IconPlus } from "@/components/Icons";
import { apiFetch } from "@/lib/api";
import { HumanEvent, KIND_RU, Stage, fmt, useObjectCard } from "@/lib/objectCard";
import { EVENT_KIND_RU, TimelineEvent, buildTimeline } from "@/lib/timeline";
import { useThemeId } from "@/lib/themes";

type EventGroup = { head: TimelineEvent; count: number };

function groupEvents(events: TimelineEvent[]): EventGroup[] {
  const groups: EventGroup[] = [];
  for (const event of events) {
    const last = groups.at(-1);
    if (last && event.kind !== "human" && last.head.title === event.title && last.head.snapshotId === event.snapshotId) {
      last.count += 1;
    } else {
      groups.push({ head: event, count: 1 });
    }
  }
  return groups;
}

export default function TimelinePage() {
  const { id } = useParams<{ id: string }>();
  const theme = useThemeId();
  const { card, load } = useObjectCard(id);
  const [humanEvents, setHumanEvents] = useState<HumanEvent[]>([]);
  const [view, setView] = useState<"timeline" | "calendar">("timeline");
  const [editorOpen, setEditorOpen] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [stageId, setStageId] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [collapsed, setCollapsed] = useState<Record<number, boolean>>({});

  const loadEvents = useCallback(async () => {
    const res = await apiFetch(`/api/objects/${id}/events`);
    if (res.ok) setHumanEvents(await res.json());
  }, [id]);
  useEffect(() => { void loadEvents(); }, [loadEvents]);

  const events = useMemo(() => (card ? buildTimeline(card, humanEvents) : []), [card, humanEvents]);
  const todayKey = new Date().toISOString().slice(0, 10);
  const snapshotHref = (snapshotId?: number) => snapshotId ? `/objects/${id}?snapshot=${snapshotId}` : `/objects/${id}`;

  async function toggleStage(stage: Stage) {
    if (!card) return;
    const next = stage.status === "done" ? "current" : "done";
    const res = await apiFetch(`/api/objects/${id}/stages`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(card.stages.map((s) => ({
        kind: s.kind, name: s.name, date_from: s.date_from, date_to: s.date_to,
        status: s.id === stage.id ? next : s.status,
      }))),
    });
    if (!res.ok) setError("Не удалось обновить этап");
    await load();
  }

  async function createEvent(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!title.trim() || saving) return;
    setSaving(true); setError("");
    try {
      const res = await apiFetch(`/api/objects/${id}/events`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: title.trim(), body: body.trim(), event_date: date, stage_id: stageId ? Number(stageId) : null }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Не удалось создать событие");
      setHumanEvents((cur) => [data, ...cur]);
      setTitle(""); setBody(""); setFormOpen(false);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Не удалось создать событие");
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className={`page v-${theme}`}>
      <NavBar wide title={card ? `Хронология · ${card.object.name}` : "Хронология"}
        back={{ href: `/objects/${id}`, label: "Объект" }}
        right={card && <>
          <button type="button" className="mini" onClick={() => setFormOpen((v) => !v)}><IconPlus size={13} /> Событие</button>
          <button type="button" className="mini tinted" onClick={() => setEditorOpen(true)}>Редактор плана</button>
        </>} />
      {error && <div className="toast error" role="alert">{error} <button onClick={() => setError("")} aria-label="Закрыть"><IconClose size={14} /></button></div>}
      <div className="content tl-page">
        {!card ? <div className="hero skeleton" /> : <>
          <header className="tl-head">
            <div>
              <span className="oc-kicker">Хронология объекта</span>
              <h1>{card.object.name}</h1>
              <p>Этапы плана, снимки, проблемы и решения инспектора на одной линии. Виды работ из справочника ЛТЦ, даты задаёт инспектор.</p>
            </div>
            <div className="event-view-toggle" role="tablist" aria-label="Представление хронологии">
              <button type="button" className={view === "timeline" ? "on" : ""} onClick={() => setView("timeline")}>Лента</button>
              <button type="button" className={view === "calendar" ? "on" : ""} onClick={() => setView("calendar")}><IconCalendar size={13} /> Календарь</button>
            </div>
          </header>

          {formOpen && (
            <form className="event-form" onSubmit={createEvent}>
              <div className="event-form-title"><strong>Новое событие инспектора</strong><span>Подкрепите решение контекстом</span></div>
              <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Например: выезд на объект" maxLength={160} aria-label="Название события" required />
              <textarea value={body} onChange={(e) => setBody(e.target.value)} placeholder="Что произошло или что нужно проверить?" maxLength={1200} rows={3} aria-label="Описание события" />
              <div className="event-form-row">
                <label>Дата <input type="date" value={date} onChange={(e) => setDate(e.target.value)} /></label>
                <label>Этап <select value={stageId} onChange={(e) => setStageId(e.target.value)}>
                  <option value="">Без этапа</option>
                  {card.stages.map((s) => <option value={s.id} key={s.id}>{s.name}</option>)}
                </select></label>
              </div>
              <div className="event-form-actions">
                <button type="button" className="mini" onClick={() => setFormOpen(false)}>Отмена</button>
                <button type="submit" className="mini pri" disabled={saving || !title.trim()}>{saving ? "Сохраняю…" : "Добавить событие"}</button>
              </div>
            </form>
          )}

          {card.stages.length === 0 && <div className="empty">План не задан. Откройте «Редактор плана», чтобы добавить этапы или импортировать CSV/XLSX.</div>}

          {view === "calendar" ? (
            <div className="pane"><EventCalendar events={events} selectedId={null}
              onSelectSnapshot={(snapshotId) => { window.location.href = snapshotHref(snapshotId); }} /></div>
          ) : (
            <div className="object-timeline tl-wide">
              {card.stages.map((st, index) => {
                const stageEvents = events.filter((e) => e.stageId === st.id);
                const problems = stageEvents.filter((e) => e.kind === "problem" && e.tone !== "done").length;
                const questions = stageEvents.filter((e) => e.kind === "question" && e.tone !== "done").length;
                const overdue = st.status !== "done" && st.date_to < todayKey;
                const isCollapsed = collapsed[st.id] ?? st.status === "future";
                return (
                  <section className={`timeline-stage ${st.status} ${overdue ? "overdue" : ""} ${isCollapsed ? "collapsed" : ""}`} key={st.id}>
                    <div className="timeline-stage-axis"><i /></div>
                    <div className="timeline-stage-body">
                      <div className="timeline-stage-head">
                        <button type="button" className="timeline-stage-toggle" aria-expanded={!isCollapsed}
                          onClick={() => setCollapsed((c) => ({ ...c, [st.id]: !isCollapsed }))}>
                          <span className="timeline-stage-kicker">Фаза {index + 1}</span>
                          <strong>{st.name}</strong>
                          <small>{fmt(st.date_from)} – {fmt(st.date_to)} · {KIND_RU[st.kind] ?? st.kind}</small>
                          <span className="timeline-stage-flags">
                            {problems > 0 && <b className="problem">{problems} проблем</b>}
                            {questions > 0 && <b className="question">{questions} вопросов</b>}
                            {overdue && <b className="overdue">Просрочен</b>}
                          </span>
                        </button>
                        <button type="button" className={`stage-complete ${st.status === "done" ? "is-done" : ""}`}
                          onClick={() => void toggleStage(st)} aria-pressed={st.status === "done"}
                          aria-label={st.status === "done" ? `Вернуть этап «${st.name}» в работу` : `Отметить этап «${st.name}» завершённым`}>
                          {st.status === "done" ? <IconCheck size={14} /> : <span aria-hidden="true">○</span>}
                        </button>
                      </div>
                      {!isCollapsed && (
                        <div className="timeline-stage-events">
                          {stageEvents.length ? groupEvents(stageEvents).map(({ head, count }) => (
                            <div className={`timeline-event ${head.tone} ${head.kind}`} key={head.id}>
                              <span className="timeline-event-node" aria-hidden="true" />
                              <Link className="timeline-event-main" href={snapshotHref(head.snapshotId)}>
                                <time>{fmt(head.date)}</time>
                                <strong>{head.title}{count > 1 && <em className="tl-count">×{count}</em>}</strong>
                                <small>{head.body}</small>
                                <em>{EVENT_KIND_RU[head.kind]}</em>
                              </Link>
                            </div>
                          )) : <span className="timeline-empty">Событий пока нет</span>}
                        </div>
                      )}
                    </div>
                  </section>
                );
              })}
            </div>
          )}
        </>}
      </div>
      {editorOpen && card && (
        <StagesEditor card={card} onClose={() => setEditorOpen(false)} onSaved={() => { setEditorOpen(false); void load(); }} />
      )}
    </main>
  );
}
