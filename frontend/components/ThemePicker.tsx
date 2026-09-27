"use client";

import { useEffect, useRef, useState } from "react";
import { IconPalette } from "@/components/Icons";
import { applyTheme, currentTheme, THEMES, type ThemeId } from "@/lib/themes";

/** Visual identity switcher in the nav bar; "ios" is the default.
 *  Hidden by default — available with ?styles=1 for previews and QA. */
export function ThemePicker() {
  const [open, setOpen] = useState(false);
  const [enabled, setEnabled] = useState(false);
  const [active, setActive] = useState<ThemeId>("ios");
  const ref = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    setEnabled(new URLSearchParams(window.location.search).has("styles"));
    setActive(currentTheme());
    const onDoc = (e: MouseEvent) => {
      if (open && ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (open && e.key === "Escape") {
        setOpen(false);
        trigger.current?.focus();
      }
    };
    document.addEventListener("pointerdown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (!enabled) return null;

  function pick(id: ThemeId) {
    applyTheme(id);
    setActive(id);
    setOpen(false);
    trigger.current?.focus();
  }

  return (
    <div className="theme-wrap" ref={ref}>
      <button
        ref={trigger}
        className={`icon-btn tinted ${active !== "ios" ? "active-theme" : ""}`}
        onClick={() => setOpen((v) => !v)}
        aria-label="Сменить визуальный стиль"
        aria-expanded={open}
        aria-controls="theme-menu"
        title="Визуальный стиль"
      >
        <IconPalette size={20} />
      </button>
      {open && (
        <div id="theme-menu" className="theme-pop" role="menu" aria-label="Визуальный стиль">
          {THEMES.map((t) => (
            <button
              key={t.id}
              role="menuitemradio"
              aria-checked={active === t.id}
              className={`theme-item ${active === t.id ? "on" : ""}`}
              onClick={() => pick(t.id)}
            >
              <span className="theme-sw">{t.sw.map((c) => <i key={c} style={{ background: c }} />)}</span>
              <span className="theme-name">{t.name}<small>{t.desc}</small></span>
              <i className="theme-check" />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
