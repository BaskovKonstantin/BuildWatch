"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { NavBar } from "@/components/NavBar";
import {
  IconBuilding, IconCalendar, IconCamera, IconChevronRight, IconClose, IconEye,
  IconPin, IconPlus, IconSearch, IconTruck, IconWarning,
} from "@/components/Icons";
import { apiFetch, saveToken } from "@/lib/api";
import { useThemeId } from "@/lib/themes";
import {
  DISTRICTS, OBJECT_TYPES, equipmentList, plural, shortDate, todayTitle, typeTint,
} from "@/lib/format";

type Project = {
  id: number;
  name: string;
  type: string;
  district: string;
  address: string;
  description: string;
  snapshots: number;
  warnings_open: number;
  reviews_open: number;
  progress: number;
  planned_finish: string | null;
  stage: { name: string; kind: string; position: number; progress: number; date_to: string } | null;
  stages_total: number;
  last_snapshot: string | null;
  equipment: string[];
  cover: string | null;
};

type Filter = "all" | "violations" | "clean";
const FILTERS: { id: Filter; label: string }[] = [
  { id: "all", label: "Все" },
  { id: "violations", label: "С сигналами" },
  { id: "clean", label: "Без сигналов" },
];

function readUrlState(): { q: string; filter: Filter; type: string } {
  const p = new URLSearchParams(window.location.search);
  const f = p.get("filter");
  return {
    q: p.get("q") ?? "",
    filter: f === "violations" || f === "clean" ? f : "all",
    type: p.get("type") ?? "",
  };
}

export default function Home() {
  const theme = useThemeId();
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [authRequired, setAuthRequired] = useState(false);
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [type, setType] = useState("");
  const [sheetOpen, setSheetOpen] = useState(false);
  const hydrated = useRef(false);

  useEffect(() => {
    const s = readUrlState();
    setQ(s.q); setFilter(s.filter); setType(s.type);
    hydrated.current = true;
    load();
  }, []);

  // Keep filters in the URL so reload / back navigation restores the view.
  useEffect(() => {
    if (!hydrated.current) return;
    const p = new URLSearchParams();
    if (q) p.set("q", q);
    if (filter !== "all") p.set("filter", filter);
    if (type) p.set("type", type);
    if (new URLSearchParams(window.location.search).has("styles")) p.set("styles", "1");
    const qs = p.toString();
    window.history.replaceState(null, "", qs ? `/?${qs}` : "/");
  }, [q, filter, type]);

  async function load() {
    try {
      const res = await apiFetch("/api/objects");
      if (res.status === 401) { setAuthRequired(true); return; }
      if (!res.ok) throw new Error(String(res.status));
      setProjects(await res.json());
      setLoadError(false);
    } catch {
      setLoadError(true);
      setProjects((cur) => cur ?? []);
    }
  }

  const types = useMemo(
    () => OBJECT_TYPES.filter((t) => projects?.some((p) => p.type === t.name)),
    [projects],
  );

  const visible = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return (projects ?? []).filter((p) => {
      if (filter === "violations" && p.warnings_open === 0) return false;
      if (filter === "clean" && p.warnings_open > 0) return false;
      if (type && p.type !== type) return false;
      if (!needle) return true;
      return [p.name, p.address, p.district, p.type, p.stage?.name ?? ""]
        .some((v) => v.toLowerCase().includes(needle));
    });
  }, [projects, q, filter, type]);

  const totals = useMemo(() => {
    const list = projects ?? [];
    const last = list.map((p) => p.last_snapshot).filter(Boolean).sort().at(-1) ?? null;
    return {
      projects: list.length,
      violations: list.reduce((s, p) => s + p.warnings_open, 0),
      reviews: list.reduce((s, p) => s + p.reviews_open, 0),
      snapshots: list.reduce((s, p) => s + p.snapshots, 0),
      last,
    };
  }, [projects]);


  if (authRequired) {
    return <Login onDone={() => { setAuthRequired(false); load(); }} />;
  }

  const filtersActive = q || filter !== "all" || type;

  const shared = { projects, visible, totals, loadError, filtersActive, onRetry: load, onNew: () => setSheetOpen(true) };

  return (
    <main className={`page v-${theme}`}>
      <NavBar
        title="Объекты"
        right={
          <button className="icon-btn tinted" onClick={() => setSheetOpen(true)} aria-label="Новый объект">
            <IconPlus size={20} />
          </button>
        }
      />

      <div className="content">
        {theme === "ios" ? (
          <>
            <div className="large-title">
              <div className="lt-date">{todayTitle()}</div>
              <h1>Объекты<span className="accent-dot">.</span></h1>
            </div>
            <section className="widgets" aria-label="Сводка">
              <Widget tint="blue" icon={<IconBuilding size={18} />} label="Объекты"
                value={projects ? totals.projects : "—"} />
              <Widget tint="red" icon={<IconWarning size={18} />} label="Сигналы о риске"
                value={projects ? totals.violations : "—"}>
                {projects && <div className="mini-bars" aria-hidden="true">
                  {(projects ?? []).map((p) => (
                    <i key={p.id} title={p.name}
                      style={{ height: `${Math.max(8, (p.warnings_open / Math.max(1, totals.violations)) * 100)}%` }}
                      className={p.warnings_open ? "" : "zero"} />
                  ))}
                </div>}
              </Widget>
              <Widget tint="orange" icon={<IconEye size={18} />} label="Неуверенные сигналы"
                value={projects ? totals.reviews : "—"} />
              <Widget tint="teal" icon={<IconCamera size={18} />} label="Снимки"
                value={projects ? totals.snapshots : "—"} />
            </section>
            <div className="toolbar">
              <label className="search">
                <IconSearch size={17} />
                <input type="search" value={q} onChange={(e) => setQ(e.target.value)}
                  placeholder="Поиск по названию, адресу, этапу" aria-label="Поиск объектов" />
                {q && (
                  <button className="search-clear" onClick={() => setQ("")} aria-label="Очистить поиск">
                    <IconClose size={12} />
                  </button>
                )}
              </label>
              <div className="segmented" role="tablist" aria-label="Фильтр по сигналам">
                {FILTERS.map((f) => (
                  <button key={f.id} role="tab" aria-selected={filter === f.id}
                    className={filter === f.id ? "on" : ""} onClick={() => setFilter(f.id)}>
                    {f.label}
                  </button>
                ))}
              </div>
            </div>
            {types.length > 1 && (
              <div className="chips" role="group" aria-label="Тип объекта">
                <button className={`chip-btn ${type === "" ? "on" : ""}`} onClick={() => setType("")}>Все типы</button>
                {types.map((t) => (
                  <button key={t.name} className={`chip-btn ${type === t.name ? "on" : ""}`}
                    onClick={() => setType(type === t.name ? "" : t.name)}>
                    <i className={`dot tint-${t.tint}`} />{t.name}
                  </button>
                ))}
              </div>
            )}
          </>
        ) : (
          <ListHeader theme={theme} q={q} setQ={setQ} filter={filter} setFilter={setFilter}
            types={types} type={type} setType={setType} totals={totals} />
        )}

        {loadError && (
          <div className="banner error" role="alert">
            <IconWarning size={18} />
            <span>Не удалось загрузить объекты. Проверьте, что API запущен.</span>
            <button className="btn-plain" onClick={load}>Повторить</button>
          </div>
        )}

        {projects === null ? (
          <div className="grid">
            {[0, 1, 2].map((i) => <div key={i} className="project skeleton" />)}
          </div>
        ) : visible.length === 0 ? (
          <div className="empty-state">
            <div className="empty-ic"><IconSearch size={26} /></div>
            <h3>{projects.length === 0 ? "Объектов пока нет" : "Ничего не найдено"}</h3>
            <p>{projects.length === 0
              ? "Создайте первый объект, чтобы загрузить снимки и задать план работ."
              : "Измените запрос или сбросьте фильтры."}</p>
            {projects.length === 0 ? (
              <button className="btn" onClick={() => setSheetOpen(true)}><IconPlus size={16} /> Новый объект</button>
            ) : (
              <button className="btn tinted" onClick={() => { setQ(""); setFilter("all"); setType(""); }}>Сбросить фильтры</button>
            )}
          </div>
        ) : theme === "tech" ? (
          <RegistryView list={visible} />
        ) : theme === "city" ? (
          <BoardView list={visible} />
        ) : theme === "ops" ? (
          <OpsView list={visible} totals={totals} />
        ) : theme === "construct" ? (
          <PosterView list={visible} />
        ) : (
          <>
            {!filtersActive && <AttentionSlider list={visible} />}
            <div className="grid">
              {visible.map((p, i) => <ProjectCard key={p.id} p={p} index={i} />)}
            </div>
          </>
        )}

      </div>

      {sheetOpen && <NewProjectSheet onClose={() => setSheetOpen(false)} />}
    </main>
  );
}

type Shared = {
  projects: Project[] | null;
  visible: Project[];
  totals: { projects: number; violations: number; reviews: number; snapshots: number; last: string | null };
  loadError: boolean;
  filtersActive: boolean | string;
  onRetry: () => void;
  onNew: () => void;
};

/** Own page top for the four non-iOS identities. */
function ListHeader({ theme, q, setQ, filter, setFilter, types, type, setType, totals }: {
  theme: string;
  q: string; setQ: (v: string) => void;
  filter: Filter; setFilter: (f: Filter) => void;
  types: { name: string; tint: string }[];
  type: string; setType: (t: string) => void;
  totals: Shared["totals"];
}) {
  if (theme === "tech") {
    return (
      <div className="reg-head">
        <div className="reg-stamp">
          <span className="reg-stamp-no">ФОРМА БВ-01</span>
          <span>РЕЕСТР ОБЪЕКТОВ СТРОЙКОНТРОЛЯ</span>
          <span className="reg-stamp-date">{todayTitle().toUpperCase()} · ОБЪЕКТОВ: {totals.projects}</span>
        </div>
        <div className="toolbar">
          <label className="search">
            <IconSearch size={17} />
            <input type="search" value={q} onChange={(e) => setQ(e.target.value)}
              placeholder="Поиск по реестру" aria-label="Поиск объектов" />
          </label>
          <div className="segmented">
            {FILTERS.map((f) => (
              <button key={f.id} className={filter === f.id ? "on" : ""} onClick={() => setFilter(f.id)}>{f.label}</button>
            ))}
          </div>
        </div>
      </div>
    );
  }
  if (theme === "city") {
    return (
      <div className="board-head">
        <h1>Объекты</h1>
        <p className="board-sub">{totals.projects} объектов · {totals.violations} сигналов о риске · обновлено {shortDate(totals.last)}</p>
        <div className="board-lines">
          {types.map((t) => (
            <button key={t.name} className={`line-chip ${type === t.name ? "on" : ""}`} onClick={() => setType(type === t.name ? "" : t.name)}>
              <i className={`dot tint-${t.tint}`} />{t.name}
            </button>
          ))}
        </div>
      </div>
    );
  }
  if (theme === "ops") {
    return (
      <div className="ops-head">
        <div className="ops-strip">
          <span>ОБЪЕКТЫ <b>{totals.projects}</b></span>
          <span>СИГНАЛЫ <b className="ops-red">{totals.violations}</b></span>
          <span>НЕУВЕРЕННЫЕ <b className="ops-amber">{totals.reviews}</b></span>
          <span>СНИМКИ <b>{totals.snapshots}</b></span>
        </div>
        <div className="toolbar">
          <label className="search">
            <IconSearch size={17} />
            <input type="search" value={q} onChange={(e) => setQ(e.target.value)}
              placeholder="FILTER" aria-label="Поиск объектов" />
          </label>
          <div className="segmented">
            {FILTERS.map((f) => (
              <button key={f.id} className={filter === f.id ? "on" : ""} onClick={() => setFilter(f.id)}>{f.label.toUpperCase()}</button>
            ))}
          </div>
        </div>
      </div>
    );
  }
  // construct
  return (
    <div className="poster-head">
      <h1>Стройка<br />под контролем</h1>
      <div className="poster-sub">
        <span className="poster-badge">{totals.violations}</span>
        <span>сигналов<br />на {totals.projects} объектах</span>
      </div>
    </div>
  );
}

/* ─── «Техпаспорт»: реестр объектов (таблица БВ-01) ─── */
function RegistryView({ list }: { list: Project[] }) {
  return (
    <div className="reg" role="table" aria-label="Реестр объектов">
      <div className="reg-row reg-cols" aria-hidden="true">
        <span>№</span><span>Объект</span><span>Тип</span><span>Этап</span>
        <span>Время плана</span><span>Сигналы</span><span>Снимки</span>
      </div>
      {list.map((p, i) => (
        <Link className="reg-row" href={`/objects/${p.id}`} key={p.id}>
          <span className="mono">{String(i + 1).padStart(2, "0")}</span>
          <span className="reg-name"><b>{p.name}</b><small>{[p.district, p.address].filter(Boolean).join(" · ")}</small></span>
          <span className="reg-type">{p.type}</span>
          <span className="reg-stage">{p.stage ? `${p.stage.position}/${p.stages_total} · ${p.stage.name}` : "план не задан"}</span>
          <span className="reg-prog"><span className="bar"><i style={{ width: `${p.progress * 100}%` }} /></span><b className="mono">{Math.round(p.progress * 100)}%</b></span>
          <span className={`reg-warn ${p.warnings_open ? "bad" : "ok"}`}>
            {p.warnings_open ? `${p.warnings_open}` : "—"}
            {p.reviews_open > 0 && <small> +{p.reviews_open}</small>}
          </span>
          <span className="mono">{p.snapshots}</span>
        </Link>
      ))}
    </div>
  );
}

/* ─── «Городская операционная»: табло линий по округам ─── */
function BoardView({ list }: { list: Project[] }) {
  const groups = useMemo(() => {
    const m = new Map<string, Project[]>();
    for (const p of list) {
      const k = p.district || "Округ не указан";
      m.set(k, [...(m.get(k) ?? []), p]);
    }
    return [...m.entries()];
  }, [list]);
  return (
    <div className="board">
      {groups.map(([district, items]) => (
        <section className="line-group" key={district}>
          <h3 className="line-title"><i className="line-badge" />{district}</h3>
          {items.map((p) => (
            <Link className="line-row" href={`/objects/${p.id}`} key={p.id}>
              <i className={`dot tint-${typeTint(p.type)}`} />
              <span className="line-name">{p.name}</span>
              <span className="line-stage">{p.stage ? p.stage.name : "план не задан"}</span>
              <span className={`line-status ${p.warnings_open ? "bad" : p.reviews_open ? "warn" : "ok"}`}>
                {p.warnings_open ? `${p.warnings_open} ${plural(p.warnings_open, ["сигнал", "сигнала", "сигналов"])}` : p.reviews_open ? `${p.reviews_open} на проверке` : "без сигналов"}
              </span>
              <span className="line-next">{p.last_snapshot ? `снимок ${shortDate(p.last_snapshot)}` : "нет снимков"}</span>
              <IconChevronRight size={15} />
            </Link>
          ))}
        </section>
      ))}
    </div>
  );
}

/* ─── «Командный центр»: плотная операционная таблица ─── */
function OpsView({ list, totals }: { list: Project[]; totals: Shared["totals"] }) {
  return (
    <div className="ops" role="table" aria-label="Сводка по объектам">
      <div className="ops-meta mono">
        {totals.violations} ОТКРЫТЫХ СИГНАЛОВ · {totals.snapshots} СНИМКОВ · СОРТИРОВКА: СТАТУС
      </div>
      <div className="ops-scroll">
        <table className="ops-table mono">
          <thead>
            <tr><th>Объект</th><th>Тип</th><th>Этап</th><th>Время плана</th><th>Сигн.</th><th>Неувер.</th><th>Снимки</th><th>Статус</th></tr>
          </thead>
          <tbody>
            {list.map((p) => (
              <tr key={p.id} data-warn={p.warnings_open > 0 ? "1" : undefined}>
                <td><Link href={`/objects/${p.id}`} className="ops-link">{p.name}</Link></td>
                <td>{p.type}</td>
                <td>{p.stage ? p.stage.name : "—"}</td>
                <td>{Math.round(p.progress * 100)}%</td>
                <td className={p.warnings_open ? "ops-red" : ""}>{p.warnings_open || "0"}</td>
                <td className={p.reviews_open ? "ops-amber" : ""}>{p.reviews_open || "0"}</td>
                <td>{p.snapshots}</td>
                <td><span className={`ops-tag ${p.warnings_open ? "bad" : "ok"}`}>{p.warnings_open ? "СИГНАЛ" : "НЕТ СИГНАЛОВ"}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ─── «Конструктивизм»: плакат + список-полосы ─── */
function PosterView({ list }: { list: Project[] }) {
  const feat = [...list].sort((a, b) => b.warnings_open - a.warnings_open)[0] ?? list[0];
  const rest = list.filter((p) => p.id !== feat.id);
  return (
    <div className="poster">
      <Link className="poster-hero" href={`/objects/${feat.id}`}>
        {feat.cover && <img src={feat.cover} alt="" />}
        <div className="poster-ov" />
        <div className="poster-txt">
          <span className="poster-kicker">{feat.type} · {feat.district || "МОСКВА"}</span>
          <h2>{feat.name}</h2>
          <p>{feat.warnings_open > 0
            ? `${feat.warnings_open} ${plural(feat.warnings_open, ["сигнал", "сигнала", "сигналов"])} требуют проверки. Этап: ${feat.stage?.name ?? "—"}.`
            : "Сигналов на снимках нет. Этап: " + (feat.stage?.name ?? "—") + "."}</p>
          <span className="poster-cta">Смотреть объект →</span>
        </div>
        <i className="poster-circle" />
      </Link>
      <div className="strips">
        {rest.map((p, i) => (
          <Link className="strip" href={`/objects/${p.id}`} key={p.id}>
            <span className="mono">{String(i + 1).padStart(2, "0")}</span>
            <span className="strip-name">{p.name}</span>
            <span className="strip-stage">{p.stage ? p.stage.name : "—"}</span>
            <span className={`strip-status ${p.warnings_open ? "bad" : "ok"}`}>{p.warnings_open || "✓"}</span>
          </Link>
        ))}
      </div>
    </div>
  );
}

function Widget({ tint, icon, label, value, children }: {
  tint: string; icon: React.ReactNode; label: string; value: number | string;
  children?: React.ReactNode;
}) {
  return (
    <div className="widget">
      <div className="w-top">
        <span className={`sq tint-${tint}`}>{icon}</span>
        <span className="w-label">{label}</span>
      </div>
      <div className="w-value">{value}</div>
      {children}
    </div>
  );
}

/** «Стоит проверить»: slider of projects that need attention right now. */
function AttentionSlider({ list }: { list: Project[] }) {
  const ref = useRef<HTMLDivElement>(null);
  const [idx, setIdx] = useState(0);

  const items = useMemo(() => [...list]
    .filter((p) => p.warnings_open > 0 || p.reviews_open > 0)
    .sort((a, b) =>
      b.warnings_open - a.warnings_open || b.reviews_open - a.reviews_open)
    .slice(0, 5), [list]);

  const onScroll = () => {
    const el = ref.current;
    if (!el || el.children.length < 2) return;
    const first = el.children[0] as HTMLElement;
    const step = first.offsetWidth + 18;
    setIdx(Math.max(0, Math.min(items.length - 1, Math.round(el.scrollLeft / step))));
  };

  const go = (dir: 1 | -1) => {
    const el = ref.current;
    if (!el) return;
    const first = el.children[0] as HTMLElement;
    el.scrollBy({ left: dir * (first.offsetWidth + 18), behavior: "smooth" });
  };

  const jump = (i: number) => {
    const el = ref.current;
    if (!el) return;
    const child = el.children[i] as HTMLElement | undefined;
    if (child) el.scrollTo({ left: child.offsetLeft - el.offsetLeft, behavior: "smooth" });
  };

  if (items.length === 0) return null;

  return (
    <section className="att" aria-label="Стоит проверить">
      <div className="att-head">
        <h2>Стоит проверить</h2>
        {items.length > 1 && (
          <div className="att-nav">
            <button className="icon-btn" onClick={() => go(-1)} disabled={idx === 0} aria-label="Предыдущий объект">
              <IconChevronRight size={17} style={{ transform: "rotate(180deg)" }} />
            </button>
            <button className="icon-btn" onClick={() => go(1)} disabled={idx === items.length - 1} aria-label="Следующий объект">
              <IconChevronRight size={17} />
            </button>
          </div>
        )}
      </div>
      <div className="att-scroll" ref={ref} onScroll={onScroll}>
        {items.map((p) => {
          const pct = Math.round(p.progress * 100);
          return (
            <Link key={p.id} href={`/objects/${p.id}`} className="att-card" aria-label={`Открыть объект ${p.name}`}>
              {p.cover && <img src={p.cover} alt="" loading="lazy" />}
              <div className="att-ov" />
              <div className="att-top">
                <span className="glass-pill att-flag alert">
                  <IconWarning size={14} />
                  {p.warnings_open} {plural(p.warnings_open, ["сигнал", "сигнала", "сигналов"])}
                </span>
                <span className="glass-pill"><i className={`dot tint-${typeTint(p.type)}`} />{p.type}</span>
              </div>
              <div className="att-body">
                <h3>{p.name}</h3>
                <div className="att-meta">
                  {p.district && <span className="fm"><IconPin size={14} />{p.district}</span>}
                  {p.stage && <span className="fm">Этап {p.stage.position}/{p.stages_total} · {p.stage.name}</span>}
                </div>
                <div className="att-foot">
                  <div className="bar"><i style={{ width: `${Math.max(4, pct)}%` }} /></div>
                  <span className="att-pct">{pct}%</span>
                </div>
              </div>
            </Link>
          );
        })}
      </div>
      {items.length > 1 && (
        <div className="att-dots" role="tablist" aria-label="Слайды">
          {items.map((p, i) => (
            <button key={p.id} role="tab" aria-selected={idx === i}
              className={`att-dot ${idx === i ? "on" : ""}`} onClick={() => jump(i)}
              aria-label={`Слайд ${i + 1}`} />
          ))}
        </div>
      )}
    </section>
  );
}

function Ring({ value, size = 38 }: { value: number; size?: number }) {
  const r = (size - 5) / 2;
  const c = 2 * Math.PI * r;
  const cssVars = { "--c": `${c}`, "--v": `${c * (1 - value)}` } as React.CSSProperties;
  return (
    <svg className="ring" width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
      <circle cx={size / 2} cy={size / 2} r={r} className="ring-track" />
      <circle cx={size / 2} cy={size / 2} r={r} className="ring-value" style={cssVars}
        strokeDasharray={c} strokeDashoffset={c * (1 - value)}
        transform={`rotate(-90 ${size / 2} ${size / 2})`} />
    </svg>
  );
}

function StatusBadge({ p }: { p: Project }) {
  if (p.snapshots === 0) return <span className="status gray">Нет снимков</span>;
  if (p.warnings_open > 0 && p.warnings_open === p.reviews_open) {
    return <span className="status orange"><i />{p.warnings_open} {plural(p.warnings_open, ["сигнал", "сигнала", "сигналов"])} с низкой уверенностью</span>;
  }
  if (p.warnings_open > 0) {
    return <span className="status red"><i />{p.warnings_open} {plural(p.warnings_open, ["сигнал", "сигнала", "сигналов"])}</span>;
  }
  return <span className="status green"><i />Без сигналов на снимках</span>;
}

function ProjectCard({ p, index }: { p: Project; index: number }) {
  const tint = typeTint(p.type);
  const equipment = equipmentList(p.equipment);
  const pct = Math.round(p.progress * 100);
  return (
    <Link href={`/objects/${p.id}`} className="project" style={{ animationDelay: `${index * 60}ms` }}>
      <div className={`cover tint-bg-${tint}`}>
        {p.cover ? <img src={p.cover} alt="" loading="lazy" /> : <IconBuilding size={44} />}
        <div className="cover-top">
          <span className="glass-pill"><i className={`dot tint-${tint}`} />{p.type}</span>
          <StatusBadge p={p} />
        </div>
      </div>
      <div className="p-body">
        <div className="p-head">
          <div className="p-title">
            <h3>{p.name}</h3>
            <div className="p-addr">
              <IconPin size={14} />
              <span>{[p.district, p.address].filter(Boolean).join(" · ") || "Адрес не указан"}</span>
            </div>
          </div>
          <div className="p-ring" title={`Прошло времени по плану: ${pct}%`} aria-label={`Прошло времени по плану: ${pct}%`}>
            <Ring value={p.progress} />
            <span>{pct}%</span>
          </div>
        </div>

        {p.stage ? (
          <div className="p-stage">
            <div className="p-stage-row">
              <span className="p-stage-label">Этап {p.stage.position} из {p.stages_total}</span>
              <span className="p-stage-due">до {shortDate(p.stage.date_to)}</span>
            </div>
            <div className="p-stage-name">{p.stage.name}</div>
            <div className="bar"><i style={{ width: `${Math.max(4, p.stage.progress * 100)}%` }} /></div>
          </div>
        ) : (
          <div className="p-stage muted">План работ ещё не задан</div>
        )}

        <div className="p-foot">
          <span className="p-meta"><IconCalendar size={14} />{p.last_snapshot ? `Снимок ${shortDate(p.last_snapshot)}` : "Снимков нет"}</span>
          {equipment.length > 0 && (
            <span className="p-meta p-equip" title={equipment.join(", ")}>
              <IconTruck size={14} />
              {equipment.slice(0, 2).join(", ")}{equipment.length > 2 ? ` +${equipment.length - 2}` : ""}
            </span>
          )}
          <IconChevronRight size={16} className="p-chev" />
        </div>
      </div>
    </Link>
  );
}

function NewProjectSheet({ onClose }: { onClose: () => void }) {
  const router = useRouter();
  const [name, setName] = useState("");
  const [type, setType] = useState(OBJECT_TYPES[0].name);
  const [district, setDistrict] = useState("");
  const [address, setAddress] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setBusy(true); setError("");
    const body = new FormData();
    body.set("name", name.trim()); body.set("type", type);
    body.set("district", district); body.set("address", address.trim());
    const res = await apiFetch("/api/objects", { method: "POST", body });
    if (res.ok) {
      const { id } = await res.json();
      router.push(`/objects/${id}`);
    } else {
      setError("Не удалось создать объект. Попробуйте ещё раз.");
      setBusy(false);
    }
  }

  return (
    <div className="sheet-back" onClick={onClose}>
      <form className="sheet" onClick={(e) => e.stopPropagation()} onSubmit={submit}
        role="dialog" aria-modal="true" aria-labelledby="new-project-title">
        <div className="sheet-grabber" />
        <div className="sheet-head">
          <button type="button" className="btn-plain" onClick={onClose}>Отменить</button>
          <h2 id="new-project-title">Новый объект</h2>
          <button className="btn-plain strong" disabled={busy || !name.trim()}>{busy ? "…" : "Создать"}</button>
        </div>
        <div className="form-group">
          <label className="form-row">
            <span>Название</span>
            <input autoFocus required value={name} onChange={(e) => setName(e.target.value)} placeholder="ЖК «Пример», корп. 1" />
          </label>
          <label className="form-row">
            <span>Тип</span>
            <select value={type} onChange={(e) => setType(e.target.value)}>
              {OBJECT_TYPES.map((t) => <option key={t.name}>{t.name}</option>)}
            </select>
          </label>
        </div>
        <div className="form-group">
          <label className="form-row">
            <span>Округ</span>
            <select value={district} onChange={(e) => setDistrict(e.target.value)}>
              <option value="">Не указан</option>
              {DISTRICTS.map((d) => <option key={d}>{d}</option>)}
            </select>
          </label>
          <label className="form-row">
            <span>Адрес</span>
            <input value={address} onChange={(e) => setAddress(e.target.value)} placeholder="ул. Примерная, вл. 1" />
          </label>
        </div>
        <p className="form-note">Тип определяет перечень видов работ из справочника ЛТЦ. План этапов и снимки добавляются на странице объекта.</p>
        {error && <div className="banner error" role="alert"><IconWarning size={18} /><span>{error}</span></div>}
      </form>
    </div>
  );
}

function Login({ onDone }: { onDone: () => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <main className="login-page">
      <form className="login-card" onSubmit={async (e) => {
        e.preventDefault(); setError(""); setBusy(true);
        const body = new FormData(); body.set("email", email); body.set("password", password);
        const r = await apiFetch("/api/auth/login", { method: "POST", body });
        setBusy(false);
        if (r.ok) { saveToken((await r.json()).access_token); onDone(); }
        else setError("Неверный email или пароль");
      }}>
        <span className="login-logo"><IconBuilding size={30} /></span>
        <h1>BuildWatch</h1>
        <p>Войдите, чтобы просматривать объекты и предупреждения.</p>
        <div className="form-group">
          <label className="form-row"><span>Email</span>
            <input type="email" required autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="name@mos.ru" /></label>
          <label className="form-row"><span>Пароль</span>
            <input type="password" required autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Обязательно" /></label>
        </div>
        {error && <div className="login-error" role="alert">{error}</div>}
        <button className="btn wide" disabled={busy}>{busy ? "Вход…" : "Войти"}</button>
      </form>
    </main>
  );
}
