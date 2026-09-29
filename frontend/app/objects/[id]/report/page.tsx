"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { NavBar } from "@/components/NavBar";
import { apiFetch } from "@/lib/api";
import { longDate, numericDate, plural, shortDate } from "@/lib/format";

type Stage = { id: number; name: string; date_from: string; date_to: string; status: string };
type Snapshot = { id: number; captured_at: string; status: string; detections: { label: string; score: number }[] };
type Warning = { id: number; snapshot_id: number; title: string; rule: string; severity: string; status: string; why: string; captured_at: string | null };
type Forecast = {
  headline: string;
  fact_stage: string | null;
  plan_stage: string | null;
  pace_label: string;
  disclaimer: string;
  drivers: string[];
  activity: { label: string; note: string };
  equipment_gap: { window: number; rows: { name: string; seen: boolean; missing: boolean }[] };
};
type Dynamics = { sentence: string; points: { date: string; snapshots: number; stage_name: string | null; violations: number; reviews: number }[] };
type Quality = { correct: number; wrong: number; pending: number; correct_share: number | null; note: string };
type ReportData = {
  object: { id: number; name: string; type: string; address?: string };
  summary: { progress: number; planned_finish: string | null; last_snapshot: string | null; forecast?: Forecast };
  stages: Stage[];
  snapshots: Snapshot[];
  warnings: Warning[];
  dynamics?: Dynamics;
  quality?: Quality;
};

function ruleCaption(rule: string): string {
  if (rule.startsWith("R-01")) return "функциональная зона (этап)";
  if (rule.startsWith("R-08")) return "активность по серии снимков";
  if (rule.startsWith("R-09")) return "опасная зона";
  if (rule.startsWith("R-10")) return "склад на монтаже";
  return rule;
}

const STATUS: Record<string, string> = {
  open: "Требует проверки", confirmed: "Подтверждено инспектором", dismissed: "Отклонено инспектором",
};

export default function ReportPage() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<ReportData | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    apiFetch(`/api/objects/${id}`)
      .then(async (response) => {
        if (!response.ok) throw new Error("Не удалось загрузить данные отчёта");
        return response.json();
      })
      .then(setData)
      .catch((cause) => setError(cause instanceof Error ? cause.message : "Не удалось загрузить данные отчёта"));
  }, [id]);

  const stats = useMemo(() => {
    const warnings = data?.warnings ?? [];
    return {
      open: warnings.filter((warning) => warning.status === "open").length,
      confirmed: warnings.filter((warning) => warning.status === "confirmed").length,
      dismissed: warnings.filter((warning) => warning.status === "dismissed").length,
    };
  }, [data]);

  return (
    <main className="page report-page">
      <NavBar title="Отчёт по объекту" back={{ href: `/objects/${id}`, label: "Объект" }}
        right={<button className="mini pri report-print" disabled={!data} onClick={() => window.print()}>Печать / PDF</button>} />
      <div className="content wide">
        {error ? <div className="report-error" role="alert">{error}</div> : !data ? <div className="hero skeleton" aria-label="Загрузка отчёта" /> : (
          <article className="report-sheet">
            <header className="report-title">
              <div><span className="report-kicker">BUILDWATCH / ОБЪЕКТ {data.object.id}</span><h1>Ход работ и проблемы</h1><p>{data.object.name} · {data.object.type}{data.object.address ? ` · ${data.object.address}` : ""}</p></div>
              <div className="report-stamp">Сформировано {longDate(new Date().toISOString())}<br />Источник: план объекта и снимки камер</div>
            </header>
            <div className="report-metrics">
              <div><span>Прошло времени по плану</span><b>{Math.round(data.summary.progress * 100)}%</b><small>Не является оценкой готовности</small></div>
              <div><span>Последний снимок</span><b>{data.summary.last_snapshot ? shortDate(data.summary.last_snapshot) : "—"}</b><small>{data.snapshots.length} {plural(data.snapshots.length, ["снимок", "снимка", "снимков"])} в истории</small></div>
              <div><span>Открытые проблемы</span><b>{stats.open}</b><small>Требуют проверки человеком</small></div>
              <div><span>Подтверждено</span><b>{stats.confirmed}</b><small>Решение инспектора</small></div>
            </div>
            {data.summary.forecast && (
              <section className="report-section">
                <div className="report-section-head"><h2>Прогноз по графику</h2><span>{data.summary.forecast.pace_label}</span></div>
                <p>{data.summary.forecast.headline}</p>
                <p>Факт по датам снимков: {data.summary.forecast.fact_stage ?? "—"}. План на сегодня: {data.summary.forecast.plan_stage ?? "—"}.</p>
                <p>Активность (по серии снимков): {data.summary.forecast.activity.label}. {data.summary.forecast.activity.note}</p>
                {data.summary.forecast.equipment_gap.rows.length > 0 && (
                  <div className="report-table-wrap"><table><thead><tr><th>На этапе нужно</th><th>Последние {data.summary.forecast.equipment_gap.window} снимка</th><th>Не хватает</th></tr></thead><tbody>
                    {data.summary.forecast.equipment_gap.rows.map((row) => <tr key={row.name}><td>{row.name}</td><td>{row.seen ? "видели" : "не видно"}</td><td>{row.missing ? "да" : "—"}</td></tr>)}
                  </tbody></table></div>
                )}
                <p>{data.summary.forecast.disclaimer}</p>
              </section>
            )}
            {data.dynamics && (
              <section className="report-section">
                <div className="report-section-head"><h2>Динамика</h2><span>{data.dynamics.sentence}</span></div>
                {data.dynamics.points.length > 0 && <div className="report-table-wrap"><table><thead><tr><th>Неделя</th><th>Снимки</th><th>Этап по дате</th><th>Проблемы</th><th>Вопросы</th></tr></thead><tbody>
                  {data.dynamics.points.map((point) => <tr key={point.date}><td>{numericDate(point.date)}</td><td>{point.snapshots}</td><td>{point.stage_name ?? "—"}</td><td>{point.violations}</td><td>{point.reviews}</td></tr>)}
                </tbody></table></div>}
              </section>
            )}
            {data.quality && (
              <section className="report-section">
                <div className="report-section-head"><h2>Качество распознавания</h2><span>{data.quality.note}</span></div>
                <p>Верно {data.quality.correct}, ошибка {data.quality.wrong}, без вердикта {data.quality.pending}. Среди проверенных верных: {data.quality.correct_share == null ? "ещё нет" : `${Math.round(data.quality.correct_share * 100)}%`}.</p>
              </section>
            )}
            <section className="report-section report-plan">
              <div className="report-section-head"><h2>Календарный план</h2><span>{data.stages.length} {plural(data.stages.length, ["этап", "этапа", "этапов"])} · завершение {data.summary.planned_finish ? shortDate(data.summary.planned_finish) : "не указано"}</span></div>
              {data.stages.length ? <div className="report-table-wrap"><table><thead><tr><th>Этап</th><th>Начало</th><th>Окончание</th><th>Статус в плане</th></tr></thead><tbody>
                {data.stages.map((stage) => <tr key={stage.id}><td>{stage.name}</td><td>{numericDate(stage.date_from)}</td><td>{numericDate(stage.date_to)}</td><td>{stage.status === "done" ? "Отмечен завершённым" : stage.status === "current" ? "Текущий" : "Предстоящий"}</td></tr>)}
              </tbody></table></div> : <p className="report-empty">Календарный план не загружен.</p>}
            </section>
            <section className="report-section report-evidence">
              <div className="report-section-head"><h2>Проблемы и доказательства</h2><span>{stats.open} {plural(stats.open, ["открытая проблема", "открытые проблемы", "открытых проблем"])} · {stats.confirmed} подтверждено · {stats.dismissed} отклонено</span></div>
              {data.warnings.length ? <div className="report-cases">{data.warnings.map((warning) => <div className="report-case" key={warning.id}>
                <div><span className="report-rule">{warning.rule}</span><strong>{warning.title}</strong><span className={`report-case-status ${warning.status}`}>{STATUS[warning.status] ?? warning.status}</span><small>{ruleCaption(warning.rule)}</small></div>
                <p>{warning.why.replace(/^Почему:\s*/, "")}</p>
                <Link href={`/objects/${data.object.id}?snapshot=${warning.snapshot_id}&warning=${warning.id}`}>Открыть снимок от {warning.captured_at ? numericDate(warning.captured_at) : "неизвестной даты"} ↗</Link>
              </div>)}</div> : <p className="report-empty">По загруженным снимкам проблемы не сформированы.</p>}
            </section>
            <aside className="report-limits"><strong>Ограничения вывода</strong><p>Камеры показывают только видимую часть площадки. Отсутствие техники на одном снимке не доказывает простой. Для заключения об отставании или опережении нужны подтверждённые фактические этапы работ и достаточная серия наблюдений.</p></aside>
          </article>
        )}
      </div>
    </main>
  );
}
