"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { IconChevronLeft } from "@/components/Icons";
import { ThemePicker } from "@/components/ThemePicker";

/**
 * iOS navigation bar: translucent material, back button on the left,
 * inline title that fades in once the page's large title scrolls away.
 */
export function NavBar({
  title,
  back,
  right,
  wide = false,
  assistant = true,
}: {
  title: string;
  wide?: boolean;
  back?: { href: string; label: string };
  right?: React.ReactNode;
  assistant?: boolean;
}) {
  const [compact, setCompact] = useState(false);

  useEffect(() => {
    const onScroll = () => setCompact(window.scrollY > 56);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header className={`nav ${wide ? "wide" : ""} ${compact ? "compact" : ""}`}>
      <div className="nav-inner">
        <div className="nav-left">
          {back ? (
            <Link className="nav-back" href={back.href}>
              <IconChevronLeft size={22} />
              <span>{back.label}</span>
            </Link>
          ) : (
            <Link className="brand" href="/" aria-label="BuildWatch — на главную">
              <span className="logo" aria-hidden="true">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M4 20V9l8-5 8 5v11" /><path d="M9 20v-6h6v6" />
                </svg>
              </span>
              <span className="brand-name">BuildWatch</span>
            </Link>
          )}
        </div>
        <div className="nav-title" aria-hidden={!compact}>{title}</div>
        <div className="nav-right">
          {assistant && <button
              className="assistant-nav-link"
              type="button"
              onClick={() => document.querySelector<HTMLButtonElement>(".assistant-trigger")?.click()}
              aria-label="Открыть ИИ-помощника"
            >
              <span aria-hidden="true">✳</span><span>Спросить BuildWatch</span>
            </button>}
          <ThemePicker />
          {right}
        </div>
      </div>
    </header>
  );
}
