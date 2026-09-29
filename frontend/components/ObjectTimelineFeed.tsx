"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { IconCheck } from "@/components/Icons";
import { apiFetch } from "@/lib/api";
import { Card, HumanEvent, KIND_RU, Stage, fmt } from "@/lib/objectCard";
import { EVENT_KIND_RU, TimelineEvent, buildTimeline, groupTimelineEvents } from "@/lib/timeline";

type Props = {
  objectId: string;
  card: Card;
  humanEvents: HumanEvent[];
  className?: string;
  wide?: boolean;
  showCompleteToggle?: boolean;
  onStagesChanged?: () => void;
  onError?: (message: string) => void;
};

export function ObjectTimelineFeed({
  objectId,
  card,
  humanEvents,
  className = "",
  wide = false,
  showCompleteToggle = true,
  onStagesChanged,
  onError,
}: Props) {
  const events = useMemo(() => buildTimeline(card, humanEvents), [card, humanEvents]);
  const todayKey = new Date().toISOString().slice(0, 10);
  const snapshotHref = (snapshotId?: number) =>
    snapshotId ? `/objects/${objectId}?snapshot=${snapshotId}` : `/objects/${objectId}`;

  const [collapsed, setCollapsed] = useState<Record<number, boolean>>({});

  async function toggleStage(stage: Stage) {
    const next = stage.status === "done" ? "current" : "done";
    const res = await apiFetch(`/api/objects/${objectId}/stages`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(
        card.stages.map((s) => ({
          kind: s.kind,
          name: s.name,
          date_from: s.date_from,
          date_to: s.date_to,
          status: s.id === stage.id ? next : s.status,
        })),
      ),
    });
    if (!res.ok) onError?.("Не удалось обновить этап");
    else onStagesChanged?.();
  }

  if (!card.stages.length) {
    return (
      <div className={`empty ${className}`.trim()}>
        План не задан. На странице хронологии можно добавить этапы или импортировать CSV/XLSX.
      </div>
    );
  }

  return (
    <div className={`object-timeline ${wide ? "tl-wide" : ""} ${className}`.trim()}>
      {card.stages.map((st, index) => {
        const stageEvents = events.filter((e) => e.stageId === st.id);
        const problems = stageEvents.filter((e) => e.kind === "problem" && e.tone !== "done").length;
        const questions = stageEvents.filter((e) => e.kind === "question" && e.tone !== "done").length;
        const overdue = st.status !== "done" && st.date_to < todayKey;
        const isCollapsed = collapsed[st.id] ?? st.status === "future";
        return (
          <section className={`timeline-stage ${st.status} ${overdue ? "overdue" : ""} ${isCollapsed ? "collapsed" : ""}`} key={st.id}>
            <div className="timeline-stage-axis">
              <i />
            </div>
            <div className="timeline-stage-body">
              <div className="timeline-stage-head">
                <button
                  type="button"
                  className="timeline-stage-toggle"
                  aria-expanded={!isCollapsed}
                  onClick={() => setCollapsed((c) => ({ ...c, [st.id]: !isCollapsed }))}
                >
                  <span className="timeline-stage-kicker">Фаза {index + 1}</span>
                  <strong>{st.name}</strong>
                  <small>
                    {fmt(st.date_from)} – {fmt(st.date_to)} · {KIND_RU[st.kind] ?? st.kind}
                  </small>
                  <span className="timeline-stage-flags">
                    {problems > 0 && <b className="problem">{problems} проблем</b>}
                    {questions > 0 && <b className="question">{questions} вопросов</b>}
                    {overdue && <b className="overdue">Просрочен</b>}
                  </span>
                </button>
                {showCompleteToggle && (
                  <button
                    type="button"
                    className={`stage-complete ${st.status === "done" ? "is-done" : ""}`}
                    onClick={() => void toggleStage(st)}
                    aria-pressed={st.status === "done"}
                    aria-label={
                      st.status === "done"
                        ? `Вернуть этап «${st.name}» в работу`
                        : `Отметить этап «${st.name}» завершённым`
                    }
                  >
                    {st.status === "done" ? <IconCheck size={14} /> : <span aria-hidden="true">○</span>}
                  </button>
                )}
              </div>
              {!isCollapsed && (
                <div className="timeline-stage-events">
                  {stageEvents.length ? (
                    groupTimelineEvents(stageEvents).map(({ head, count }) => (
                      <div className={`timeline-event ${head.tone} ${head.kind}`} key={head.id}>
                        <span className="timeline-event-node" aria-hidden="true" />
                        <Link className="timeline-event-main" href={snapshotHref(head.snapshotId)}>
                          <time>{fmt(head.date)}</time>
                          <strong>
                            {head.title}
                            {count > 1 && <em className="tl-count">×{count}</em>}
                          </strong>
                          <small>{head.body}</small>
                          <em>{EVENT_KIND_RU[head.kind]}</em>
                        </Link>
                      </div>
                    ))
                  ) : (
                    <span className="timeline-empty">Событий пока нет</span>
                  )}
                </div>
              )}
            </div>
          </section>
        );
      })}
    </div>
  );
}
