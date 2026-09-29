"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { NavBar } from "@/components/NavBar";
import { ObjectTimelineFeed } from "@/components/ObjectTimelineFeed";
import { SiteZoneLayer, type SiteZone } from "@/components/SiteZoneLayer";
import { SwipeReview, reviewItems } from "@/components/SwipeReview";
import { IconCheck, IconClose, IconPin, IconUpload, IconWarning } from "@/components/Icons";
import { apiFetch } from "@/lib/api";
import { Card, Forecast, HumanEvent, fmt, snapshotTone, stageForDate, useObjectCard } from "@/lib/objectCard";
import { equipmentRu, shortDate, typeTint } from "@/lib/format";
import { useThemeId } from "@/lib/themes";

const FORECAST_TONE: Record<Forecast["verdict"], Schedule["tone"]> = {
  behind: "late",
  ahead: "ok",
  on_track: "ok",
  unknown: "none",
};
const ZONE_KINDS: { id: SiteZone["kind"]; label: string }[] = [
  { id: "danger", label: "Опасная" },
  { id: "work", label: "Работы" },
  { id: "storage", label: "Склад" },
];

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
  const [zonesOn, setZonesOn] = useState(false);
  const [zoneKind, setZoneKind] = useState<SiteZone["kind"]>("danger");

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
  const forecast = card.summary?.forecast;
  const gap = forecast?.equipment_gap.rows ?? [];
  const location = [card.object.district, card.object.address].filter(Boolean).join(" · ");
  const openSignals = (card.summary?.violations_open ?? 0) + (card.summary?.reviews_open ?? 0);
  const snapWarnings = snap
    ? card.warnings
      .filter((w) => w.snapshot_id === snap.id && w.status === "open")
      .sort((a, b) => Number(b.severity === "violation") - Number(a.severity === "violation"))
    : [];
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
        </section>

        <section className={`oc-verdict ${forecast ? "split" : ""} ${forecast && FORECAST_TONE[forecast.verdict] === "late" ? "late" : schedule.tone}`}>
            <div className="oc-status">
              <span className="oc-kicker">Статус по графику</span>
              <strong>{schedule.label}</strong>
              <p>{schedule.note}</p>
              {card.dynamics && card.dynamics.points.length > 0 && (
                <div className="oc-dyn" aria-label="Динамика по неделям">
                  <span className="oc-kicker">Динамика · {card.dynamics.window_days} дн.</span>
                  <p>{card.dynamics.sentence}</p>
                  {card.dynamics.points.length > 1 && (
                    <ol className="oc-dyn-weeks">
                      {card.dynamics.points.map((p) => {
                        const peak = Math.max(1, ...card.dynamics!.points.map((x) => x.violations + x.reviews));
                        return (
                          <li key={p.date} title={`${fmt(p.date)} · ${p.stage_name ?? "вне плана"} · снимков ${p.snapshots} · проблем ${p.violations}, вопросов ${p.reviews}`}>
                            <span className="oc-dyn-bar" aria-hidden="true">
                              <i className="rv" style={{ height: `${(p.reviews / peak) * 100}%` }} />
                              <i className="vl" style={{ height: `${(p.violations / peak) * 100}%` }} />
                            </span>
                            <small>{fmt(p.date).slice(0, 5)}</small>
                          </li>
                        );
                      })}
                    </ol>
                  )}
                </div>
              )}
            </div>
            {forecast && (
              <div className="oc-forecast">
                <div className="oc-forecast-head">
                  <span className="oc-kicker">Прогноз · умеренный сценарий</span>
                  {forecast.days_delta != null && forecast.days_delta !== 0 && (
                    <b className={`oc-delta ${forecast.days_delta > 0 ? "late" : "ok"}`}>
                      {forecast.days_delta > 0 ? `+${forecast.days_delta}` : forecast.days_delta} дн.
                    </b>
                  )}
                </div>
                <strong className="oc-cap">{forecast.headline.replace(/^Прогноз:\s*/i, "").replace(/\s*\(сценарий умеренный\)/i, "")}</strong>
                <div className="oc-forecast-stages">
                  <span><small>План</small>{forecast.plan_stage ?? "—"}</span>
                  <span><small>Факт</small>{forecast.fact_stage ?? "нет снимка в сроках"}</span>
                  <span><small>Темп</small>{forecast.pace_label}</span>
                </div>
                {forecast.drivers.length > 0 && (
                  <ul className="oc-drivers">
                    {forecast.drivers.slice(0, 3).map((d) => <li key={d}>{d}</li>)}
                  </ul>
                )}
                <small className="oc-disclaimer">{forecast.disclaimer}</small>
              </div>
            )}
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
              <span className="oc-viewer-actions">
                <button type="button" className={`mini ${zonesOn ? "pri" : ""}`} onClick={() => setZonesOn((on) => !on)}>Зоны</button>
                <label className="tgl"><input type="checkbox" checked={showBoxes} onChange={(e) => setShowBoxes(e.target.checked)} />Боксы</label>
              </span>
            </div>
            {zonesOn && (
              <div className="zone-tools">
                {ZONE_KINDS.map((item) => (
                  <button key={item.id} type="button" className={`mini ${zoneKind === item.id ? "pri" : ""}`} onClick={() => setZoneKind(item.id)}>{item.label}</button>
                ))}
                <span>Протяните прямоугольник по кадру</span>
              </div>
            )}
            {snap ? (
              <div className="canvas">
                <img src={`/api/snapshots/${snap.id}/file`} alt={`Снимок ${fmt(snap.captured_at)}`} />
                {showBoxes && snap.detections.filter((d) => d.score >= BOX_CONF && d.verdict !== "wrong").map((d) => (
                  <div key={d.id} className={`box b-${d.match} ${d.verdict === "correct" ? "verified" : ""}`} style={{
                    left: `${(d.x1 / snap.width) * 100}%`, top: `${(d.y1 / snap.height) * 100}%`,
                    width: `${((d.x2 - d.x1) / snap.width) * 100}%`, height: `${((d.y2 - d.y1) / snap.height) * 100}%`,
                  }}><span className="tag">{equipmentRu(d.label)} · {d.score.toFixed(2)}</span></div>
                ))}
                <SiteZoneLayer objectId={id} zones={card.zones ?? []} enabled={zonesOn} kind={zoneKind} onChanged={() => void load()} onError={setError} />
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
              {forecast && (
                <div className={`oc-activity ${forecast.activity.verdict}`}>
                  <span className="oc-activity-dot" aria-hidden="true" />
                  <div><b>{forecast.activity.label}</b><small>{forecast.activity.note}</small></div>
                </div>
              )}
              {gap.length > 0 && (
                <div className="oc-gap">
                  <span className="oc-gap-title">Техника этапа · последние {forecast?.equipment_gap.window ?? 3} снимка</span>
                  <ul>
                    {gap.map((row) => (
                      <li key={row.name} className={row.missing ? "miss" : "seen"}>
                        {row.missing ? <IconClose size={12} /> : <IconCheck size={12} />}
                        <span>{row.name}</span>
                        <em>{row.missing ? "не видно" : "видели"}</em>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <div className={`oc-conclusion ${conclusion.tone}`}>
                {conclusion.tone === "bad" ? <IconWarning size={16} /> : conclusion.tone === "ok" ? <IconCheck size={16} /> : null}
                {conclusion.text}
              </div>
            </div>

            <div className="oc-review" id="quality">
              <button type="button" className="oc-cta" onClick={() => setSwipeOpen(true)}>
                <span className="oc-cta-stack" aria-hidden="true"><i /><i /><i /></span>
                <span className="oc-cta-copy">
                  <strong>Проверить распознавание</strong>
                  <small>{toReview ? `${toReview} карточек · ← ошибка, → верно` : `Всё проверено · ${reviewed} решений`}</small>
                </span>
                <b className="oc-cta-n">{toReview}</b>
              </button>
              {card.quality && card.quality.total > 0 && (
                <div className="oc-quality" title={card.quality.note}>
                  <div className="oc-quality-bar" aria-hidden="true">
                    <i className="ok" style={{ width: `${(card.quality.correct / card.quality.total) * 100}%` }} />
                    <i className="bad" style={{ width: `${(card.quality.wrong / card.quality.total) * 100}%` }} />
                  </div>
                  <div className="oc-quality-row">
                    <span><b>{card.quality.correct}</b> верно</span>
                    <span><b>{card.quality.wrong}</b> ошибка</span>
                    <span><b>{card.quality.pending}</b> ждут</span>
                    <span className="oc-quality-share">
                      {card.quality.correct_share == null ? "точность —" : `точность ${Math.round(card.quality.correct_share * 100)}%`}
                    </span>
                  </div>
                </div>
              )}
            </div>

            <div className="oc-signals">
              <div className="oc-signals-head">
                <span className="oc-kicker">Сигналы на снимке</span>
                <a href="#chronology">все {openSignals} →</a>
              </div>
              <div className="oc-signals-body">
                {snapWarnings.length ? (
                  <ul>
                    {snapWarnings.map((w) => (
                      <li key={w.id} className={w.severity === "violation" ? "bad" : "warn"} title={w.why}>
                        <b>{w.title}</b>
                        <small>{w.severity === "violation" ? "Проблема" : "Вопрос"} · {w.rule}</small>
                      </li>
                    ))}
                  </ul>
                ) : <p className="oc-signals-empty">Открытых сигналов по этому снимку нет.</p>}
              </div>
            </div>
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
