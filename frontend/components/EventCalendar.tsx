"use client";

import { TimelineEvent } from "@/lib/timeline";
import { fmt } from "@/lib/objectCard";

export function EventCalendar({
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

