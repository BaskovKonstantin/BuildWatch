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
const GAP = 14;
const BOTTOM_RESERVE = 84;

const HOME: Guide = {
  name: "Портфель объектов",
  steps: [
    { target: ".review-cta", side: "bottom", title: "Очередь разбора",
      text: "Сигналы, которые ждут решения инспектора. Кнопка открывает первый объект сразу в режиме разбора." },
    { target: ".assistant-center-cta", side: "bottom", title: "ИИ-помощник",
      text: "Отвечает по данным всего портфеля: планам, снимкам и открытым сигналам." },
    { target: ".view-controls", side: "bottom", title: "Фильтры и вид",
      text: "Тип объекта и переключение между картой и списком. Поиск выше ищет по названию, адресу и этапу." },
    { target: ".map-feed", side: "right", title: "Сводка портфеля",
      text: "Сколько объектов в норме, с вопросами и с проблемами. Раскройте строку, чтобы увидеть объекты." },
    { target: ".map-canvas", side: "inside", offset: [0.45, 0.45], title: "Карта Москвы",
      text: "На маркере число открытых сигналов, цвет — статус объекта. Нажмите маркер, чтобы открыть сводку." },
    { target: ".map-details", side: "left", title: "Карточка объекта",
      text: "Этап по плану и факт по последнему снимку, прогноз и сравнение нужной техники с увиденной." },
  ],
};

const OBJECT: Guide = {
  name: "Карточка объекта",
  steps: [
    { target: ".oc-status", side: "top", title: "Статус по графику",
      text: "Итог сверки снимков с календарным планом и динамика сигналов за 30 дней." },
    { target: ".oc-forecast", side: "top", title: "Прогноз",
      text: "Оценка отставания по серии снимков: этап по плану, этап по факту и темп работ." },
    { target: ".oc-stages", side: "bottom", offset: [0.3, 0], title: "Этапы плана",
      text: "Календарный график объекта. Текущий этап выделен, завершённые отмечены галочкой." },
    { target: ".oc-viewer .canvas", side: "inside", offset: [0, 0.35], title: "Снимок с распознаванием",
      text: "Рамки YOLO с уверенностью модели. Кнопка «Зоны» размечает опасную зону и склад (R-09, R-10)." },
    { target: ".oc-fact", side: "left", title: "План и факт",
      text: "Какая техника нужна этапу, что видно на кадре и вывод о вероятной активности на площадке." },
    { target: ".report-nav-link", side: "bottom", title: "Отчёт и снимки",
      text: "Хронология, отчёт по объекту для печати и загрузка нового снимка камеры." },
  ],
};

const ASSISTANT: Guide = {
  name: "ИИ-помощник",
  steps: [
    { target: ".assistant-head", side: "left", title: "Контекст",
      text: "Помощник видит текущий объект: план, снимки, распознавания и сигналы. На главной — весь портфель." },
    { target: ".assistant-question", last: true, side: "left", title: "Вопрос",
      text: "Свободная формулировка или готовая подсказка." },
    { target: ".assistant-answer", last: true, side: "left", offset: [0, 0.3], title: "Ответ по данным",
      text: "Ссылается на правила, сигналы и даты снимков, отделяет факты от эвристик." },
    { target: ".assistant-compose textarea", side: "left", title: "Вопрос или команда",
      text: "Можно попросить, например, перенести дату этапа — помощник подготовит изменение." },
    { target: ".assistant-disclaimer", side: "left", offset: [-0.9, -0.2], title: "Контроль человеком",
      text: "План меняется только после подтверждения инспектора." },
  ],
};

const REPORT: Guide = {
  name: "Отчёт по объекту",
  steps: [
    { target: ".report-metrics", side: "right", title: "Ключевые цифры",
      text: "Время по плану, последний снимок, открытые проблемы и решения инспектора." },
    { target: ".report-section", index: 0, side: "right", title: "Прогноз по графику",
      text: "Отставание, этап по факту и техника, которой не хватает на последних снимках." },
    { target: ".report-section", index: 1, side: "left", title: "Динамика",
      text: "По неделям: сколько снимков, какой этап по дате, проблемы и вопросы." },
    { target: ".report-section", index: 2, side: "right", title: "Качество распознавания",
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

function place(steps: Step[]): Placed[] {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const out: Placed[] = [];
  steps.forEach((step, i) => {
    const el = findTarget(step);
    if (!el) return;
    const rect = el.getBoundingClientRect();
    if (rect.width < 4 || rect.height < 4 || rect.bottom < 0 || rect.top > vh) return;
    const h = 110;
    let x = rect.left;
    let y = rect.bottom + GAP;
    switch (step.side) {
      case "top": y = rect.top - GAP - h; break;
      case "bottom": break;
      case "left": x = rect.left - GAP - CALLOUT_W; y = rect.top; break;
      case "right": x = rect.right + GAP; y = rect.top; break;
      case "inside": x = rect.left + 20; y = rect.top + 20; break;
      default: { const never: never = step.side; return never; }
    }
    const visW = Math.min(rect.right, vw) - Math.max(rect.left, 0);
    const visH = Math.min(rect.bottom, vh) - Math.max(rect.top, 0);
    x += (step.offset?.[0] ?? 0) * visW;
    y += (step.offset?.[1] ?? 0) * visH;
    x = Math.min(Math.max(x, 12), vw - CALLOUT_W - 12);
    y = Math.max(y, 12);
    for (const prev of out) {
      const overlapX = x < prev.x + CALLOUT_W && prev.x < x + CALLOUT_W;
      if (overlapX && y < prev.y + h && prev.y < y + h) y = prev.y + h + 8;
    }
    y = Math.min(y, vh - h - BOTTOM_RESERVE);
    out.push({ step, n: i + 1, rect, x, y });
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
      <button type="button" className={`guide-trigger ${fresh ? "fresh" : ""} ${open ? "on" : ""}`}
        onClick={toggle} aria-expanded={open} aria-label={open ? "Скрыть подсказки" : "Как устроен этот экран"}>
        {open ? "×" : "?"}
        {fresh && !open && <span className="guide-hint">Как устроен этот экран?</span>}
      </button>
    </>
  );
}
