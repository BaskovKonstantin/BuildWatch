"use client";

import { useState } from "react";
import type { PointerEvent } from "react";
import { apiFetch } from "@/lib/api";

export type SiteZone = {
  id: number;
  name: string;
  kind: "work" | "danger" | "storage";
  polygon: number[][];
};

const KIND_LABEL: Record<SiteZone["kind"], string> = {
  danger: "Опасная зона",
  work: "Зона работ",
  storage: "Склад",
};

function boxStyle(polygon: number[][]) {
  const xs = polygon.map((point) => point[0]);
  const ys = polygon.map((point) => point[1]);
  const x1 = Math.min(...xs);
  const y1 = Math.min(...ys);
  const x2 = Math.max(...xs);
  const y2 = Math.max(...ys);
  return {
    left: `${x1 * 100}%`,
    top: `${y1 * 100}%`,
    width: `${(x2 - x1) * 100}%`,
    height: `${(y2 - y1) * 100}%`,
  };
}

export function SiteZoneLayer({
  objectId, zones, enabled, kind, onChanged, onError,
}: {
  objectId: string;
  zones: SiteZone[];
  enabled: boolean;
  kind: SiteZone["kind"];
  onChanged: () => void;
  onError: (message: string) => void;
}) {
  const [draft, setDraft] = useState<{ x1: number; y1: number; x2: number; y2: number } | null>(null);

  function point(event: PointerEvent<HTMLDivElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    return {
      x: Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width)),
      y: Math.min(1, Math.max(0, (event.clientY - rect.top) / rect.height)),
    };
  }

  function onPointerDown(event: PointerEvent<HTMLDivElement>) {
    if (!enabled) return;
    const start = point(event);
    setDraft({ x1: start.x, y1: start.y, x2: start.x, y2: start.y });
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function onPointerMove(event: PointerEvent<HTMLDivElement>) {
    if (!draft) return;
    const next = point(event);
    setDraft((current) => current ? { ...current, x2: next.x, y2: next.y } : current);
  }

  async function onPointerUp() {
    if (!draft) return;
    const x1 = Math.min(draft.x1, draft.x2);
    const y1 = Math.min(draft.y1, draft.y2);
    const x2 = Math.max(draft.x1, draft.x2);
    const y2 = Math.max(draft.y1, draft.y2);
    setDraft(null);
    if (x2 - x1 < 0.02 || y2 - y1 < 0.02) return;
    const response = await apiFetch(`/api/objects/${objectId}/zones`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        kind,
        name: KIND_LABEL[kind],
        polygon: [[x1, y1], [x2, y1], [x2, y2], [x1, y2]],
      }),
    });
    if (!response.ok) {
      onError("Не удалось сохранить зону");
      return;
    }
    onChanged();
  }

  async function remove(zoneId: number) {
    const response = await apiFetch(`/api/objects/${objectId}/zones/${zoneId}`, { method: "DELETE" });
    if (!response.ok) {
      onError("Не удалось удалить зону");
      return;
    }
    onChanged();
  }

  const draftPolygon = draft
    ? [[Math.min(draft.x1, draft.x2), Math.min(draft.y1, draft.y2)], [Math.max(draft.x1, draft.x2), Math.max(draft.y1, draft.y2)]]
    : null;

  return (
    <>
      {zones.map((zone) => (
        <div key={zone.id} className={`zone ${zone.kind}`} style={boxStyle(zone.polygon)}>
          <span>{zone.name}{enabled && <button type="button" onClick={() => void remove(zone.id)}>убрать</button>}</span>
        </div>
      ))}
      {draftPolygon && <div className={`zone ${kind} draft`} style={boxStyle(draftPolygon)} />}
      {enabled && (
        <div className="zone-draw" onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={() => void onPointerUp()} />
      )}
    </>
  );
}
