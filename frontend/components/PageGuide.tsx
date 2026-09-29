"use client";

import { usePathname } from "next/navigation";
import { useCallback, useEffect, useLayoutEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";

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
/** Space for the fixed «Понятно» bar at the bottom of the viewport. */
const BOTTOM_RESERVE = 64;

const HOME_COMMON: Step[] = [
  { target: ".review-cta", side: "left", offset: [0, 0.15], title: "Очередь разбора",
    text: "Сигналы, которые ждут решения инспектора. Кнопка открывает первый объект сразу в режиме разбора." },
  { target: ".assistant-center-cta", side: "left", offset: [0, 0.15], title: "ИИ-помощник",
    text: "Отвечает по данным всего портфеля: планам, снимкам и открытым сигналам." },
];

const HOME_MAP: Step[] = [
  { target: ".view-controls", side: "left", offset: [0, 0.05], title: "Фильтры и вид",
    text: "Тип объекта и переключение между картой и списком. Поиск выше ищет по названию, адресу и этапу." },
  { target: ".map-feed", side: "left", offset: [0, 0.06], title: "Сводка портфеля",
    text: "Сколько объектов в норме, с вопросами и с проблемами. Раскройте строку, чтобы увидеть объекты." },
  { target: ".map-canvas", side: "top", offset: [0.22, 0], title: "Карта Москвы",
    text: "На маркере число открытых сигналов, цвет — статус объекта. Нажмите маркер, чтобы открыть сводку." },
  { target: ".map-details", side: "right", offset: [0, 0.06], title: "Карточка объекта",
    text: "Этап по плану и факт по последнему снимку, прогноз и сравнение нужной техники с увиденной." },
];

const HOME_LIST: Step[] = [
  { target: ".home-widgets", side: "left", offset: [0, 0.08], title: "Сводка портфеля",
    text: "Объекты в мониторинге, открытые проблемы и вопросы на проверку. Мини-график показывает, где риски выше." },
  { target: ".home-toolbar", side: "left", offset: [0, 0.06], title: "Поиск и фильтр",
    text: "Поиск по названию, адресу и этапу. Вкладки «С проблемами» и «Без проблем» сужают список." },
  { target: ".view-controls", side: "left", offset: [0, 0.05], title: "Тип и представление",
    text: "Чипы — тип объекта. Переключатель «Карта / Список» возвращает к карте Москвы с маркерами." },
  { target: ".home-attention", side: "left", offset: [0, 0.1], title: "Стоит проверить",
    text: "Крупные карточки объектов с наибольшим числом проблем и вопросов — быстрый вход без поиска." },
  { target: ".home-project-grid", side: "left", offset: [0, 0.06], title: "Карточки объектов",
    text: "Этап по плану, прогресс, последний снимок и счётчики сигналов. Клик открывает карточку объекта." },
];

function homeGuide(portfolioView: "map" | "list"): Guide {
  return {
    name: "Портфель объектов",
    steps: [...HOME_COMMON, ...(portfolioView === "list" ? HOME_LIST : HOME_MAP)],
  };
}

const OBJECT: Guide = {
  name: "Карточка объекта",
  steps: [
    { target: ".oc-status", side: "left", offset: [0, 0.08], title: "Статус по графику",
      text: "Итог сверки снимков с календарным планом и динамика сигналов за 30 дней." },
    { target: ".oc-forecast", side: "left", offset: [0, 0.08], title: "Прогноз",
      text: "Оценка отставания по серии снимков: этап по плану, этап по факту и темп работ." },
    { target: ".oc-stages", side: "left", offset: [0, 0.12], title: "Этапы плана",
      text: "Календарный график объекта. Текущий этап выделен, завершённые отмечены галочкой." },
    { target: ".oc-viewer", side: "left", offset: [0, 0.1], title: "Снимок с распознаванием",
      text: "Рамки YOLO с уверенностью модели. Кнопка «Зоны» размечает опасную зону и склад (R-09, R-10)." },
    { target: ".oc-fact", side: "right", offset: [0, 0.08], title: "План и факт",
      text: "Какая техника нужна этапу, что видно на кадре и вывод о вероятной активности на площадке." },
    { target: ".chronology-nav-link", side: "top", title: "Хронология",
      text: "Прокрутка к ленте этапов, снимков и сигналов внизу страницы. Там же откроется гайд по хронологии." },
    { target: ".report-nav-link", side: "top", title: "Отчёт",
      text: "Отчёт по объекту для печати и выгрузки в PDF." },
  ],
};

/** Карточка объекта с якорем #chronology — пояснения у блока ленты, а не «где-то на странице». */
const CHRONOLOGY_ON_OBJECT: Guide = {
  name: "Хронология на карточке",
  steps: [
    { target: ".oc-timeline-head", side: "left", offset: [0, 0.1], title: "Блок хронологии",
      text: "Здесь собраны этапы плана, снимки камеры, проблемы, вопросы и записи инспектора на одной линии." },
    { target: ".object-timeline", side: "left", offset: [0, 0.05], title: "Лента по фазам",
      text: "Раскройте фазу — увидите события по дате. Клик по снимку открывает кадр; цвет узла: проблема, вопрос или действие человека." },
    { target: ".timeline-editor-link", side: "bottom", title: "Календарь и редактор",
      text: "Отдельная страница: вид «календарь», добавление события инспектора и правка этапов плана (CSV/XLSX)." },
  ],
};

const TIMELINE: Guide = {
  name: "Хронология объекта",
  steps: [
    { target: ".tl-head", side: "bottom", title: "Хронология объекта",
      text: "На одной линии: этапы плана, снимки камеры, проблемы, вопросы и записи инспектора." },
    { target: ".event-view-toggle", side: "bottom", title: "Лента и календарь",
      text: "Лента — события по фазам плана. Календарь — те же события по датам." },
    { target: ".object-timeline", side: "inside", offset: [0.04, 0.04], title: "Фазы и события",
      text: "Раскройте этап, чтобы увидеть снимки и сигналы. Клик по событию открывает кадр на карточке объекта." },
    { target: ".tl-add-event", side: "bottom", title: "Событие инспектора",
      text: "Ручная запись: выезд, решение, комментарий к этапу. Попадает в ленту рядом со снимками." },
    { target: ".tl-plan-editor", side: "bottom", title: "Редактор плана",
      text: "Добавление и правка этапов, импорт CSV/XLSX. План меняется только после вашего подтверждения." },
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
    { target: ".report-metrics", side: "left", offset: [0, 0.12], title: "Ключевые цифры",
      text: "Время по плану, последний снимок, открытые проблемы и решения инспектора." },
    { target: ".report-section", index: 0, side: "left", offset: [0, 0.08], title: "Прогноз по графику",
      text: "Отставание, этап по факту и техника, которой не хватает на последних снимках." },
    { target: ".report-section", index: 1, side: "left", offset: [0, 0.08], title: "Динамика",
      text: "По неделям: сколько снимков, какой этап по дате, проблемы и вопросы." },
    { target: ".report-section", index: 2, side: "left", offset: [0, 0.08], title: "Качество распознавания",
      text: "Статистика вердиктов инспектора: сколько выводов модели верны." },
    { target: ".report-print", side: "left", title: "Печать и PDF",
      text: "Отчёт готов к печати и выгрузке в PDF для совещания." },
  ],
};

function guideFor(
  pathname: string,
  assistantOpen: boolean,
  hash: string,
  portfolioView: "map" | "list",
): Guide | null {
  if (assistantOpen) return ASSISTANT;
  if (pathname === "/") return homeGuide(portfolioView);
  if (/^\/objects\/[^/]+\/report\/?$/.test(pathname)) return REPORT;
  if (/^\/objects\/[^/]+\/timeline\/?$/.test(pathname)) return TIMELINE;
  if (/^\/objects\/[^/]+\/?$/.test(pathname)) {
    if (hash === "#chronology") return CHRONOLOGY_ON_OBJECT;
    return OBJECT;
  }
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

/** Pin the callout to the configured side of its target — stay next to that block. */
function anchor(side: Side, rect: DOMRect, ox: number, oy: number): { x: number; y: number } {
  const cx = rect.left + (rect.width - CALLOUT_W) / 2;
  switch (side) {
    case "top":
      return { x: cx + ox, y: rect.top - GAP - CALLOUT_H };
    case "bottom":
      return { x: cx + ox, y: rect.bottom + GAP };
    case "left":
      return { x: rect.left - GAP - CALLOUT_W, y: rect.top + oy };
    case "right":
      return { x: rect.right + GAP, y: rect.top + oy };
    case "inside":
      return { x: rect.left + 14 + ox, y: rect.top + 14 + oy };
    default: {
      const never: never = side;
      return never;
    }
  }
}

function overlaps(a: { x: number; y: number }, b: { x: number; y: number }) {
  return a.x < b.x + CALLOUT_W + 8 && b.x < a.x + CALLOUT_W + 8
    && a.y < b.y + CALLOUT_H + 8 && b.y < a.y + CALLOUT_H + 8;
}

function overlapsRect(x: number, y: number, r: DOMRect, pad = 8) {
  return x < r.right + pad && x + CALLOUT_W > r.left - pad
    && y < r.bottom + pad && y + CALLOUT_H > r.top - pad;
}

function nudgeFromBar(x: number, y: number, bar: DOMRect | null, vh: number) {
  if (!bar) return { x, y };
  let nx = x;
  let ny = y;
  for (let i = 0; i < 10 && overlapsRect(nx, ny, bar, 6); i++) {
    if (bar.bottom + GAP + CALLOUT_H <= vh - BOTTOM_RESERVE) {
      ny = bar.bottom + GAP;
    } else if (bar.top - GAP - CALLOUT_H >= EDGE) {
      ny = bar.top - GAP - CALLOUT_H;
    } else {
      nx = bar.left - GAP - CALLOUT_W;
      if (nx < EDGE) nx = bar.right + GAP;
    }
  }
  return { x: nx, y: ny };
}

function place(steps: Step[]): Placed[] {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const bar = document.querySelector(".guide-bar")?.getBoundingClientRect() ?? null;
  const out: Placed[] = [];

  steps.forEach((step, i) => {
    const el = findTarget(step);
    if (!el) return;
    const rect = el.getBoundingClientRect();
    if (rect.width < 4 || rect.height < 4 || rect.bottom < 0 || rect.top > vh) return;

    const visW = Math.min(rect.right, vw) - Math.max(rect.left, 0);
    const visH = Math.min(rect.bottom, vh) - Math.max(rect.top, 0);
    const ox = (step.offset?.[0] ?? 0) * visW;
    const oy = (step.offset?.[1] ?? 0) * visH;
    const raw = anchor(step.side, rect, ox, oy);
    let x = raw.x;
    let y = raw.y;
    // Left gutter: keep callouts in the margin, not over the block.
    if (step.side === "left" && x < EDGE) x = EDGE;
    if (step.side === "right" && x + CALLOUT_W > vw - EDGE) x = vw - CALLOUT_W - EDGE;
    x = clamp(x, EDGE, vw - CALLOUT_W - EDGE);
    y = clamp(y, EDGE, vh - CALLOUT_H - BOTTOM_RESERVE);

    // Resolve overlaps by sliding along the free axis, staying on the chosen side.
    for (let attempt = 0; attempt < 16; attempt++) {
      const hit = out.find((prev) => overlaps({ x, y }, prev));
      if (!hit) break;
      if (step.side === "bottom" || step.side === "top") {
        const shifted = clamp(
          hit.x + (x >= hit.x ? CALLOUT_W + 10 : -(CALLOUT_W + 10)),
          EDGE,
          vw - CALLOUT_W - EDGE,
        );
        if (!overlaps({ x: shifted, y }, hit)) x = shifted;
        else y = clamp(hit.y + CALLOUT_H + 12, EDGE, vh - CALLOUT_H - BOTTOM_RESERVE);
      } else {
        y = clamp(hit.y + CALLOUT_H + 10, EDGE, vh - CALLOUT_H - BOTTOM_RESERVE);
      }
    }

    ({ x, y } = nudgeFromBar(x, y, bar, vh));
    x = clamp(x, EDGE, vw - CALLOUT_W - EDGE);
    y = clamp(y, EDGE, vh - CALLOUT_H - BOTTOM_RESERVE);

    out.push({ step, n: i + 1, rect, x, y });
  });

  return out;
}

export function PageGuide() {
  const pathname = usePathname();
  const [navAnchor, setNavAnchor] = useState<HTMLElement | null>(null);
  const [hash, setHash] = useState("");
  const [open, setOpen] = useState(false);
  const [fresh, setFresh] = useState(false);
  const [assistantOpen, setAssistantOpen] = useState(false);
  const [placed, setPlaced] = useState<Placed[]>([]);
  const [portfolioView, setPortfolioView] = useState<"map" | "list">("map");

  useEffect(() => {
    if (pathname !== "/") return;
    const readView = () => {
      const pressed = document.querySelector('.portfolio-switcher button[aria-pressed="true"]');
      setPortfolioView(pressed?.textContent?.trim() === "Список" ? "list" : "map");
    };
    readView();
    const mo = new MutationObserver(readView);
    mo.observe(document.body, { subtree: true, attributes: true, attributeFilter: ["aria-pressed", "class"] });
    window.addEventListener("click", readView, true);
    return () => {
      mo.disconnect();
      window.removeEventListener("click", readView, true);
    };
  }, [pathname]);

  useEffect(() => {
    const syncAnchor = () => setNavAnchor(document.getElementById("nav-guide-anchor"));
    syncAnchor();
    const mo = new MutationObserver(syncAnchor);
    mo.observe(document.body, { childList: true, subtree: true });
    return () => mo.disconnect();
  }, [pathname]);

  useEffect(() => {
    const syncHash = () => setHash(window.location.hash);
    syncHash();
    window.addEventListener("hashchange", syncHash);
    return () => window.removeEventListener("hashchange", syncHash);
  }, [pathname]);

  useEffect(() => {
    if (hash !== "#chronology") return;
    document.getElementById("chronology")?.scrollIntoView({ block: "start", behavior: "smooth" });
  }, [hash, pathname]);

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

  const guide = useMemo(
    () => guideFor(pathname, assistantOpen, hash, portfolioView),
    [pathname, assistantOpen, hash, portfolioView],
  );

  const relayout = useCallback(() => {
    if (open && guide) setPlaced(place(guide.steps));
  }, [open, guide]);

  // Хронология и карточка объекта подгружаются после API — пересчитать якоря гайда.
  useEffect(() => {
    if (!open || !guide) return;
    const mo = new MutationObserver(() => relayout());
    mo.observe(document.body, { childList: true, subtree: true });
    const t = window.setInterval(relayout, 400);
    const stop = window.setTimeout(() => window.clearInterval(t), 4000);
    return () => {
      mo.disconnect();
      window.clearInterval(t);
      window.clearTimeout(stop);
    };
  }, [open, guide, relayout]);

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

  const trigger = (
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
          {fresh ? "Как устроен экран?" : "Гайд"}
        </span>
      )}
    </button>
  );

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
          <div className="guide-bar" id="guide-bar">
            <span>Гайд · {guide.name}</span>
            <button type="button" onClick={() => setOpen(false)}>Понятно</button>
          </div>
        </div>
      )}
      {navAnchor ? createPortal(trigger, navAnchor) : trigger}
    </>
  );
}
