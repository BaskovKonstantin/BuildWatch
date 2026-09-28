"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import type { LayerGroup, Map as LeafletMap, Marker } from "leaflet";
import {
  IconArrowUpRight, IconBuilding, IconEye, IconPin, IconWarning,
} from "@/components/Icons";
import { apiFetch } from "@/lib/api";
import { equipmentRu } from "@/lib/format";

type MapProject = {
  id: number;
  name: string;
  type: string;
  district: string;
  address: string;
  snapshots: number;
  violations_open: number;
  reviews_open: number;
  progress: number;
  last_snapshot: string | null;
  stage: { name: string; position: number; progress: number } | null;
  stages_total: number;
};

type MapTotals = { projects: number; violations: number; reviews: number; snapshots: number };
type MapComment = { id: number; body: string; created_at: string };
type MapDetection = { id: number; label: string; score: number; match: "ok" | "mismatch" | "review" };
type MapSnapshot = { id: number; filename: string; captured_at: string; detections: MapDetection[] };
type MapRequirement = { name: string; classes: string[] };
type MapWarning = {
  id: number;
  snapshot_id: number;
  title: string;
  body: string;
  why: string;
  status: string;
  severity: string;
  captured_at: string | null;
  snapshot_filename: string | null;
};
type MapCard = {
  stages: { id: number; name: string; kind: string; position: number; date_from: string; date_to: string }[];
  stage_requirements: Record<string, MapRequirement[]>;
  snapshots: MapSnapshot[];
  warnings: MapWarning[];
};
type FeedSection = "objects" | "danger" | "review";

type ObjectMapProps = {
  projects: MapProject[];
  totals: MapTotals;
  selectedId: number | null;
  onSelect: (id: number) => void;
};

const DISTRICT_COORDINATES: Record<string, [number, number]> = {
  САО: [55.896, 37.545], ЮЗАО: [55.649, 37.526], ВАО: [55.793, 37.799],
  ЗелАО: [55.991, 37.207], СЗАО: [55.83, 37.43], НАО: [55.568, 37.483],
  ЦАО: [55.7558, 37.6173], ЮАО: [55.67, 37.64],
};
const MOSCOW_CENTER: [number, number] = [55.7558, 37.6173];
const OSM_TILE_URL = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";

function coordinatesFor(project: MapProject, ordinal = 0, total = 1): [number, number] {
  const [baseLat, baseLng] = DISTRICT_COORDINATES[project.district] ?? MOSCOW_CENTER;
  if (total <= 1) return [baseLat, baseLng];
  const ringSize = Math.min(total, 8);
  const ring = Math.floor(ordinal / ringSize);
  const angle = -Math.PI / 2 + (ordinal % ringSize) * ((Math.PI * 2) / ringSize) + ring * 0.22;
  const radius = 0.0035 + ring * 0.0022;
  const longitudeRadius = radius / Math.max(0.2, Math.cos(baseLat * Math.PI / 180));
  return [baseLat + Math.sin(angle) * radius, baseLng + Math.cos(angle) * longitudeRadius];
}

function buildCoordinates(projects: MapProject[]) {
  const groups = new Map<string, MapProject[]>();
  projects.forEach((project) => {
    const group = groups.get(project.district) ?? [];
    group.push(project);
    groups.set(project.district, group);
  });
  const coordinates = new Map<number, [number, number]>();
  groups.forEach((group) => {
    group.sort((a, b) => a.id - b.id).forEach((project, ordinal) => {
      coordinates.set(project.id, coordinatesFor(project, ordinal, group.length));
    });
  });
  return coordinates;
}

function shortDate(value: string | null) {
  if (!value) return "—";
  const [year, month, day] = value.slice(0, 10).split("-");
  return `${day}.${month}.${year}`;
}

function statusFor(project: MapProject) {
  if (project.violations_open > 0) return { className: "danger", label: "Есть проблемы" };
  if (project.reviews_open > 0) return { className: "review", label: "Требует внимания" };
  return { className: "clear", label: "Без открытых проблем" };
}

function markerIcon(L: typeof import("leaflet"), project: MapProject, selected: boolean) {
  const status = statusFor(project);
  const count = project.violations_open || project.reviews_open;
  return L.divIcon({
    className: `leaflet-object-marker ${status.className} ${selected ? "selected" : ""}`,
    html: `<span>${count || "✓"}</span>`,
    iconSize: [40, 40],
    iconAnchor: [20, 20],
  });
}

function commentDate(value: string) {
  const date = new Date(value.replace(" ", "T"));
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
  }).format(date);
}

function FeedMetric({
  id, tone, count, label, icon, open, onToggle, children,
}: {
  id: FeedSection;
  tone: string;
  count: number;
  label: string;
  icon: ReactNode;
  open: boolean;
  onToggle: () => void;
  children: ReactNode;
}) {
  const panelId = `portfolio-feed-${id}`;
  return (
    <div className={`map-feed-group ${tone} ${open ? "open" : ""}`}>
      <button className="map-feed-item" type="button" aria-expanded={open} aria-controls={panelId} onClick={onToggle}>
        <span className="map-feed-icon">{icon}</span>
        <span className="map-feed-value"><b>{count}</b><span>{label}</span></span>
        <span className="map-feed-chevron" aria-hidden="true">⌄</span>
      </button>
      <div className="map-feed-detail" id={panelId} hidden={!open}>
        {children}
      </div>
    </div>
  );
}

export function ObjectMap({ projects, totals, selectedId, onSelect }: ObjectMapProps) {
  const mapElement = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const layerRef = useRef<LayerGroup | null>(null);
  const didFitBoundsRef = useRef(false);
  const leafletRef = useRef<typeof import("leaflet") | null>(null);
  const markersRef = useRef(new Map<number, Marker>());
  const [mapReady, setMapReady] = useState(false);
  const [feedOpen, setFeedOpen] = useState<FeedSection[]>(["objects"]);
  const [issuesOpen, setIssuesOpen] = useState(false);
  const [comments, setComments] = useState<MapComment[]>([]);
  const [commentsLoadedFor, setCommentsLoadedFor] = useState<number | null>(null);
  const [commentsLoading, setCommentsLoading] = useState(false);
  const [commentDraft, setCommentDraft] = useState("");
  const [commentSaving, setCommentSaving] = useState(false);
  const [commentNotice, setCommentNotice] = useState("");
  const [commentError, setCommentError] = useState("");
  const [selectedCard, setSelectedCard] = useState<MapCard | null>(null);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [warningDecisions, setWarningDecisions] = useState<Record<number, "confirm" | "dismiss">>({});
  const [routePending, setRoutePending] = useState(false);
  const coordinates = useMemo(() => buildCoordinates(projects), [projects]);
  const selected = projects.find((project) => project.id === selectedId) ?? null;
  const selectedStatus = selected ? statusFor(selected) : null;
  const problemProjects = projects.filter((project) => project.violations_open > 0);
  const reviewProjects = projects.filter((project) => project.reviews_open > 0);

  useEffect(() => {
    let disposed = false;
    let resizeObserver: ResizeObserver | null = null;
    let sizeTimers: number[] = [];
    if (!mapElement.current) return;
    import("leaflet").then((L) => {
      if (disposed || !mapElement.current || mapRef.current) return;
      leafletRef.current = L;
      const map = L.map(mapElement.current, {
        center: MOSCOW_CENTER,
        zoom: 10,
        minZoom: 9,
        maxZoom: 18,
        zoomControl: true,
        attributionControl: false,
      });
      L.tileLayer(OSM_TILE_URL, { maxZoom: 19, attribution: "" }).addTo(map);
      layerRef.current = L.layerGroup().addTo(map);
      mapRef.current = map;
      setMapReady(true);

      const syncMapSize = () => {
        map.invalidateSize({ pan: false });
      };
      syncMapSize();
      sizeTimers = [0, 50, 150, 400, 1000].map((delay) => window.setTimeout(() => {
        if (!disposed && mapRef.current === map) syncMapSize();
      }, delay));

      if (typeof ResizeObserver !== "undefined" && mapElement.current) {
        resizeObserver = new ResizeObserver(() => {
          if (!disposed && mapRef.current === map) syncMapSize();
        });
        resizeObserver.observe(mapElement.current);
      }
    });
    return () => {
      disposed = true;
      sizeTimers.forEach((timer) => window.clearTimeout(timer));
      resizeObserver?.disconnect();
      markersRef.current.clear();
      mapRef.current?.remove();
      mapRef.current = null;
      layerRef.current = null;
      leafletRef.current = null;
      didFitBoundsRef.current = false;
      setMapReady(false);
    };
  }, []);

  useEffect(() => {
    const L = leafletRef.current;
    const layer = layerRef.current;
    if (!mapReady || !L || !layer) return;
    layer.clearLayers();
    markersRef.current.clear();
    const latLngs: [number, number][] = [];
    projects.forEach((project) => {
      const position = coordinates.get(project.id) ?? coordinatesFor(project);
      latLngs.push(position);
      const marker = L.marker(position, {
        icon: markerIcon(L, project, project.id === selectedId),
        title: project.name,
        alt: `${project.name}, ${statusFor(project).label}`,
      });
      marker.on("click", () => onSelect(project.id));
      marker.addTo(layer);
      markersRef.current.set(project.id, marker);
    });
    const map = mapRef.current;
    if (map && latLngs.length > 0 && !didFitBoundsRef.current) {
      if (latLngs.length === 1) {
        map.setView(latLngs[0], 12);
      } else {
        map.fitBounds(L.latLngBounds(latLngs), { padding: [48, 48], maxZoom: 12 });
      }
      didFitBoundsRef.current = true;
    }
  }, [coordinates, mapReady, projects, selectedId, onSelect]);

  useEffect(() => {
    if (!mapRef.current || !selected) return;
    mapRef.current.panTo(coordinates.get(selected.id) ?? coordinatesFor(selected), { animate: true, duration: 0.35 });
  }, [coordinates, selected]);

  useEffect(() => {
    setIssuesOpen(false);
    setComments([]);
    setCommentsLoadedFor(null);
    setCommentDraft("");
    setCommentNotice("");
    setCommentError("");
  }, [selectedId]);

  useEffect(() => {
    if (selectedId === null) {
      setSelectedCard(null);
      return;
    }
    let active = true;
    setSelectedCard(null);
    setDetailsLoading(true);
    setWarningDecisions({});
    apiFetch(`/api/objects/${selectedId}`)
      .then(async (response) => {
        if (!response.ok) throw new Error("Не удалось загрузить детали объекта");
        const data = await response.json() as MapCard;
        if (active) setSelectedCard(data);
      })
      .catch(() => {
        if (active) setSelectedCard(null);
      })
      .finally(() => {
        if (active) setDetailsLoading(false);
      });
    return () => { active = false; };
  }, [selectedId]);

  function toggleFeed(id: FeedSection) {
    setFeedOpen((current) => current.includes(id)
      ? current.filter((item) => item !== id)
      : [...current, id]);
  }

  async function loadComments(objectId: number) {
    setCommentsLoading(true);
    setCommentError("");
    try {
      const response = await apiFetch(`/api/objects/${objectId}/comments`);
      if (!response.ok) throw new Error("Не удалось загрузить комментарии");
      setComments(await response.json());
      setCommentsLoadedFor(objectId);
    } catch (cause) {
      setCommentError(cause instanceof Error ? cause.message : "Не удалось загрузить комментарии");
    } finally {
      setCommentsLoading(false);
    }
  }

  function toggleIssues() {
    const next = !issuesOpen;
    setIssuesOpen(next);
    if (next && selected && commentsLoadedFor !== selected.id) void loadComments(selected.id);
  }

  async function submitComment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected || !commentDraft.trim() || commentSaving) return;
    setCommentSaving(true);
    setCommentError("");
    try {
      const response = await apiFetch(`/api/objects/${selected.id}/comments`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ body: commentDraft.trim() }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Не удалось сохранить комментарий");
      setComments((current) => [data, ...current]);
      setCommentsLoadedFor(selected.id);
      setCommentDraft("");
      setCommentNotice("Комментарий сохранён");
    } catch (cause) {
      setCommentError(cause instanceof Error ? cause.message : "Не удалось сохранить комментарий");
    } finally {
      setCommentSaving(false);
    }
  }

  async function resolveMapWarning(warningId: number, action: "confirm" | "dismiss") {
    const body = new FormData();
    body.set("action", action);
    const response = await apiFetch(`/api/warnings/${warningId}`, { method: "POST", body });
    if (!response.ok) return;
    setWarningDecisions((current) => ({ ...current, [warningId]: action }));
    setSelectedCard((current) => current ? {
      ...current,
      warnings: current.warnings.map((warning) => warning.id === warningId
        ? { ...warning, status: action === "confirm" ? "confirmed" : "dismissed" }
        : warning),
    } : current);
  }

  function renderProjectList(items: MapProject[], emptyLabel: string) {
    if (!items.length) return <p className="map-feed-empty">{emptyLabel}</p>;
    return (
      <ul className="map-feed-projects">
        {items.map((project) => (
          <li key={project.id}>
            <button type="button" onClick={() => onSelect(project.id)}>
              <span>{project.name}</span>
              <b>{project.violations_open || project.reviews_open || "✓"}</b>
            </button>
          </li>
        ))}
      </ul>
    );
  }

  const latestSnapshot = selectedCard?.snapshots[0] ?? null;
  const factStage = latestSnapshot
    ? selectedCard?.stages.find((stage) => stage.date_from.slice(0, 10) <= latestSnapshot.captured_at.slice(0, 10)
      && latestSnapshot.captured_at.slice(0, 10) <= stage.date_to.slice(0, 10)) ?? null
    : null;
  // Portfolio summaries use one-based stage positions, while the object detail
  // endpoint returns zero-based positions. Normalize before comparing them.
  const planPosition = selected?.stage ? selected.stage.position - 1 : -1;
  const factPosition = factStage?.position ?? -1;
  const planFactTone = !latestSnapshot || !factStage ? "unknown" : factPosition === planPosition ? "match" : "mismatch";
  const currentStage = factStage ?? selectedCard?.stages.find((stage) => stage.position === planPosition) ?? null;
  const currentRequirements = currentStage && selectedCard ? selectedCard.stage_requirements?.[String(currentStage.id)] ?? [] : [];
  const equipmentComparison = (() => {
    if (!latestSnapshot) return [] as { expected: string; actual: string; tone: "match" | "review" | "mismatch" | "unknown"; status: string }[];
    if (currentRequirements.length) {
      return currentRequirements.map((requirement) => {
        const matches = latestSnapshot.detections.filter((detection) => requirement.classes.includes(detection.label));
        const best = matches.slice().sort((a, b) => b.score - a.score)[0];
          const tone = !best ? "review" : best.match === "ok" ? "match" : best.match === "mismatch" ? "mismatch" : "review";
        return {
          expected: requirement.name,
            actual: best ? `${equipmentRu(best.label)} · ${best.score.toFixed(2)}` : "Не видно на снимке",
          tone,
            status: tone === "match" ? "Совпадает" : tone === "mismatch" ? "Проблема" : best ? "Проверка" : "Нужен просмотр",
        };
      });
    }
    const seen = new Set<string>();
    return latestSnapshot.detections.filter((detection) => {
      if (seen.has(detection.label)) return false;
      seen.add(detection.label);
      return true;
    }).map((detection) => ({
      expected: "Правило не задано",
      actual: `${equipmentRu(detection.label)} · ${detection.score.toFixed(2)}`,
      tone: "unknown" as const,
      status: "Нет правила",
    }));
  })();
  const planFactLabel = detailsLoading
    ? "Загрузка факта…"
    : !latestSnapshot
      ? "Нет снимка для сравнения"
      : !factStage
        ? "Снимок вне плана"
        : factPosition === planPosition
          ? "Совпадает с планом"
          : factPosition < planPosition
            ? "Факт отстаёт от плана"
            : "Факт опережает план";
  const mapWarnings = selectedCard?.warnings.filter((warning) => warning.status === "open") ?? [];

  return (
    <section className={`object-map ${routePending ? "is-routing" : ""}`} aria-label="Объекты на карте Москвы" aria-busy={routePending}>
      <div className="map-head">
        <div>
          <span className="map-kicker">ПОРТФЕЛЬ / МОСКВА</span>
          <h2>Объекты на карте</h2>
          <p className="map-osm-credit">
            <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">
              © OpenStreetMap
            </a>
          </p>
        </div>
        <div className="map-legend" aria-label="Легенда состояний">
          <span><i className="map-dot danger" />Проблемы</span><span><i className="map-dot review" />Вопросы</span><span><i className="map-dot clear" />Норма</span>
        </div>
      </div>

      <div className="map-layout">
        <aside className="map-feed" aria-label="Лента состояния портфеля">
          <div className="map-feed-head"><strong>Состояние портфеля</strong><span>Сейчас</span></div>
          <div className="map-feed-list">
            <FeedMetric id="objects" tone="objects" count={totals.projects} label="объектов в мониторинге" icon={<IconBuilding size={17} />} open={feedOpen.includes("objects")} onToggle={() => toggleFeed("objects")}>
              <p className="map-feed-detail-caption">Все объекты текущего портфеля</p>
              {renderProjectList(projects, "В портфеле пока нет объектов")}
            </FeedMetric>
            <FeedMetric id="danger" tone="danger" count={totals.violations} label="открытых проблем" icon={<IconWarning size={17} />} open={feedOpen.includes("danger")} onToggle={() => toggleFeed("danger")}>
              <p className="map-feed-detail-caption">Объекты с несоответствием плану или этапу</p>
              {renderProjectList(problemProjects, "Открытых проблем нет")}
            </FeedMetric>
            <FeedMetric id="review" tone="review" count={totals.reviews} label="вопросов на проверку" icon={<IconEye size={17} />} open={feedOpen.includes("review")} onToggle={() => toggleFeed("review")}>
              <p className="map-feed-detail-caption">Распознавания, которые должен проверить инженер</p>
              {renderProjectList(reviewProjects, "Дополнительных наблюдений нет")}
            </FeedMetric>
          </div>
        </aside>

        <div className="map-canvas" ref={mapElement} />

        <aside className="map-details" aria-live="polite">
          {selected && selectedStatus ? (
            <>
              <div className={`map-status ${selectedStatus.className}`}><i className="map-dot" />{selectedStatus.label}</div>
              <h3>{selected.name}</h3>
              <p className="map-address"><IconPin size={15} />{selected.district} · {selected.address}</p>
              <div className="map-facts">
                <div className={`map-plan-fact ${planFactTone}`}>
                  <div className="map-plan-fact-head"><span>План / факт</span><b>{planFactLabel}</b></div>
                  <div className="map-plan-fact-grid">
                    <div><span>План</span><strong>{selected.stage?.name ?? "Этап не задан"}</strong><small>Этап {selected.stage ? selected.stage.position : "—"} из {selected.stages_total}</small></div>
                    <div><span>Факт на снимке</span><strong>{factStage?.name ?? (latestSnapshot ? "Этап не определён" : "Нет данных")}</strong><small>{latestSnapshot ? shortDate(latestSnapshot.captured_at) : "Выберите снимок"}</small></div>
                  </div>
                  <div className="map-plan-fact-progress"><span>Прогресс</span><strong><b>План {Math.round(selected.progress * 100)}%</b><em>{factStage ? `Факт: этап ${factStage.position + 1} из ${selected.stages_total}` : "Факт: нет данных"}</em></strong><i><b style={{ width: `${Math.round(selected.progress * 100)}%` }} /><em style={{ width: factStage ? `${Math.round(((factStage.position + 1) / Math.max(selected.stages_total, 1)) * 100)}%` : "0%" }} /></i><small><span className="plan-key" />план <span className="fact-key" />факт по последнему снимку</small></div>
                  <div className="map-equipment-compare"><div className="map-equipment-compare-head"><span>Техника на текущем этапе</span><small>{latestSnapshot ? `Последний снимок · ${shortDate(latestSnapshot.captured_at)}` : "Нет снимка для сравнения"}</small></div>{equipmentComparison.length ? <table><thead><tr><th>Ожидается по плану</th><th>На снимке</th><th>Статус</th></tr></thead><tbody>{equipmentComparison.map((row) => <tr key={`${row.expected}-${row.actual}`}><td>{row.expected}</td><td>{row.actual}</td><td><span className={`map-equipment-status ${row.tone}`}>{row.status}</span></td></tr>)}</tbody></table> : <p>Нет данных для сравнения.</p>}</div>
                </div>
                <div className={`map-fact ${issuesOpen ? "open" : ""}`}>
                  <button className="map-fact-toggle" type="button" aria-expanded={issuesOpen} aria-controls="map-issues-panel" onClick={toggleIssues}>
                    <span><span>Проблемы / вопросы</span><strong className={selected.violations_open ? "is-danger" : ""}><IconWarning size={14} />{selected.violations_open} / {selected.reviews_open}</strong></span>
                    <span className="map-fact-chevron" aria-hidden="true">⌄</span>
                  </button>
                  {issuesOpen && (
                    <div className="map-issues-panel" id="map-issues-panel">
                      <p className="map-issues-intro">Здесь собраны решения из карточки объекта. Наведите на запись, чтобы посмотреть исходный снимок.</p>
                      <div className="map-terminology" aria-label="Пояснение терминов"><div><b className="problem">Проблема</b><span>подтверждённое несоответствие работ плану или техники текущему этапу</span></div><div><b className="question">Вопрос</b><span>распознавание с недостаточной уверенностью — нужна ручная проверка</span></div></div>
                      {detailsLoading && <p className="map-comment-muted">Загружаю распознавания…</p>}
                      {!detailsLoading && mapWarnings.length === 0 && <p className="map-comment-muted">Открытых проблем по снимкам нет.</p>}
                      <div className="map-issues-list">
                        {mapWarnings.map((warning) => {
                          const snapshot = selectedCard?.snapshots.find((item) => item.id === warning.snapshot_id);
                          const decision = warningDecisions[warning.id];
                          const related = snapshot?.detections.filter((detection) => detection.match !== "ok").slice(0, 3) ?? [];
                          return (
                            <article className={`map-issue-card ${warning.severity === "violation" ? "danger" : "review"}`} key={warning.id} tabIndex={0}>
                              <div className="map-issue-preview" aria-hidden="true"><img src={`/api/snapshots/${warning.snapshot_id}/file`} alt="" /></div>
                              <div className="map-issue-copy">
                                <div className="map-issue-meta"><span>{warning.severity === "violation" ? "Проблема" : "Вопрос"}</span><time>{shortDate(warning.captured_at)}</time></div>
                                <strong>{warning.title}</strong>
                                <p>{warning.body}</p>
                                {related.length > 0 && <div className="map-issue-detections">{related.map((detection) => <span key={detection.id}>{detection.label} · {detection.score.toFixed(2)}</span>)}</div>}
                                <div className="map-issue-actions">
                                  <button type="button" className={`mini pri ${decision === "confirm" ? "selected" : ""}`} onClick={() => void resolveMapWarning(warning.id, "confirm")}>Подтвердить</button>
                                  <button type="button" className={`mini ${decision === "dismiss" ? "selected" : ""}`} onClick={() => void resolveMapWarning(warning.id, "dismiss")}>Отклонить</button>
                                </div>
                              </div>
                            </article>
                          );
                        })}
                      </div>
                      <Link className="map-issues-link" href={`/objects/${selected.id}?review=1`}>Разобрать проблемы <IconArrowUpRight size={14} /></Link>
                      <div className="map-comments">
                        <div className="map-comments-head"><strong>Комментарии</strong><span>{comments.length}</span></div>
                        {commentsLoading && <p className="map-comment-muted">Загружаю комментарии…</p>}
                        {!commentsLoading && comments.length === 0 && <p className="map-comment-muted">Добавьте пояснение для команды.</p>}
                        {comments.map((comment) => <div className="map-comment" key={comment.id}><p>{comment.body}</p><time>{commentDate(comment.created_at)}</time></div>)}
                        <form className="map-comment-form" onSubmit={submitComment}>
                          <label htmlFor="map-comment-input">Новый комментарий</label>
                          <textarea id="map-comment-input" rows={2} maxLength={1000} value={commentDraft} onChange={(event) => setCommentDraft(event.target.value)} placeholder="Например: проверить фасад до пятницы" />
                          <button type="submit" disabled={!commentDraft.trim() || commentSaving}>{commentSaving ? "Сохраняю…" : "Добавить комментарий"}</button>
                        </form>
                        {commentNotice && <p className="map-comment-success" role="status">{commentNotice}</p>}
                        {commentError && <p className="map-comment-error" role="alert">{commentError}</p>}
                      </div>
                    </div>
                  )}
                </div>
              </div>
              <Link className="map-open" href={`/objects/${selected.id}`} onClick={() => { if (!routePending) setRoutePending(true); }} aria-disabled={routePending}>
                <span>Открыть объект</span><IconArrowUpRight size={16} />
              </Link>
            </>
          ) : (
            <div className="map-empty"><span className="map-empty-mark"><IconPin size={20} /></span><h3>Выберите объект</h3><p>Нажмите на маркер, чтобы увидеть текущий этап, прогресс и проблемы.</p></div>
          )}
        </aside>
      </div>
      {routePending && selected && <div className="map-route-slider" role="status" aria-live="polite"><div className="map-route-slider-panel"><span>Переходим к объекту</span><strong>{selected.name}</strong><i><b /></i></div></div>}
    </section>
  );
}
