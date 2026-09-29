"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

export type Detection = {
  id: number;
  model: string;
  label: string;
  score: number;
  x1: number; y1: number; x2: number; y2: number;
  match: "ok" | "mismatch" | "review";
  verdict?: "" | "correct" | "wrong";
};
export type Snapshot = {
  id: number;
  filename: string;
  captured_at: string;
  status: string;
  width: number;
  height: number;
  detections: Detection[];
};
export type Stage = {
  id: number;
  kind: string;
  name: string;
  date_from: string;
  date_to: string;
  status: string;
};
export type Warning = {
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
export type HumanEvent = {
  id: number;
  object_id: number;
  stage_id: number | null;
  snapshot_id: number | null;
  event_type: "human";
  title: string;
  body: string;
  event_date: string;
  created_at: string;
};
export type Forecast = {
  verdict: "behind" | "ahead" | "on_track" | "unknown";
  days_delta: number | null;
  pace_label: string;
  confidence: string;
  drivers: string[];
  disclaimer: string;
  headline: string;
  fact_stage: string | null;
  plan_stage: string | null;
  equipment_gap: { window: number; rows: { name: string; seen: boolean; missing: boolean }[] };
  activity: { verdict: "working" | "idle" | "insufficient"; label: string; note: string };
};
export type DynamicsPoint = {
  date: string;
  snapshots: number;
  stage_kind: string | null;
  stage_name: string | null;
  violations: number;
  reviews: number;
  equipment_present: string[];
};
export type Dynamics = { window_days: number; sentence: string; points: DynamicsPoint[] };
export type Quality = {
  correct: number;
  wrong: number;
  pending: number;
  total: number;
  rated: number;
  correct_share: number | null;
  note: string;
};
export type SiteZone = {
  id: number;
  name: string;
  kind: "work" | "danger" | "storage";
  polygon: number[][];
};
export type Summary = {
  progress: number;
  planned_finish: string | null;
  stage: { name: string; position: number; progress: number; date_to: string } | null;
  stages_total: number;
  last_snapshot: string | null;
  violations_open: number;
  reviews_open: number;
  forecast?: Forecast;
};
export type Card = {
  object: { id: number; name: string; type: string; district?: string; address?: string; description?: string };
  summary?: Summary;
  stages: Stage[];
  stage_kinds: string[];
  stage_requirements: Record<string, { name: string; classes: string[] }[]>;
  snapshots: Snapshot[];
  warnings: Warning[];
  zones?: SiteZone[];
  dynamics?: Dynamics;
  quality?: Quality;
  events?: HumanEvent[];
  counts: { snapshots: number; warnings_open: number; warnings_total: number };
  conf_threshold: number;
};

export const KIND_RU: Record<string, string> = {
  ground: "подготовка", excavation: "котлован", frame: "каркас",
  facade: "фасады", roof: "кровля", other: "прочее",
};

export function fmt(d: string): string {
  if (!d) return "Дата не задана";
  const [y, m, dd] = d.slice(0, 10).split("-");
  return `${dd}.${m}.${y}`;
}

export function snapshotTone(snap: Snapshot): string {
  if (snap.status === "processing") return "processing";
  if (snap.status === "failed") return "bad";
  if (snap.detections.some((d) => d.match === "mismatch")) return "bad";
  if (snap.status === "new" || snap.status === "empty") return "new";
  if (snap.detections.some((d) => d.match === "review")) return "warn";
  return "ok";
}

export function stageForDate(stages: Stage[], value: string): Stage | undefined {
  const day = value.slice(0, 10);
  return stages.find((stage) => stage.date_from.slice(0, 10) <= day && day <= stage.date_to.slice(0, 10));
}

export function useObjectCard(id: string) {
  const [card, setCard] = useState<Card | null>(null);
  const [notFound, setNotFound] = useState(false);

  const load = useCallback(async () => {
    const res = await apiFetch(`/api/objects/${id}`);
    if (res.status === 404) { setNotFound(true); return null; }
    if (!res.ok) return null;
    const data: Card = await res.json();
    setCard(data);
    return data;
  }, [id]);

  useEffect(() => { void load(); }, [load]);

  useEffect(() => {
    const refresh = (event: Event) => {
      if ((event as CustomEvent<{ objectId: number }>).detail?.objectId === Number(id)) void load();
    };
    window.addEventListener("buildwatch:plan-updated", refresh);
    return () => window.removeEventListener("buildwatch:plan-updated", refresh);
  }, [id, load]);

  useEffect(() => {
    if (!card?.snapshots.some((s) => s.status === "processing")) return;
    const timer = window.setInterval(() => { void load(); }, 5000);
    return () => window.clearInterval(timer);
  }, [card, load]);

  return { card, setCard, load, notFound };
}
