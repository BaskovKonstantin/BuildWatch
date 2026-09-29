"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { NavBar } from "@/components/NavBar";
import { EventCalendar } from "@/components/EventCalendar";
import { StagesEditor } from "@/components/StagesEditor";
import { ObjectTimelineFeed } from "@/components/ObjectTimelineFeed";
import { IconCalendar, IconClose, IconPlus } from "@/components/Icons";
import { apiFetch } from "@/lib/api";
import { HumanEvent, useObjectCard } from "@/lib/objectCard";
import { TimelineEvent, buildTimeline } from "@/lib/timeline";
import { useThemeId } from "@/lib/themes";

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
  const loadEvents = useCallback(async () => {
    const res = await apiFetch(`/api/objects/${id}/events`);
    if (res.ok) setHumanEvents(await res.json());
  }, [id]);
  useEffect(() => { void loadEvents(); }, [loadEvents]);

  const events = useMemo(() => (card ? buildTimeline(card, humanEvents) : []), [card, humanEvents]);
  const snapshotHref = (snapshotId?: number) => snapshotId ? `/objects/${id}?snapshot=${snapshotId}` : `/objects/${id}`;

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

          {view === "calendar" ? (
            <div className="pane"><EventCalendar events={events} selectedId={null}
              onSelectSnapshot={(snapshotId) => { window.location.href = snapshotHref(snapshotId); }} /></div>
          ) : (
            <ObjectTimelineFeed objectId={id} card={card} humanEvents={humanEvents} wide
              onStagesChanged={() => void load()} onError={(msg) => setError(msg)} />
          )}
        </>}
      </div>
      {editorOpen && card && (
        <StagesEditor card={card} onClose={() => setEditorOpen(false)} onSaved={() => { setEditorOpen(false); void load(); }} />
      )}
    </main>
  );
}
