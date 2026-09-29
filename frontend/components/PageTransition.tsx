"use client";

import { usePathname } from "next/navigation";
import { useEffect } from "react";

type Direction = "forward" | "back" | "same";

let lastPath = "";

function routeDepth(path: string) {
  return path.split("/").filter(Boolean).length;
}

function resolveDirection(from: string, to: string): Direction {
  if (!from || from === to) return "same";
  const fromDepth = routeDepth(from);
  const toDepth = routeDepth(to);
  if (toDepth > fromDepth) return "forward";
  if (toDepth < fromDepth) return "back";
  return "same";
}

/**
 * Spring-slide enter animation for App Router navigations.
 * Relies on `app/template.tsx` remounting on each route change.
 * AssistantDock / PageGuide stay in layout and do not animate.
 */
export function PageTransition({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() || "/";
  const from = lastPath || (typeof window !== "undefined" ? window.location.pathname : "");
  const direction = resolveDirection(from, pathname);

  useEffect(() => {
    lastPath = pathname;
  }, [pathname]);

  return (
    <div
      className={`page-transition page-transition--${direction}`}
      data-page-transition="spring-slide"
      data-direction={direction}
    >
      {children}
    </div>
  );
}
