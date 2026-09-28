"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { IconArrowUpRight, IconCheck, IconClose, IconQuestion, IconWarning } from "@/components/Icons";
import { equipmentRu } from "@/lib/format";

export type ReviewWarning = {
  id: number;
  snapshot_id: number;
  rule: string;
  title: string;
  body: string;
  why: string;
  status: string;
  severity: string;
  captured_at: string | null;
};

type ReviewDetection = { id: number; label: string; score: number };

export type SignalGroup = {
  key: string;
  snapshotId: number;
  rule: string;
  title: string;
  why: string;
  severity: "violation" | "review";
  date: string;
  items: ReviewWarning[];
  open: ReviewWarning[];
  hits: { label: string; score: number }[];
};

export type Decision = "confirm" | "dismiss" | "reopen";
type Tab = "open" | "done";

const HIT_PATTERNS = [
  /обнаружен ([a-z_ ]+?) \(уверенность ([0-9.]+)\)/gi,
  /([a-z_]+(?: [a-z_]+)?) ([0-9]\.[0-9]+)/gi,
];

function parseHits(text: string): { label: string; score: number }[] {
  for (const pattern of HIT_PATTERNS) {
    const hits = [...text.matchAll(pattern)].map((m) => ({ label: m[1].trim().toLowerCase(), score: Number(m[2]) }));
    if (hits.length) return hits;
  }
  return [];
}

export function groupSignals(warnings: ReviewWarning[]): SignalGroup[] {
  const groups = new Map<string, SignalGroup>();
  for (const w of warnings) {
    const key = `${w.snapshot_id}|${w.rule}|${w.title}`;
    const g = groups.get(key) ?? {
      key, snapshotId: w.snapshot_id, rule: w.rule, title: w.title, why: w.why,
      severity: w.severity === "violation" ? "violation" : "review",
      date: w.captured_at ?? "", items: [], open: [], hits: [],
    };
    g.items.push(w);
    if (w.status === "open") g.open.push(w);
    g.hits.push(...parseHits(w.body));
    groups.set(key, g);
  }
  return [...groups.values()].sort((a, b) =>
    Number(b.open.length > 0) - Number(a.open.length > 0)
    || Number(b.severity === "violation") - Number(a.severity === "violation")
    || b.date.localeCompare(a.date)
    || b.items.length - a.items.length);
}

export function relatedDetectionIds(group: SignalGroup | null, detections: ReviewDetection[]): Set<number> {
  const ids = new Set<number>();
  if (!group) return ids;
  for (const hit of group.hits) {
    const match = detections.find((d) =>
      d.label.toLowerCase() === hit.label && Math.abs(d.score - hit.score) < 0.006 && !ids.has(d.id));
    if (match) ids.add(match.id);
  }
  return ids;
}

function groupSummary(g: SignalGroup): string {
  if (g.hits.length > 1) {
    const labels = [...new Set(g.hits.map((h) => equipmentRu(h.label)))];
    return `${g.hits.length} срабатываний: ${labels.join(", ")}`;
  }
  return g.items[0]?.body ?? "";
}

function fmtDate(value: string): string {
  if (!value) return "—";
  const [y, m, d] = value.slice(0, 10).split("-");
  return `${d}.${m}.${y}`;
}

function isTyping(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  return !!el && (el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName));
}

export function ReviewQueue({
  groups, activeKey, onActivate, onResolve, nextObject,
}: {
  groups: SignalGroup[];
  activeKey: string | null;
  onActivate: (key: string) => void;
  onResolve: (group: SignalGroup, decision: Decision) => void;
  nextObject: { id: number; name: string; open: number } | null;
}) {
  const [tab, setTab] = useState<Tab>("open");
  const listRef = useRef<HTMLDivElement>(null);
  const openGroups = useMemo(() => groups.filter((g) => g.open.length > 0), [groups]);
  const doneGroups = useMemo(() => groups.filter((g) => g.open.length === 0), [groups]);
  const shown = tab === "open" ? openGroups : doneGroups;
  const totalSignals = groups.reduce((s, g) => s + g.items.length, 0);
  const resolvedSignals = groups.reduce((s, g) => s + g.items.length - g.open.length, 0);
  const active = shown.find((g) => g.key === activeKey) ?? null;

  useEffect(() => {
    listRef.current?.querySelector<HTMLElement>(`[data-key="${CSS.escape(activeKey ?? "")}"]`)
      ?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [activeKey]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey || isTyping(e.target)) return;
      const idx = shown.findIndex((g) => g.key === activeKey);
      if (e.code === "KeyJ" || e.key === "ArrowDown") {
        const next = shown[Math.min(shown.length - 1, idx + 1)];
        if (next) { e.preventDefault(); onActivate(next.key); }
      } else if (e.code === "KeyK" || e.key === "ArrowUp") {
        const prev = shown[Math.max(0, idx - 1)];
        if (prev) { e.preventDefault(); onActivate(prev.key); }
      } else if (tab === "open" && active && e.code === "KeyY") {
        e.preventDefault(); onResolve(active, "confirm");
      } else if (tab === "open" && active && e.code === "KeyX") {
        e.preventDefault(); onResolve(active, "dismiss");
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [shown, activeKey, active, tab, onActivate, onResolve]);

  return (
    <aside className="rq" aria-label="Очередь разбора сигналов">
      <header className="rq-head">
        <div className="rq-title">
          <span className="rq-kicker">Разбор сигналов</span>
          <strong>{openGroups.length ? `${openGroups.length} ждут решения` : "Всё разобрано"}</strong>
        </div>
        <div className="rq-progress" aria-label={`Разобрано ${resolvedSignals} из ${totalSignals}`}>
          <span className="rq-progress-bar"><i style={{ width: `${totalSignals ? (resolvedSignals / totalSignals) * 100 : 100}%` }} /></span>
          <small>{resolvedSignals} / {totalSignals}</small>
        </div>
        <div className="rq-tabs" role="tablist">
          <button type="button" role="tab" aria-selected={tab === "open"} className={tab === "open" ? "on" : ""} onClick={() => setTab("open")}>
            К разбору <b>{openGroups.length}</b>
          </button>
          <button type="button" role="tab" aria-selected={tab === "done"} className={tab === "done" ? "on" : ""} onClick={() => setTab("done")}>
            Решённые <b>{doneGroups.length}</b>
          </button>
        </div>
      </header>

      <div className="rq-list" ref={listRef}>
        {shown.length === 0 && (tab === "open" ? (
          <div className="rq-empty">
            <span className="rq-empty-ic"><IconCheck size={22} /></span>
            <strong>Все сигналы по объекту разобраны</strong>
            <p>Решения сохранены и попадут в отчёт.</p>
            {nextObject && (
              <Link className="btn small" href={`/objects/${nextObject.id}?review=1`}>
                Следующий: {nextObject.name} · {nextObject.open} <IconArrowUpRight size={14} />
              </Link>
            )}
          </div>
        ) : <div className="rq-empty"><p>Решённых сигналов пока нет.</p></div>)}

        {shown.map((g) => {
          const isActive = g.key === activeKey;
          const status = g.open.length ? "open" : g.items.every((w) => w.status === "confirmed") ? "confirmed" : "dismissed";
          return (
            <article key={g.key} data-key={g.key}
              className={`rq-item ${g.severity} ${isActive ? "active" : ""} ${status}`}>
              <button type="button" className="rq-item-main" onClick={() => onActivate(g.key)} aria-expanded={isActive}>
                <span className="rq-sev" aria-hidden="true">{g.severity === "violation" ? <IconWarning size={14} /> : <IconQuestion size={14} />}</span>
                <span className="rq-body">
                  <span className="rq-meta">
                    <b>{g.severity === "violation" ? "Проблема" : "Вопрос"}</b>
                    <span>{g.rule}</span>
                    <time>{fmtDate(g.date)}</time>
                    {g.items.length > 1 && <em>×{g.items.length}</em>}
                  </span>
                  <strong>{g.title}</strong>
                  <small>{groupSummary(g)}</small>
                </span>
              </button>
              {isActive && (
                <div className="rq-detail">
                  {g.why && <p className="rq-why"><span>Почему сработало</span>{g.why}</p>}
                  {g.hits.length > 1 && (
                    <div className="rq-hits">
                      {g.hits.map((h, i) => <span key={i}>{equipmentRu(h.label)} <b>{h.score.toFixed(2)}</b></span>)}
                    </div>
                  )}
                  {status === "open" ? (
                    <div className="rq-actions">
                      <button type="button" className="rq-btn confirm" onClick={() => onResolve(g, "confirm")}>
                        <IconCheck size={15} /> Подтвердить <kbd>Y</kbd>
                      </button>
                      <button type="button" className="rq-btn dismiss" onClick={() => onResolve(g, "dismiss")}>
                        <IconClose size={14} /> Ложное <kbd>X</kbd>
                      </button>
                    </div>
                  ) : (
                    <div className="rq-actions">
                      <span className={`rq-verdict ${status}`}>{status === "confirmed" ? "Нарушение подтверждено" : "Отклонено как ложное"}</span>
                      <button type="button" className="mini" onClick={() => onResolve(g, "reopen")}>Вернуть в разбор</button>
                    </div>
                  )}
                </div>
              )}
            </article>
          );
        })}
      </div>
      {shown.length > 0 && tab === "open" && (
        <footer className="rq-foot"><kbd>J</kbd><kbd>K</kbd> навигация · <kbd>Y</kbd> подтвердить · <kbd>X</kbd> ложное</footer>
      )}
    </aside>
  );
}
