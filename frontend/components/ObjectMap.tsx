"use client";

import Link from "next/link";
import { IconArrowUpRight, IconPin, IconWarning } from "@/components/Icons";

type MapProject = {
  id: number;
  name: string;
  type: string;
  district: string;
  address: string;
  snapshots: number;
  warnings_open: number;
  reviews_open: number;
  progress: number;
  last_snapshot: string | null;
  stage: { name: string; position: number; progress: number } | null;
  stages_total: number;
};

type ObjectMapProps = {
  projects: MapProject[];
  selectedId: number | null;
  onSelect: (id: number) => void;
};

const DISTRICT_POSITIONS: Record<string, [number, number]> = {
  САО: [48, 25],
  ЮЗАО: [34, 62],
  ВАО: [73, 49],
  ЗелАО: [12, 36],
  СЗАО: [28, 27],
  НАО: [43, 83],
  ЦАО: [52, 48],
  ЮАО: [58, 73],
};

const DISTRICT_LABELS = [
  ["СЗАО", 23, 19], ["САО", 51, 14], ["ВАО", 82, 44],
  ["ЮЗАО", 26, 68], ["ЦАО", 52, 42], ["ЮАО", 63, 82],
  ["НАО", 35, 93], ["ЗелАО", 8, 29],
] as const;

function offsetFor(id: number, index: number): [number, number] {
  const angle = (id * 41 + index * 73) * Math.PI / 180;
  return [Math.cos(angle) * 2.6, Math.sin(angle) * 2.6];
}

function positionFor(project: MapProject, index: number): [number, number] {
  const [baseX, baseY] = DISTRICT_POSITIONS[project.district] ?? [48, 48];
  const [offsetX, offsetY] = offsetFor(project.id, index);
  return [Math.max(7, Math.min(93, baseX + offsetX)), Math.max(9, Math.min(91, baseY + offsetY))];
}

function statusFor(project: MapProject) {
  if (project.warnings_open > 0) return { className: "danger", label: "Есть сигналы" };
  if (project.reviews_open > 0) return { className: "review", label: "Нужна проверка" };
  return { className: "clear", label: "Без открытых сигналов" };
}

function shortDate(value: string | null) {
  if (!value) return "—";
  const [year, month, day] = value.slice(0, 10).split("-");
  return `${day}.${month}.${year}`;
}

export function ObjectMap({ projects, selectedId, onSelect }: ObjectMapProps) {
  const selected = projects.find((project) => project.id === selectedId) ?? null;
  const selectedStatus = selected ? statusFor(selected) : null;

  return (
    <section className="object-map" aria-label="Объекты на карте Москвы">
      <div className="map-head">
        <div>
          <span className="map-kicker">ПОРТФЕЛЬ / МОСКВА</span>
          <h2>Объекты на карте</h2>
        </div>
        <div className="map-legend" aria-label="Легенда состояний">
          <span><i className="map-dot danger" />Сигналы</span>
          <span><i className="map-dot review" />Проверка</span>
          <span><i className="map-dot clear" />Норма</span>
        </div>
      </div>

      <div className="map-layout">
        <div className="map-canvas">
          <svg className="map-surface" viewBox="0 0 100 100" role="img" aria-label="Схематичная карта Москвы">
            <path className="map-ring" d="M14 36 C22 12 47 7 67 17 C87 27 91 53 82 72 C72 93 47 96 27 84 C10 74 6 53 14 36Z" />
            <path className="map-ring inner" d="M27 40 C33 23 51 17 66 25 C79 32 82 50 75 64 C67 80 49 84 35 75 C22 67 21 52 27 40Z" />
            <path className="map-road" d="M8 54 C26 49 36 52 49 49 S75 42 93 47" />
            <path className="map-road" d="M37 6 C42 25 48 38 51 49 S57 76 61 96" />
            <path className="map-road minor" d="M13 75 C32 64 45 59 64 61 S82 71 91 84" />
            <path className="map-road minor" d="M21 22 C32 35 41 42 51 49 S69 57 84 63" />
            {DISTRICT_LABELS.map(([label, x, y]) => <text key={label} x={x} y={y} className="map-district">{label}</text>)}
            <text x="50" y="52" className="map-city">МОСКВА</text>
          </svg>

          <div className="map-markers">
            {projects.map((project, index) => {
              const [x, y] = positionFor(project, index);
              const status = statusFor(project);
              const selectedMarker = project.id === selectedId;
              return (
                <button
                  key={project.id}
                  type="button"
                  className={`map-marker ${status.className} ${selectedMarker ? "selected" : ""}`}
                  style={{ left: `${x}%`, top: `${y}%` }}
                  onClick={() => onSelect(project.id)}
                  aria-label={`${project.name}. ${status.label}. ${project.warnings_open} сигналов`}
                  aria-pressed={selectedMarker}
                >
                  <span>{project.warnings_open || project.reviews_open || "✓"}</span>
                </button>
              );
            })}
          </div>
          <span className="map-scale">Схема районов · точки по округам</span>
        </div>

        <aside className="map-details" aria-live="polite">
          {selected && selectedStatus ? (
            <>
              <div className={`map-status ${selectedStatus.className}`}>
                <i className="map-dot" />{selectedStatus.label}
              </div>
              <h3>{selected.name}</h3>
              <p className="map-address"><IconPin size={15} />{selected.district} · {selected.address}</p>
              <div className="map-facts">
                <div><span>Текущий этап</span><strong>{selected.stage?.name ?? "Не задан"}</strong></div>
                <div><span>Прогресс по плану</span><strong>{Math.round(selected.progress * 100)}%</strong></div>
                <div><span>Сигналы</span><strong className={selected.warnings_open ? "is-danger" : ""}><IconWarning size={14} />{selected.warnings_open}</strong></div>
                <div><span>Последний снимок</span><strong>{shortDate(selected.last_snapshot)}</strong></div>
              </div>
              <Link className="map-open" href={`/objects/${selected.id}`}>
                Открыть объект <IconArrowUpRight size={16} />
              </Link>
            </>
          ) : (
            <div className="map-empty">
              <span className="map-empty-mark"><IconPin size={20} /></span>
              <h3>Выберите объект</h3>
              <p>Нажмите на маркер, чтобы увидеть текущий этап, прогресс и сигналы.</p>
            </div>
          )}
        </aside>
      </div>
    </section>
  );
}
