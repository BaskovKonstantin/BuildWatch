"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Topbar } from "@/components/Topbar";

type Detection = {
  id: number;
  model: string;
  label: string;
  score: number;
  x1: number; y1: number; x2: number; y2: number;
  match: "ok" | "mismatch" | "review";
};
type Snapshot = {
  id: number;
  filename: string;
  captured_at: string;
  status: string;
  width: number;
  height: number;
  detections: Detection[];
};
type Stage = {
  id: number;
  kind: string;
  name: string;
  date_from: string;
  date_to: string;
  status: string;
};
type Warning = {
  id: number;
  snapshot_id: number;
  rule: string;
  title: string;
  body: string;
  why: string;
  source: string;
  status: string;
  severity: string;
  captured_at: string | null;
};
type Card = {
  object: { id: number; name: string; type: string };
  stages: Stage[];
  stage_kinds: string[];
  snapshots: Snapshot[];
  warnings: Warning[];
  counts: { snapshots: number; warnings_open: number; warnings_total: number };
  conf_threshold: number;
};

const MODELS = ["yolo_world", "uisikdag", "Ансамбль"];
const KIND_RU: Record<string, string> = {
  ground: "подготовка", excavation: "котлован", frame: "каркас",
  facade: "фасады", roof: "кровля", other: "прочее",
};

function fmt(d: string) {
  const [y, m, dd] = d.split("-");
  return `${dd}.${m}.${y}`;
}

function timelineClass(snap: Snapshot): string {
  if (snap.status === "processing") return "processing";
  const violations = snap.detections.filter((d) => d.match === "mismatch");
  const reviews = snap.detections.filter((d) => d.match === "review");
  if (violations.length) return "bad";
  if (snap.status === "new" || snap.status === "empty") return "new";
  if (reviews.length) return "warn";
  return "ok";
}

export default function Page() {
  const params = useParams<{ id: string }>();
  return <ObjectCard id={params.id} />;
}

function ObjectCard({ id }: { id: string }) {
  const [card, setCard] = useState<Card | null>(null);
  const [snapId, setSnapId] = useState<number | null>(null);
  const [model, setModel] = useState("yolo_world");
  const [conf, setConf] = useState(0.2);
  const [showBoxes, setShowBoxes] = useState(true);
  const [hlBox, setHlBox] = useState<string | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);

  const load = useCallback(async () => {
    const res = await fetch(`/api/objects/${id}`);
    if (!res.ok) return;
    const data: Card = await res.json();
    setCard(data);
    setSnapId((cur) =>
      cur && data.snapshots.some((s) => s.id === cur)
        ? cur
        : (data.snapshots[0]?.id ?? null),
    );
  }, [id]);

  useEffect(() => { load(); }, [load]);

  const snap = useMemo(
    () => card?.snapshots.find((s) => s.id === snapId) ?? null,
    [card, snapId],
  );
  const warnings = useMemo(
    () => (card ? card.warnings.filter((w) => w.snapshot_id === snapId) : []),
    [card, snapId],
  );
  const visibleDets = useMemo(() => {
    if (!snap) return [];
    return snap.detections
      .filter((d) => d.score >= conf)
      .filter((d) =>
        model === "Ансамбль"
          ? true
          : d.model === model ||
            (model === "uisikdag" && d.model === "uisikdag"),
      );
  }, [snap, model, conf]);

  async function resolveWarning(warningId: number, action: "confirm" | "dismiss" | "reopen") {
    const body = new FormData();
    body.set("action", action);
    await fetch(`/api/warnings/${warningId}`, { method: "POST", body });
    load();
  }

  async function uploadFile(file: File) {
    const body = new FormData();
    body.set("file", file);
    const res = await fetch(`/api/objects/${id}/upload`, { method: "POST", body });
    if (res.ok) load();
  }

  async function startDetect(snapshotId: number) {
    await fetch(`/api/snapshots/${snapshotId}/detect`, { method: "POST" });
    load();
    const timer = setInterval(async () => {
      await load();
      // stop polling when the snapshot leaves "processing"
    }, 5000);
    setTimeout(() => clearInterval(timer), 15 * 60 * 1000);
  }

  if (!card) {
    return (
      <main>
        <Topbar crumbs="Объекты / …" />
        <div className="empty">Загрузка…</div>
      </main>
    );
  }

  return (
    <main>
      <Topbar
        crumbs={
          <>
            <Link href="/">Объекты</Link> / <b>{card.object.name}</b>
          </>
        }
        chips={
          <>
            {card.counts.warnings_open > 0 ? (
              <span className="chip bad">
                Предупреждений: {card.counts.warnings_open}
              </span>
            ) : (
              <span className="chip ok">Нарушений нет</span>
            )}
            <span className="chip ok">Снимков: {card.counts.snapshots}</span>
          </>
        }
        action={
          <label className="btn" style={{ cursor: "pointer" }}>
            Загрузить снимок
            <input
              type="file"
              accept="image/*"
              style={{ display: "none" }}
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) uploadFile(f);
              }}
            />
          </label>
        }
      />

      <div className="wrap">
        {/* LEFT: stages + warnings */}
        <div className="pane">
          <div className="pane-h">
            Этапы работ · план объекта
            <button className="mini" onClick={() => setEditorOpen(true)}>
              Редактор
            </button>
          </div>
          <div className="stages-note">
            Виды работ — из справочника ЛТЦ. Плановые даты задаёт инспектор в
            редакторе: справочник ЛТЦ не содержит календаря.
          </div>
          {card.stages.map((st) => {
            const progress =
              st.status === "current" &&
              snap && snap.captured_at >= st.date_from && snap.captured_at <= st.date_to
                ? 34
                : st.status === "current"
                  ? Math.min(95, Math.max(5,
                      ((new Date(snap!.captured_at).getTime() -
                        new Date(st.date_from).getTime()) /
                        Math.max(1, new Date(st.date_to).getTime() -
                          new Date(st.date_from).getTime())) * 100))
                  : 0;
            return (
              <div className="stage" key={st.id}>
                <div className="row">
                  <span className="name">{st.name}</span>
                  <span className={`pill ${st.status}`}>
                    {st.status === "done" ? "✓" : st.status === "current" ? "текущий" : "ожидается"}
                  </span>
                </div>
                <div className="sub">
                  {fmt(st.date_from)} – {fmt(st.date_to)} ·{" "}
                  {KIND_RU[st.kind] ?? st.kind}
                </div>
                {st.status === "current" && (
                  <div className="bar"><i style={{ width: `${progress}%` }} /></div>
                )}
              </div>
            );
          })}

          <div className="pane-h" style={{ borderTop: "1px solid var(--line2)" }}>
            Предупреждения
          </div>
          {warnings.length === 0 ? (
            <div className="empty">На этом снимке нарушений нет</div>
          ) : (
            warnings.map((w) => (
              <div
                key={w.id}
                className={`warn-card ${w.severity} ${w.status}`}
                onClick={() => setHlBox(null)}
              >
                <div className="warn-t">
                  <span className="ic" style={{ color: w.severity === "violation" ? "var(--bad)" : "var(--warn)" }}>
                    {w.severity === "violation" ? "🚫" : "❔"}
                  </span>
                  <span>{w.title}</span>
                </div>
                <div className="warn-body">{w.body}</div>
                <div className="warn-why">
                  <b>Почему:</b> {w.why.replace(/^Почему:\s*/, "")}
                </div>
                {w.status === "open" ? (
                  <div className="warn-act">
                    {w.severity === "violation" && (
                      <button
                        className="mini pri"
                        onClick={async (e) => {
                          e.stopPropagation();
                          const body = new FormData();
                          body.set("action", "confirm");
                          await fetch(`/api/warnings/${w.id}`, { method: "POST", body });
                          load();
                        }}
                      >
                        Подтвердить нарушение
                      </button>
                    )}
                    <button
                      className="mini"
                      onClick={async (e) => {
                        e.stopPropagation();
                        const body = new FormData();
                        body.set("action", "dismiss");
                        await fetch(`/api/warnings/${w.id}`, { method: "POST", body });
                        load();
                      }}
                    >
                      Отклонить
                    </button>
                  </div>
                ) : (
                  <div className="warn-act">
                    <span className="chip" style={{ fontSize: 10.5 }}>
                      {w.status === "confirmed" ? "Подтверждено" : "Отклонено"}
                    </span>
                    <button
                      className="mini"
                      onClick={async (e) => {
                        e.stopPropagation();
                        const body = new FormData();
                        body.set("action", "reopen");
                        await fetch(`/api/warnings/${w.id}`, { method: "POST", body });
                        load();
                      }}
                    >
                      Вернуть
                    </button>
                  </div>
                )}
                <div className="src">{w.source}</div>
              </div>
            ))
          )}
        </div>

        {/* CENTER: snapshot */}
        <div className="pane">
          <div className="stagebar">
            <div className="seg">
              {MODELS.map((m) => (
                <button
                  key={m}
                  className={model === m ? "on" : ""}
                  onClick={() => setModel(m)}
                >
                  {m === "yolo_world" ? "YOLO-World" : m === "uisikdag" ? "UISikDag" : "Ансамбль"}
                </button>
              ))}
            </div>
            <label className="tgl">
              <input
                type="checkbox"
                checked={showBoxes}
                onChange={(e) => setShowBoxes(e.target.checked)}
              />
              Боксы
            </label>
            <div className="conf">
              Порог
              <input
                type="range"
                min={10}
                max={90}
                value={conf * 100}
                style={{ width: 88 }}
                onChange={(e) => setConf(Number(e.target.value) / 100)}
              />
              <b className="mono">{conf.toFixed(2)}</b>
            </div>
          </div>
          {snap ? (
            <>
              <div className="imgwrap">
                <div className="canvas">
                  <img
                    src={`/api/snapshots/${snap.id}/file`}
                    alt={`Снимок ${snap.captured_at}`}
                  />
                  {showBoxes &&
                    visibleDets.map((d) => {
                      const left = (d.x1 / snap.width) * 100;
                      const top = (d.y1 / snap.height) * 100;
                      const w = ((d.x2 - d.x1) / snap.width) * 100;
                      const h = ((d.y2 - d.y1) / snap.height) * 100;
                      const key = `${d.id}`;
                      return (
                        <div
                          key={key}
                          className={`box b-${d.match} ${hlBox === key ? "hl" : ""}`}
                          style={{ left: `${left}%`, top: `${top}%`, width: `${w}%`, height: `${h}%` }}
                        >
                          <span className="tag">
                            {d.label} · {d.score.toFixed(2)}
                          </span>
                        </div>
                      );
                    })}
                </div>
              </div>
              <div className="legend">
                <span><i style={{ background: "#30B0C7" }} />Совпадает с этапом</span>
                <span><i style={{ background: "#FF9500" }} />Требует проверки</span>
                <span><i style={{ background: "#FF3B30" }} />Не соответствует</span>
                <span className="meta">
                  {snap.width}×{snap.height} · {fmt(snap.captured_at)} ·{" "}
                  {snap.status === "processing" ? "распознавание…" : snap.status}
                </span>
              </div>
              <table className="det-table">
                <thead>
                  <tr><th>Объект</th><th>Уверенность</th><th>Соответствие этапу</th><th>Действие</th></tr>
                </thead>
                <tbody>
                  {visibleDets.length === 0 ? (
                    <tr>
                      <td colSpan={4}>
                        {snap.status === "new" ? (
                          <span>
                            Снимок не разобран.{" "}
                            <button className="mini pri" onClick={() => startDetect(snap.id)}>
                              Запустить распознавание
                            </button>
                          </span>
                        ) : snap.status === "processing" ? (
                          "Идёт распознавание (первый запуск модели — до 5 минут)…"
                        ) : (
                          "Ниже порога уверенности объектов нет"
                        )}
                      </td>
                    </tr>
                  ) : (
                    visibleDets.map((d) => (
                      <tr key={d.id}>
                        <td><b>{d.label}</b> <span className="mono" style={{ color: "var(--ink3)" }}>#{d.id}</span></td>
                        <td className="mono">{d.score.toFixed(2)}</td>
                        <td>
                          <span className={`badge ${d.match}`}>
                            {d.match === "ok"
                              ? "этапу соответствует"
                              : d.match === "review"
                                ? "низкая уверенность · проверка"
                                : "не соответствует этапу"}
                          </span>
                        </td>
                        <td>
                          <button className="mini" onClick={() => setHlBox(`${d.id}`)}>
                            Показать
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </>
          ) : (
            <div className="empty">Выберите снимок на таймлайне</div>
          )}
        </div>

        {/* RIGHT: timeline */}
        <div className="pane">
          <div className="pane-h">
            Хронология <span className="mono" style={{ fontSize: 10 }}>июнь–июль</span>
          </div>
          <div className="tl">
            {(card?.snapshots ?? []).slice(0, 12).map((s, i) => {
              const cls = timelineClass(s);
              const violation = s.detections.filter((d) => d.match === "mismatch").length;
              const review = s.detections.filter((d) => d.match === "review").length;
              return (
                <div
                  key={s.id}
                  className={`tl-item ${cls} ${s.id === snapId ? "active" : ""}`}
                  style={{ animationDelay: `${i * 0.05}s` }}
                  onClick={() => setSnapId(s.id)}
                >
                  <div>
                    <div className="d">{fmt(s.captured_at)}</div>
                    <div className="s">
                      {s.status === "processing"
                        ? "распознавание…"
                        : s.detections.length === 0
                          ? "не разобран"
                          : `${s.detections.length} объектов`}
                    </div>
                  </div>
                  <span className="n">
                    {violation ? String(violation) : review ? String(review) : s.status === "empty" ? "✓" : "—"}
                  </span>
                </div>
              );
            })}
            {(card?.snapshots.length ?? 0) > 12 && (
              <div className="tl-more">
                Показать все {card!.snapshots.length} ↓
              </div>
            )}
          </div>
        </div>
      </div>

      {editorOpen && (
        <StagesEditor
          card={card}
          onClose={() => setEditorOpen(false)}
          onSaved={() => { setEditorOpen(false); load(); }}
        />
      )}
    </main>
  );
}

type EditorStage = {
  kind: string;
  name: string;
  date_from: string;
  date_to: string;
  status: string;
};

function StagesEditor({
  card, onClose, onSaved,
}: { card: Card; onClose: () => void; onSaved: () => void }) {
  const [rows, setRows] = useState<EditorStage[]>(
    card.stages.map(({ kind, name, date_from, date_to, status }) => ({
      kind, name, date_from, date_to, status,
    })),
  );
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    await fetch(`/api/objects/${card.object.id}/stages`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(rows),
    });
    onSaved();
  }

  return (
    <div className="modal-back" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="pane-h" style={{ padding: "0 0 12px" }}>
          Редактор этапов · план объекта
          <button className="mini" onClick={onClose}>Закрыть</button>
        </div>
        <div className="hint" style={{ padding: "0 0 10px" }}>
          Виды работ выбираются из справочника ЛТЦ; плановые даты задаёт
          инспектор. После сохранения предупреждения пересчитываются.
        </div>
        {rows.map((st, i) => (
          <div className="stage-row" key={i}>
            <input
              value={st.name}
              onChange={(e) => setRows(rows.map((r, j) => j === i ? { ...r, name: e.target.value } : r))}
            />
            <select
              value={st.kind}
              onChange={(e) => setRows(rows.map((r, j) => j === i ? { ...r, kind: e.target.value } : r))}
            >
              {card.stage_kinds.map((k) => (
                <option key={k} value={k}>{KIND_RU[k] ?? k}</option>
              ))}
            </select>
            <input
              type="date"
              value={st.date_from}
              onChange={(e) => setRows(rows.map((r, j) => j === i ? { ...r, date_from: e.target.value } : r))}
            />
            <input
              type="date"
              value={st.date_to}
              onChange={(e) => setRows(rows.map((r, j) => j === i ? { ...r, date_to: e.target.value } : r))}
            />
            <select
              value={st.status}
              onChange={(e) => setRows(rows.map((r, j) => j === i ? { ...r, status: e.target.value } : r))}
            >
              <option value="done">завершён</option>
              <option value="current">текущий</option>
              <option value="future">ожидается</option>
            </select>
            <button
              className="mini"
              onClick={() => setRows(rows.filter((_, j) => j !== i))}
            >
              ✕
            </button>
          </div>
        ))}
        <div className="warn-act">
          <button
            className="mini"
            onClick={() => setRows([...rows, {
              kind: "other", name: "Новый этап", date_from: card.snapshots[0]?.captured_at ?? "2026-07-01",
              date_to: "2026-12-31", status: "future",
            }])}
          >
            + Этап
          </button>
          <span style={{ flex: 1 }} />
          <button className="mini pri" disabled={saving} onClick={save}>
            {saving ? "Сохранение…" : "Сохранить план"}
          </button>
        </div>
      </div>
    </div>
  );
}
