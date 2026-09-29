import { Card, HumanEvent, snapshotTone, stageForDate } from "@/lib/objectCard";

export type TimelineEvent = {
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

export const EVENT_KIND_RU: Record<TimelineEvent["kind"], string> = {
  human: "Событие инспектора",
  problem: "Проблема · несоответствие",
  question: "Вопрос · нужна ручная проверка",
  snapshot: "Снимок · анализ CV",
};

export function buildTimeline(card: Card, humanEvents: HumanEvent[]): TimelineEvent[] {
  const snapshots: TimelineEvent[] = card.snapshots.map((item) => {
    const violation = item.detections.filter((d) => d.match === "mismatch").length;
    const review = item.detections.filter((d) => d.match === "review").length;
    return {
      id: `snapshot-${item.id}`,
      kind: "snapshot",
      date: item.captured_at,
      title: "Снимок и анализ",
      body: item.status === "processing" ? "Распознавание выполняется"
        : item.status === "failed" ? "Распознавание завершилось ошибкой"
          : `${item.detections.length} объектов · ${violation ? `${violation} проблем` : review ? `${review} вопросов` : "соответствие проверено"}`,
      snapshotId: item.id,
      stageId: stageForDate(card.stages, item.captured_at)?.id,
      tone: violation ? "bad" : review ? "warn" : snapshotTone(item),
    };
  });
  const warnings: TimelineEvent[] = card.warnings.map((warning) => ({
    id: `warning-${warning.id}`,
    kind: warning.severity === "violation" ? "problem" : "question",
    date: warning.captured_at ?? "",
    title: warning.title,
    body: warning.status === "open" ? warning.body : `${warning.body} · ${warning.status === "confirmed" ? "подтверждено" : "отклонено"}`,
    snapshotId: warning.snapshot_id,
    stageId: stageForDate(card.stages, warning.captured_at ?? "")?.id,
    warningId: warning.id,
    tone: warning.status !== "open" ? "done" : warning.severity === "violation" ? "bad" : "warn",
  }));
  const manual: TimelineEvent[] = humanEvents.map((event) => ({
    id: `human-${event.id}`, kind: "human", date: event.event_date, title: event.title,
    body: event.body || "Событие добавлено инспектором",
    stageId: event.stage_id ?? undefined, snapshotId: event.snapshot_id ?? undefined, tone: "human",
  }));
  return [...manual, ...warnings, ...snapshots]
    .sort((a, b) => b.date.localeCompare(a.date) || b.id.localeCompare(a.id));
}

export type EventGroup = { head: TimelineEvent; count: number };

export function groupTimelineEvents(events: TimelineEvent[]): EventGroup[] {
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
