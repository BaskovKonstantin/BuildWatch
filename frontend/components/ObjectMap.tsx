"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import type { LayerGroup, Map as LeafletMap, Marker } from "leaflet";
import {
  IconArrowUpRight, IconBuilding, IconCamera, IconEye, IconPin, IconWarning,
} from "@/components/Icons";

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

function coordinatesFor(project: MapProject): [number, number] {
  return DISTRICT_COORDINATES[project.district] ?? MOSCOW_CENTER;
}

function shortDate(value: string | null) {
  if (!value) return "—";
  const [year, month, day] = value.slice(0, 10).split("-");
  return `${day}.${month}.${year}`;
}

function statusFor(project: MapProject) {
  if (project.violations_open > 0) return { className: "danger", label: "Есть сигналы" };
  if (project.reviews_open > 0) return { className: "review", label: "Нужна проверка" };
  return { className: "clear", label: "Без открытых сигналов" };
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

export function ObjectMap({ projects, totals, selectedId, onSelect }: ObjectMapProps) {
  const mapElement = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const layerRef = useRef<LayerGroup | null>(null);
  const leafletRef = useRef<typeof import("leaflet") | null>(null);
  const markersRef = useRef(new Map<number, Marker>());
  const [mapReady, setMapReady] = useState(false);
  const selected = projects.find((project) => project.id === selectedId) ?? null;
  const selectedStatus = selected ? statusFor(selected) : null;

  useEffect(() => {
    let disposed = false;
    if (!mapElement.current) return;
    import("leaflet").then((L) => {
      if (disposed || !mapElement.current || mapRef.current) return;
      leafletRef.current = L;
      const map = L.map(mapElement.current, { center: MOSCOW_CENTER, zoom: 9, minZoom: 8, maxZoom: 17, zoomControl: true });
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: "© OpenStreetMap contributors",
      }).addTo(map);
      layerRef.current = L.layerGroup().addTo(map);
      mapRef.current = map;
      setMapReady(true);
      window.setTimeout(() => map.invalidateSize(), 0);
    });
    return () => {
      disposed = true;
      markersRef.current.clear();
      mapRef.current?.remove();
      mapRef.current = null;
      layerRef.current = null;
      leafletRef.current = null;
      setMapReady(false);
    };
  }, []);

  useEffect(() => {
    const L = leafletRef.current;
    const layer = layerRef.current;
    if (!mapReady || !L || !layer) return;
    layer.clearLayers();
    markersRef.current.clear();
    projects.forEach((project) => {
      const marker = L.marker(coordinatesFor(project), {
        icon: markerIcon(L, project, project.id === selectedId),
        title: project.name,
        alt: `${project.name}, ${statusFor(project).label}`,
      });
      marker.on("click", () => onSelect(project.id));
      marker.addTo(layer);
      markersRef.current.set(project.id, marker);
    });
  }, [mapReady, projects, selectedId, onSelect]);

  useEffect(() => {
    if (!mapRef.current || !selected) return;
    mapRef.current.panTo(coordinatesFor(selected), { animate: true, duration: 0.35 });
  }, [selected]);

  return (
    <section className="object-map" aria-label="Объекты на карте Москвы">
      <div className="map-head">
        <div><span className="map-kicker">ПОРТФЕЛЬ / МОСКВА</span><h2>Объекты на карте</h2></div>
        <div className="map-legend" aria-label="Легенда состояний">
          <span><i className="map-dot danger" />Сигналы</span><span><i className="map-dot review" />Проверка</span><span><i className="map-dot clear" />Норма</span>
        </div>
      </div>

      <div className="map-layout">
        <aside className="map-feed" aria-label="Лента состояния портфеля">
          <div className="map-feed-head"><strong>Состояние портфеля</strong><span>Сейчас</span></div>
          <div className="map-feed-list">
            <div className="map-feed-item objects"><span className="map-feed-icon"><IconBuilding size={17} /></span><div><b>{totals.projects}</b><span>объектов в мониторинге</span></div></div>
            <div className="map-feed-item danger"><span className="map-feed-icon"><IconWarning size={17} /></span><div><b>{totals.violations}</b><span>открытых сигналов</span></div></div>
            <div className="map-feed-item review"><span className="map-feed-icon"><IconEye size={17} /></span><div><b>{totals.reviews}</b><span>сигналов на проверке</span></div></div>
            <div className="map-feed-item snapshots"><span className="map-feed-icon"><IconCamera size={17} /></span><div><b>{totals.snapshots}</b><span>снимков в истории</span></div></div>
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
                <div><span>Текущий этап</span><strong>{selected.stage?.name ?? "Не задан"}</strong></div>
                <div><span>Прогресс по плану</span><strong>{Math.round(selected.progress * 100)}%</strong></div>
                <div><span>Сигналы / проверка</span><strong className={selected.violations_open ? "is-danger" : ""}><IconWarning size={14} />{selected.violations_open} / {selected.reviews_open}</strong></div>
                <div><span>Последний снимок</span><strong>{shortDate(selected.last_snapshot)}</strong></div>
              </div>
              <Link className="map-open" href={`/objects/${selected.id}`}>Открыть объект <IconArrowUpRight size={16} /></Link>
            </>
          ) : (
            <div className="map-empty"><span className="map-empty-mark"><IconPin size={20} /></span><h3>Выберите объект</h3><p>Нажмите на маркер, чтобы увидеть текущий этап, прогресс и сигналы.</p></div>
          )}
        </aside>
      </div>
    </section>
  );
}
