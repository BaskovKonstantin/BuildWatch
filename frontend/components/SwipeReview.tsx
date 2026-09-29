"use client";

import { PointerEvent as ReactPointerEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { IconCheck, IconClose } from "@/components/Icons";
import { apiFetch } from "@/lib/api";
import { Card, Detection, Snapshot, fmt, stageForDate } from "@/lib/objectCard";
import { equipmentRu } from "@/lib/format";

type Verdict = "correct" | "wrong";
type Item = { det: Detection; snap: Snapshot };

const CROP_W = 4;
const CROP_H = 3;
const SWIPE_DISTANCE = 110;
const MATCH_RU: Record<Detection["match"], string> = {
  ok: "совпадает с этапом",
  review: "низкая уверенность",
  mismatch: "не соответствует этапу",
};

export function reviewItems(card: Card, minScore: number): Item[] {
  const priority = { mismatch: 0, review: 1, ok: 2 } as const;
  return card.snapshots
    .flatMap((snap) => snap.detections.map((det) => ({ det, snap })))
    .filter(({ det }) => det.score >= minScore && !det.verdict)
    .sort((a, b) => priority[a.det.match] - priority[b.det.match] || a.det.score - b.det.score);
}

/** Zoomed crop of one box, positioned in percentages so it scales with the card. */
function Crop({ det, snap }: Item) {
  const bw = det.x2 - det.x1;
  const bh = det.y2 - det.y1;
  const cover = Math.max(CROP_W / snap.width, CROP_H / snap.height);
  const scale = Math.max(cover, Math.min((0.55 * CROP_W) / bw, (0.55 * CROP_H) / bh, cover * 6));
  const cx = (det.x1 + det.x2) / 2;
  const cy = (det.y1 + det.y2) / 2;
  const imgW = (snap.width * scale) / CROP_W * 100;
  const left = 50 - (cx * scale) / CROP_W * 100;
  const top = 50 - (cy * scale) / CROP_H * 100;
  const box = {
    left: `${50 - (bw / 2) * scale / CROP_W * 100}%`,
    top: `${50 - (bh / 2) * scale / CROP_H * 100}%`,
    width: `${bw * scale / CROP_W * 100}%`,
    height: `${bh * scale / CROP_H * 100}%`,
  };
  return (
    <div className="sw-crop">
      <img src={`/api/snapshots/${snap.id}/file`} alt="" draggable={false}
        style={{ width: `${imgW}%`, left: `${left}%`, top: `${top}%` }} />
      <i className={`sw-crop-box ${det.match}`} style={box} />
    </div>
  );
}

function Context({ det, snap }: Item) {
  return (
    <div className="sw-context">
      <img src={`/api/snapshots/${snap.id}/file`} alt="" draggable={false} />
      <i style={{
        left: `${(det.x1 / snap.width) * 100}%`, top: `${(det.y1 / snap.height) * 100}%`,
        width: `${((det.x2 - det.x1) / snap.width) * 100}%`, height: `${((det.y2 - det.y1) / snap.height) * 100}%`,
      }} />
    </div>
  );
}

export function SwipeReview({ card, minScore, onClose, onChanged }: {
  card: Card;
  minScore: number;
  onClose: () => void;
  onChanged: () => void;
}) {
  const initial = useMemo(() => reviewItems(card, minScore), []); // eslint-disable-line react-hooks/exhaustive-deps
  const [index, setIndex] = useState(0);
  const [history, setHistory] = useState<{ item: Item; verdict: Verdict }[]>([]);
  const [drag, setDrag] = useState({ x: 0, y: 0, active: false });
  const [leaving, setLeaving] = useState<Verdict | null>(null);
  const start = useRef<{ x: number; y: number } | null>(null);
  const current = initial[index];
  const next = initial[index + 1];

  const send = useCallback((det: Detection, verdict: Verdict | "") => {
    const body = new FormData();
    body.set("verdict", verdict);
    return apiFetch(`/api/detections/${det.id}/verdict`, { method: "POST", body }).then(onChanged);
  }, [onChanged]);

  const decide = useCallback((verdict: Verdict) => {
    if (!current || leaving) return;
    setLeaving(verdict);
    setHistory((h) => [...h, { item: current, verdict }]);
    void send(current.det, verdict);
    window.setTimeout(() => {
      setLeaving(null);
      setDrag({ x: 0, y: 0, active: false });
      setIndex((i) => i + 1);
    }, 260);
  }, [current, leaving, send]);

  const undo = useCallback(() => {
    const last = history.at(-1);
    if (!last || leaving) return;
    setHistory((h) => h.slice(0, -1));
    setIndex((i) => Math.max(0, i - 1));
    void send(last.item.det, "");
  }, [history, leaving, send]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      else if (e.key === "ArrowRight") decide("correct");
      else if (e.key === "ArrowLeft") decide("wrong");
      else if (e.code === "KeyZ" || e.key === "Backspace") undo();
    };
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => { window.removeEventListener("keydown", onKey); document.body.style.overflow = ""; };
  }, [decide, undo, onClose]);

  const onDown = (e: ReactPointerEvent<HTMLDivElement>) => {
    if (leaving) return;
    if (e.currentTarget.hasPointerCapture?.(e.pointerId) === false) {
      try { e.currentTarget.setPointerCapture(e.pointerId); } catch { /* pointer already released */ }
    }
    start.current = { x: e.clientX, y: e.clientY };
    setDrag({ x: 0, y: 0, active: true });
  };
  const onMove = (e: ReactPointerEvent<HTMLDivElement>) => {
    if (!start.current) return;
    setDrag({ x: e.clientX - start.current.x, y: (e.clientY - start.current.y) * 0.4, active: true });
  };
  const onUp = () => {
    if (!start.current) return;
    start.current = null;
    if (drag.x > SWIPE_DISTANCE) decide("correct");
    else if (drag.x < -SWIPE_DISTANCE) decide("wrong");
    else setDrag({ x: 0, y: 0, active: false });
  };

  const dx = leaving === "correct" ? 700 : leaving === "wrong" ? -700 : drag.x;
  const strength = Math.min(1, Math.abs(dx) / SWIPE_DISTANCE);
  const correct = history.filter((h) => h.verdict === "correct").length;
  const wrong = history.length - correct;
  const total = initial.length;

  return (
    <div className="sw-back" role="dialog" aria-modal="true" aria-label="Проверка распознавания">
      <header className="sw-head">
        <div>
          <span className="sw-kicker">Проверка распознавания</span>
          <strong>{card.object.name}</strong>
        </div>
        <div className="sw-count" aria-live="polite">{Math.min(index + 1, total)} / {total}</div>
        <button type="button" className="sw-close" onClick={onClose} aria-label="Закрыть"><IconClose size={18} /></button>
      </header>
      <div className="sw-progress"><i style={{ width: `${total ? (index / total) * 100 : 100}%` }} /></div>

      <div className="sw-stage">
        {current ? (
          <>
            {next && (
              <div className="sw-card under" aria-hidden="true">
                <Crop {...next} />
              </div>
            )}
            <div
              key={current.det.id}
              className={`sw-card ${drag.active ? "dragging" : ""}`}
              style={{ transform: `translate(${dx}px, ${drag.y}px) rotate(${dx / 18}deg)`, opacity: leaving ? 0 : 1 }}
              onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onPointerCancel={onUp}
            >
              <span className="sw-stamp yes" style={{ opacity: dx > 0 ? strength : 0 }}>Верно</span>
              <span className="sw-stamp no" style={{ opacity: dx < 0 ? strength : 0 }}>Ошибка</span>
              <Crop {...current} />
              <div className="sw-info">
                <div className="sw-question">Модель видит здесь</div>
                <h2>{equipmentRu(current.det.label)}</h2>
                <div className="sw-meta">
                  <span className="sw-score">
                    <i style={{ width: `${current.det.score * 100}%` }} />
                    <b>{Math.round(current.det.score * 100)}%</b>
                  </span>
                  <span className={`sw-match ${current.det.match}`}>{MATCH_RU[current.det.match]}</span>
                </div>
                <div className="sw-foot">
                  <Context {...current} />
                  <span>
                    Снимок {fmt(current.snap.captured_at)}
                    <small>{stageForDate(card.stages, current.snap.captured_at)?.name ?? "этап не задан"}</small>
                  </span>
                </div>
              </div>
            </div>
          </>
        ) : (
          <div className="sw-done">
            <span className="sw-done-ic"><IconCheck size={28} /></span>
            <h2>{total ? "Все детекции проверены" : "Проверять нечего"}</h2>
            <p>{total
              ? `Верно: ${correct} · ошибок модели: ${wrong}. Предупреждения по ошибочным детекциям сняты автоматически.`
              : "Все детекции этого объекта уже размечены инспектором."}</p>
            <button type="button" className="btn" onClick={onClose}>Вернуться к объекту</button>
          </div>
        )}
      </div>

      {current && (
        <footer className="sw-actions">
          <button type="button" className="sw-btn no" onClick={() => decide("wrong")} aria-label="Ошибка распознавания">
            <IconClose size={26} />
          </button>
          <button type="button" className="sw-undo" onClick={undo} disabled={!history.length}>Отменить</button>
          <button type="button" className="sw-btn yes" onClick={() => decide("correct")} aria-label="Распознано верно">
            <IconCheck size={28} />
          </button>
        </footer>
      )}
      <p className="sw-hint">Свайп вправо — верно, влево — ошибка · клавиши ← → · Z отменить</p>
    </div>
  );
}
