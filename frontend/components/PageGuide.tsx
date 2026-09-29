"use client";

import { usePathname } from "next/navigation";
import { useCallback, useEffect, useLayoutEffect, useState } from "react";

type Side = "top" | "bottom" | "left" | "right" | "inside";

type Step = {
  target: string;
  index?: number;
  last?: boolean;
  side: Side;
  /** Shift as a fraction of the target's visible width and height. */
  offset?: [number, number];
  title: string;
  text: string;
};

type Guide = { name: string; steps: Step[] };

const SEEN_KEY = "buildwatch_guide_seen";
const CALLOUT_W = 280;
const CALLOUT_H = 118;
const GAP = 10;
const EDGE = 12;
/** Keep callouts clear of the top guide chrome (trigger + bar). */
const TOP_RESERVE = 72;
const BOTTOM_RESERVE = 24;

const HOME: Guide = {
  name: "Портфель объектов",
  steps: [
    { target: ".review-cta", side: "bottom", title: "Очередь разбора",
      text: "Сигналы, которые ждут решения инспектора. Кнопка открывает первый объект сразу в режиме разбора." },
    { target: ".assistant-center-cta", side: "bottom", title: "ИИ-помощник",
      text: "Отвечает по данным всего портфеля: планам, снимкам и открытым сигналам." },
    { target: ".view-controls", side: "bottom", offset: [0.02, 0], title: "Фильтры и вид",
      text: "Тип объекта и переключение между картой и списком. Поиск выше ищет по названию, адресу и этапу." },
    { target: ".map-feed", side: "inside", offset: [0.04, 0.08], title: "Сводка портфеля",
      text: "Сколько объектов в норме, с вопросами и с проблемами. Раскройте строку, чтобы увидеть объекты." },
    { target: ".map-canvas", side: "inside", offset: [0.28, 0.08], title: "Карта Москвы",
      text: "На маркере число открытых сигналов, цвет — статус объекта. Нажмите маркер, чтобы открыть сводку." },
    { target: ".map-details", side: "inside", offset: [0.06, 0.08], title: "Карточка объекта",
      text: "Этап по плану и факт по последнему снимку, прогноз и сравнение нужной техники с увиденной." },
  ],
};

const OBJECT: Guide = {
  name: "Карточка объекта",
  steps: [
    { target: ".oc-status", side: "bottom", title: "Статус по графику",
      text: "Итог сверки снимков с календарным планом и динамика сигналов за 30 дней." },
    { target: ".oc-forecast", side: "bottom", title: "Прогноз",
      text: "Оценка отставания по серии снимков: этап по плану, этап по факту и темп работ." },
    { target: ".oc-stages", side: "bottom", offset: [0.15, 0], title: "Этапы плана",
      text: "Календарный график объекта. Текущий этап выделен, завершённые отмечены галочкой." },
    { target: ".oc-viewer .canvas", side: "inside", offset: [0.04, 0.08], title: "Снимок с распознаванием",
      text: "Рамки YOLO с уверенностью модели. Кнопка «Зоны» размечает опасную зону и склад (R-09, R-10)." },
    { target: ".oc-fact", side: "inside", offset: [0.06, 0.08], title: "План и факт",
      text: "Какая техника нужна этапу, что видно на кадре и вывод о вероятной активности на площадке." },
    { target: ".report-nav-link", side: "bottom", title: "Отчёт и снимки",
      text: "Хронология, отчёт по объекту для печати и загрузка нового снимка камеры." },
  ],
};

const ASSISTANT: Guide = {
  name: "ИИ-помощник",
  steps: [
    { target: ".assistant-head", side: "inside", offset: [0.04, 0.2], title: "Контекст",
      text: "Помощник видит текущий объект: план, снимки, распознавания и сигналы. На главной — весь портфель." },
    { target: ".assistant-question", last: true, side: "left", title: "Вопрос",
      text: "Свободная формулировка или готовая подсказка." },
    { target: ".assistant-answer", last: true, side: "left", title: "Ответ по данным",
      text: "Ссылается на правила, сигналы и даты снимков, отделяет факты от эвристик." },
    { target: ".assistant-compose textarea", side: "top", title: "Вопрос или команда",
      text: "Можно попросить, например, перенести дату этапа — помощник подготовит изменение." },
    { target: ".assistant-disclaimer", side: "top", title: "Контроль человеком",
      text: "План меняется только после подтверждения инспектора." },
  ],
};

const REPORT: Guide = {
  name: "Отчёт по объекту",
  steps: [
    { target: ".report-metrics", side: "inside", offset: [0.04, 0.15], title: "Ключевые цифры",
      text: "Время по плану, последний снимок, открытые проблемы и решения инспектора." },
    { target: ".report-section", index: 0, side: "inside", offset: [0.04, 0.1], title: "Прогноз по графику",
      text: "Отставание, этап по факту и техника, которой не хватает на последних снимках." },
    { target: ".report-section", index: 1, side: "inside", offset: [0.04, 0.1], title: "Динамика",
      text: "По неделям: сколько снимков, какой этап по дате, проблемы и вопросы." },
    { target: ".report-section", index: 2, side: "inside", offset: [0.04, 0.1], title: "Качество распознавания",
      text: "Статистика вердиктов инспектора: сколько выводов модели верны." },
    { target: ".report-print", side: "bottom", title: "Печать и PDF",
      text: "Отчёт готов к печати и выгрузке в PDF для совещания." },
  ],
};

function guideFor(pathname: string, assistantOpen: boolean): Guide | null {
  if (assistantOpen) return ASSISTANT;
  if (pathname === "/") return HOME;
  if (/^\/objects\/[^/]+\/report\/?$/.test(pathname)) return REPORT;
  if (/^\/objects\/[^/]+\/?$/.test(pathname)) return OBJECT;
  return null;
}

type Placed = { step: Step; n: number; rect: DOMRect; x: number; y: number };

function findTarget(step: Step): Element | null {
  const all = document.querySelectorAll(step.target);
  return all[step.last ? all.length - 1 : step.index ?? 0] ?? null;
}

function clamp(v: number, min: number, max: number) {
  return Math.min(Math.max(v, min), max);
}

/** Anchor a callout next to (or on) the target block — never free-float into unrelated regions. */
function anchor(side: Side, rect: DOMRect, ox: number, oy: number): { x: number; y: number } {
  const left = rect.left + ox;
  const top = rect.top + oy;
  switch (side) {
    case "top":
      return { x: left, y: rect.top - GAP - CALLOUT_H + oy };
    case "bottom":
      return { x: left, y: rect.bottom + GAP + oy };
    case "left":
      return { x: rect.left - GAP - CALLOUT_W + ox, y: top };
    case "right":
      return { x: rect.right + GAP + ox, y: top };
    case "inside":
      return { x: left + 16, y: top + 16 };
    default: {
      const never: never = side;
      return never;
    }
  }
}

function sideOrder(preferred: Side): Side[] {
  const rest: Side[] = ["inside", "bottom", "top", "right", "left"].filter((s) => s !== preferred);
  return [preferred, ...rest];
}

function overlaps(a: { x: number; y: number }, b: { x: number; y: number }) {
  return a.x < b.x + CALLOUT_W + 8 && b.x < a.x + CALLOUT_W + 8
    && a.y < b.y + CALLOUT_H + 8 && b.y < a.y + CALLOUT_H + 8;
}

function fitsViewport(p: { x: number; y: number }, vw: number, vh: number) {
  return p.x >= EDGE
    && p.y >= EDGE + TOP_RESERVE
    && p.x + CALLOUT_W <= vw - EDGE
    && p.y + CALLOUT_H <= vh - BOTTOM_RESERVE;
}

/** Keep the card overlapping or touching the highlighted block. */
function nearTarget(p: { x: number; y: number }, rect: DOMRect) {
  const cx = p.x + CALLOUT_W / 2;
  const cy = p.y + CALLOUT_H / 2;
  const pad = 28;
  return cx >= rect.left - pad - CALLOUT_W / 2
    && cx <= rect.right + pad + CALLOUT_W / 2
    && cy >= rect.top - pad - CALLOUT_H / 2
    && cy <= rect.bottom + pad + CALLOUT_H / 2;
}

function score(
  p: { x: number; y: number },
  rect: DOMRect,
  preferred: Side,
  side: Side,
  occupied: { x: number; y: number }[],
  vw: number,
  vh: number,
) {
  let s = 0;
  if (side === preferred) s += 40;
  if (fitsViewport(p, vw, vh)) s += 30;
  if (nearTarget(p, rect)) s += 25;
  if (occupied.some((o) => overlaps(p, o))) s -= 50;
  // Prefer staying close to the badge (top-left of the spot).
  const dx = (p.x + CALLOUT_W / 2) - rect.left;
  const dy = (p.y + CALLOUT_H / 2) - rect.top;
  s -= Math.hypot(dx, dy) / 40;
  return s;
}

function place(steps: Step[]): Placed[] {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const out: Placed[] = [];

  steps.forEach((step, i) => {
    const el = findTarget(step);
    if (!el) return;
    const rect = el.getBoundingClientRect();
    if (rect.width < 4 || rect.height < 4 || rect.bottom < 0 || rect.top > vh) return;

    const visLeft = Math.max(rect.left, 0);
    const visTop = Math.max(rect.top, 0);
    const visW = Math.min(rect.right, vw) - visLeft;
    const visH = Math.min(rect.bottom, vh) - visTop;
    const ox = (step.offset?.[0] ?? 0) * visW;
    const oy = (step.offset?.[1] ?? 0) * visH;
    const occupied = out.map(({ x, y }) => ({ x, y }));

    let best: { x: number; y: number; s: number } | null = null;
    for (const side of sideOrder(step.side)) {
      const raw = anchor(side, rect, ox, oy);
      const clamped = {
        x: clamp(raw.x, EDGE, vw - CALLOUT_W - EDGE),
        y: clamp(raw.y, EDGE + TOP_RESERVE, vh - CALLOUT_H - BOTTOM_RESERVE),
      };
      // Nudge along the free axis if overlapping a prior card, still near this target.
      const candidates = [clamped];
      for (const dy of [0, CALLOUT_H + 10, -(CALLOUT_H + 10), (CALLOUT_H + 10) * 2]) {
        for (const dx of [0, 24, -24, 48, -48]) {
          if (dx === 0 && dy === 0) continue;
          candidates.push({
            x: clamp(clamped.x + dx, EDGE, vw - CALLOUT_W - EDGE),
            y: clamp(clamped.y + dy, EDGE + TOP_RESERVE, vh - CALLOUT_H - BOTTOM_RESERVE),
          });
        }
      }
      for (const p of candidates) {
        const s = score(p, rect, step.side, side, occupied, vw, vh);
        if (!best || s > best.s) best = { ...p, s };
      }
    }

    const pick = best ?? { x: EDGE, y: EDGE, s: 0 };
    out.push({ step, n: i + 1, rect, x: pick.x, y: pick.y });
  });

  return out;
}

export function PageGuide() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [fresh, setFresh] = useState(false);
  const [assistantOpen, setAssistantOpen] = useState(false);
  const [placed, setPlaced] = useState<Placed[]>([]);

  useEffect(() => {
    try { setFresh(!localStorage.getItem(SEEN_KEY)); } catch { setFresh(false); }
  }, []);

  useEffect(() => {
    const sync = () => setAssistantOpen(Boolean(document.querySelector(".assistant-drawer")));
    sync();
    const mo = new MutationObserver(sync);
    mo.observe(document.body, { childList: true, subtree: true });
    return () => mo.disconnect();
  }, []);

  const guide = guideFor(pathname, assistantOpen);

  const relayout = useCallback(() => {
    if (open && guide) setPlaced(place(guide.steps));
  }, [open, guide]);

  useLayoutEffect(() => {
    relayout();
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    window.addEventListener("resize", relayout);
    window.addEventListener("scroll", relayout, true);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("resize", relayout);
      window.removeEventListener("scroll", relayout, true);
      window.removeEventListener("keydown", onKey);
    };
  }, [open, relayout]);

  useEffect(() => { setOpen(false); }, [pathname]);

  if (!guide) return null;

  const toggle = () => {
    setOpen((v) => !v);
    if (fresh) {
      setFresh(false);
      try { localStorage.setItem(SEEN_KEY, "1"); } catch { /* storage unavailable */ }
    }
  };

  return (
    <>
      {open && (
        <div className="guide-layer" role="dialog" aria-modal="true" aria-label={`Гайд: ${guide.name}`}
          onMouseDown={(e) => { if (e.target === e.currentTarget) setOpen(false); }}>
          {placed.map(({ step, n, rect }) => (
            <div key={`h${n}`} className="guide-spot" style={{
              left: rect.left - 4, top: rect.top - 4, width: rect.width + 8, height: rect.height + 8,
            }}><span className="guide-num" style={rect.top < 16 ? { top: 4 } : undefined}>{n}</span></div>
          ))}
          {placed.map(({ step, n, x, y }) => (
            <div key={`c${n}`} className={`guide-callout side-${step.side}`} style={{ left: x, top: y, width: CALLOUT_W }}>
              <b><span className="guide-num inline">{n}</span>{step.title}</b>
              <p>{step.text}</p>
            </div>
          ))}
          <div className="guide-bar">
            <span>Гайд · {guide.name}</span>
            <button type="button" onClick={() => setOpen(false)}>Понятно</button>
          </div>
        </div>
      )}
      <button
        type="button"
        className={`guide-trigger ${fresh ? "fresh" : ""} ${open ? "on" : ""}`}
        onClick={toggle}
        aria-expanded={open}
        aria-label={open ? "Скрыть подсказки" : "Как устроен этот экран"}
      >
        <span className="guide-q" aria-hidden="true">{open ? "×" : "?"}</span>
        {!open && (
          <span className="guide-label">
            {fresh ? "Как устроен этот экран?" : "Гайд"}
          </span>
        )}
      </button>
    </>
  );
}
