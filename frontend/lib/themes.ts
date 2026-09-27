"use client";

import { useEffect, useState } from "react";

export type ThemeId = "ios" | "tech" | "city" | "ops" | "construct";

const VALID: ThemeId[] = ["ios", "tech", "city", "ops", "construct"];
const KEY = "buildwatch_theme";

export const THEMES: { id: ThemeId; name: string; desc: string; sw: string[] }[] = [
  { id: "ios", name: "iOS", desc: "Системная, светлая и тёмная", sw: ["#007AFF", "#34C759", "#FF9500"] },
  { id: "tech", name: "Техпаспорт", desc: "Инженерная миссия: NASA, ГОСТ, hi-vis", sw: ["#E8590C", "#14181D", "#F4F2EC"] },
  { id: "city", name: "Городская операционная", desc: "Швейцарская сетка, TfL, красный", sw: ["#DC241F", "#111111", "#FFFFFF"] },
  { id: "ops", name: "Командный центр", desc: "Тёмный терминал, Palantir, янтарь", sw: ["#FFB000", "#10151C", "#3FB950"] },
  { id: "construct", name: "Конструктивизм", desc: "Авангард: красный, чёрный, бумага", sw: ["#D02020", "#141414", "#EFE7D8"] },
];

export function applyTheme(id: ThemeId) {
  if (id === "ios") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = id;
  try { localStorage.setItem(KEY, id); } catch {}
}

export function currentTheme(): ThemeId {
  let t: string | undefined;
  try { t = document.documentElement.dataset.theme; } catch {}
  return VALID.includes(t as ThemeId) ? (t as ThemeId) : "ios";
}

/** Reactive theme id: follows html[data-theme] set by the picker or pre-paint script. */
export function useThemeId(): ThemeId {
  const [theme, setTheme] = useState<ThemeId>("ios");
  useEffect(() => {
    setTheme(currentTheme());
    const obs = new MutationObserver(() => setTheme(currentTheme()));
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => obs.disconnect();
  }, []);
  return theme;
}
