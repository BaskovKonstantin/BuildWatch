"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { NavBar } from "@/components/NavBar";
import { ObjectTimelineFeed } from "@/components/ObjectTimelineFeed";
import { SwipeReview, reviewItems } from "@/components/SwipeReview";
import { IconArrowUpRight, IconCheck, IconClose, IconPin, IconUpload, IconWarning } from "@/components/Icons";
import { apiFetch } from "@/lib/api";
import { Card, HumanEvent, fmt, snapshotTone, stageForDate, useObjectCard } from "@/lib/objectCard";
import { equipmentRu, shortDate, typeTint } from "@/lib/format";
import { useThemeId } from "@/lib/themes";

const BOX_CONF = 0.2;
const OBSERVED_CONF = 0.35;
const DAY_MS = 86_400_000;

type Schedule = { tone: "ok" | "risk" | "late" | "none"; label: string; note: string };

function scheduleVerdict(card: Card): Schedule {
  const today = new Date().toISOString().slice(0, 10);
  if (!card.stages.length) return { tone: "none", label: "План не задан", note: "Загрузите календарный план, чтобы сравнивать факт с графиком." };
  const overdue = card.stages.filter((s) => s.status !== "done" && s.date_to.slice(0, 10) < today);
  if (overdue.length) {
    const worst = overdue.reduce((a, b) => (a.date_to < b.date_to ? a : b));
    const days = Math.round((Date.parse(today) - Date.parse(worst.date_to.slice(0, 10))) / DAY_MS);
    return { tone: "late", label: `Отставание ${days} дн.`, note: `Этап «${worst.name}» должен был завершиться ${fmt(worst.date_to)}.` };
  }
  const problems = card.summary?.violations_open ?? 0;
  if (problems > 0) return { tone: "risk", label: "Риск отставания", note: `${problems} открытых проблем по технике на снимках. Сроки этапов пока не сорваны.` };
  return { tone: "ok", label: "По графику", note: "Этапы идут в срок, критичных расхождений на снимках нет." };
}

export default function ObjectPage() {
  const { id } = useParams<{ id: string }>();
  const theme = useThemeId();
  const { card, load } = useObjectCard(id);
  const [snapId, setSnapId] = useState<number | null>(null);
  const [showBoxes, setShowBoxes] = useState(true);
  const [swipeOpen, setSwipeOpen] = useState(false);
  const [humanEvents, setHumanEvents] = useState<HumanEvent[]>([]);
  const [error, setError] = useState("");

  const loadEvents = useCallback(async () => {
    const res = await apiFetch(`/api/objects/${id}/events`);
    if (res.ok) setHumanEvents(await res.json());
  }, [id]);
  useEffect(() => { void loadEvents(); }, [loadEvents]);

  useEffect(() => {
    if (!card) return;
    const requested = Number(new URLSearchParams(window.location.search).get("snapshot"));
    setSnapId((cur) => {
      if (cur && card.snapshots.some((s) => s.id === cur)) return cur;
      if (requested && card.snapshots.some((s) => s.id === requested)) return requested;
      return card.snapshots[0]?.id ?? null;
    });
    if (new URLSearchParams(window.location.search).has("review")) setSwipeOpen(true);
  }, [card]);

  const snap = card?.snapshots.find((s) => s.id === snapId) ?? null;
  const planStage = card && snap ? stageForDate(card.stages, snap.captured_at) ?? null : null;
  const requirements = planStage ? card?.stage_requirements?.[String(planStage.id)] ?? [] : [];
  const observed = useMemo(
    () => new Set((snap?.detections ?? []).filter((d) => d.score >= OBSERVED_CONF && d.verdict !== "wrong").map((d) => d.label)),
    [snap],
  );
  const missing = requirements.filter((r) => !r.classes.some((c) => observed.has(c)));
  const toReview = useMemo(() => (card ? reviewItems(card, BOX_CONF).length : 0), [card]);
  const reviewed = useMemo(
    () => card?.snapshots.flatMap((s) => s.detections).filter((d) => d.verdict).length ?? 0,
    [card],
  );

  async function uploadFile(file: File) {
    const body = new FormData();
    body.set("file", file);
    const res = await apiFetch(`/api/objects/${id}/upload`, { method: "POST", body });
    if (res.ok) void load(); else setError("Не удалось загрузить снимок");
  }

  async function startDetect(snapshotId: number) {
    const body = new FormData();
    body.set("model", "equipment");
    const res = await apiFetch(`/api/snapshots/${snapshotId}/detect`, { method: "POST", body });
    if (res.ok) void load(); else setError("Не удалось запустить распознавание");
  }

  if (!card) {
    return (
      <main className={`page v-${theme}`}>
        <NavBar wide title="Объект" back={{ href: "/", label: "Объекты" }} />
        <div className="content wide"><div className="hero skeleton" /></div>
      </main>
    );
  }

  const schedule = scheduleVerdict(card);
  const location = [card.object.district, card.object.address].filter(Boolean).join(" · ");
  const openSignals = (card.summary?.violations_open ?? 0) + (card.summary?.reviews_open ?? 0);
  const conclusion = !snap || ["new", "processing", "failed"].includes(snap.status) ? { tone: "none", text: "Недостаточно данных" }
    : !planStage ? { tone: "none", text: "Снимок вне сроков плана" }
      : !requirements.length ? { tone: "none", text: "Для этапа нет правила" }
        : missing.length ? { tone: "bad", text: `Не видно: ${missing.map((m) => m.name).join(", ")}` }
          : { tone: "ok", text: "Соответствует плану" };

  return (
    <main className={`page v-${theme}`}>
      <NavBar wide title={card.object.name} back={{ href: "/", label: "Объекты" }}
        right={<>
          <Link className="mini" href={`/objects/${id}#chronology`}>Хронология</Link>
          <Link className="mini report-nav-link" href={`/objects/${id}/report`}>Отчёт</Link>
          <label className="btn small" style={{ cursor: "pointer" }}>
            <IconUpload size={16} /><span className="hide-sm">Снимок</span>
            <input type="file" accept="image/*" style={{ display: "none" }}
              onChange={(e) => { const f = e.target.files?.[0]; if (f) void uploadFile(f); e.target.value = ""; }} />
          </label>
        </>} />
      {error && <div className="toast error" role="alert">{error} <button onClick={() => setError("")} aria-label="Закрыть"><IconClose size={14} /></button></div>}

      <div className="content wide oc">
        <section className="oc-hero">
          <div className="oc-id">
            <span className="glass-pill solid"><i className={`dot tint-${typeTint(card.object.type)}`} />{card.object.type}</span>
            <h1>{card.object.name}</h1>
            {location && <div className="hero-addr"><IconPin size={15} />{location}</div>}
          </div>
          <div className={`oc-verdict ${schedule.tone}`}>
            <span className="oc-kicker">Статус по графику</span>
            <strong>{schedule.label}</strong>
            <p>{schedule.note}</p>
          </div>
        </section>

        {card.stages.length > 0 && (
          <ol className="oc-stages" aria-label="Этапы плана">
            {card.stages.map((st, i) => (
              <li key={st.id} className={`${st.status} ${card.summary?.stage?.name === st.name ? "now" : ""}`}>
                <span className="oc-stage-n">{st.status === "done" ? <IconCheck size={12} /> : i + 1}</span>
                <span className="oc-stage-t"><b>{st.name}</b><small>до {shortDate(st.date_to)}</small></span>
              </li>
            ))}
          </ol>
        )}

        <section className="oc-main">
          <div className="oc-viewer">
            <div className="oc-viewer-bar">
              <span className="oc-kicker">Снимок · {snap ? fmt(snap.captured_at) : "нет снимков"}</span>
              <label className="tgl"><input type="checkbox" checked={showBoxes} onChange={(e) => setShowBoxes(e.target.checked)} />Боксы</label>
            </div>
            {snap ? (
              <div className="canvas">
                <img src={`/api/snapshots/${snap.id}/file`} alt={`Снимок ${fmt(snap.captured_at)}`} />
                {showBoxes && snap.detections.filter((d) => d.score >= BOX_CONF && d.verdict !== "wrong").map((d) => (
                  <div key={d.id} className={`box b-${d.match} ${d.verdict === "correct" ? "verified" : ""}`} style={{
                    left: `${(d.x1 / snap.width) * 100}%`, top: `${(d.y1 / snap.height) * 100}%`,
                    width: `${((d.x2 - d.x1) / snap.width) * 100}%`, height: `${((d.y2 - d.y1) / snap.height) * 100}%`,
                  }}><span className="tag">{equipmentRu(d.label)} · {d.score.toFixed(2)}</span></div>
                ))}
                {snap.status === "processing" && <div className="canvas-state">Идёт распознавание…</div>}
                {(snap.status === "new" || snap.status === "failed") && (
                  <button type="button" className="canvas-state action" onClick={() => void startDetect(snap.id)}>
                    {snap.status === "failed" ? "Повторить распознавание" : "Запустить распознавание"}
                  </button>
                )}
              </div>
            ) : <div className="empty">Загрузите первый снимок площадки</div>}
            {card.snapshots.length > 1 && (
              <div className="filmstrip" role="listbox" aria-label="Снимки объекта">
                {card.snapshots.map((s) => (
                  <button key={s.id} type="button" role="option" aria-selected={s.id === snapId}
                    className={`film ${snapshotTone(s)} ${s.id === snapId ? "on" : ""}`} onClick={() => setSnapId(s.id)}>
                    <img src={`/api/snapshots/${s.id}/file`} alt="" loading="lazy" />
                    <span>{fmt(s.captured_at).slice(0, 5)}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          <aside className="oc-side">
            <div className="oc-fact">
              <span className="oc-kicker">План и факт на снимке</span>
              <dl>
                <div><dt>Этап по плану</dt><dd>{planStage?.name ?? "—"}</dd></div>
                <div><dt>Нужна техника</dt><dd>{requirements.length ? requirements.map((r) => r.name).join(", ") : "—"}</dd></div>
                <div><dt>Видно на кадре</dt><dd>{observed.size ? [...observed].map(equipmentRu).join(", ") : "техника не найдена"}</dd></div>
              </dl>
              <div className={`oc-conclusion ${conclusion.tone}`}>
                {conclusion.tone === "bad" ? <IconWarning size={16} /> : conclusion.tone === "ok" ? <IconCheck size={16} /> : null}
                {conclusion.text}
              </div>
            </div>

            <button type="button" className="oc-cta" onClick={() => setSwipeOpen(true)}>
              <span className="oc-cta-stack" aria-hidden="true"><i /><i /><i /></span>
              <span className="oc-cta-copy">
                <strong>Проверить распознавание</strong>
                <small>{toReview ? `${toReview} карточек · свайп вправо верно, влево ошибка` : `Всё проверено · ${reviewed} решений`}</small>
              </span>
              <b className="oc-cta-n">{toReview}</b>
            </button>

            <Link className="oc-link" href={`/objects/${id}/timeline`}>
              <span><strong>Календарь и редактор плана</strong><small>{openSignals ? `${openSignals} открытых сигналов · события, CSV/XLSX` : "События, календарь, импорт плана"}</small></span>
              <IconArrowUpRight size={16} />
            </Link>
          </aside>
        </section>

        <section className="oc-timeline" id="chronology" aria-labelledby="oc-chronology-title">
          <header className="oc-timeline-head">
            <div>
              <span className="oc-kicker" id="oc-chronology-title">Хронология</span>
              <h2>Этапы, снимки и сигналы</h2>
              <p>Лента по фазам плана — те же события, что на отдельной странице. Клик по событию открывает снимок.</p>
            </div>
            <Link className="mini tinted" href={`/objects/${id}/timeline`}>Календарь и редактор</Link>
          </header>
          {card && (
            <ObjectTimelineFeed objectId={id} card={card} humanEvents={humanEvents} wide
              onStagesChanged={() => void load()} onError={(msg) => setError(msg)} />
          )}
        </section>
      </div>

      {swipeOpen && (
        <SwipeReview card={card} minScore={BOX_CONF} onChanged={() => void load()}
          onClose={() => {
            setSwipeOpen(false);
            const url = new URL(window.location.href);
            url.searchParams.delete("review");
            window.history.replaceState(null, "", url.toString());
          }} />
      )}
    </main>
  );
}
