"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef } from "react";

/** Swap to try variants: "spring-slide" | "view-morph" | "fade" */
export const PAGE_TRANSITION_MODE: "spring-slide" | "view-morph" | "fade" = "view-morph";

type Direction = "forward" | "back" | "same";

let lastPath = "";
let pendingResolve: (() => void) | null = null;

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

function supportsViewTransition(): boolean {
  return typeof document !== "undefined" && typeof document.startViewTransition === "function";
}

type ViewTransition = {
  finished: Promise<void>;
  ready: Promise<void>;
  updateCallbackDone: Promise<void>;
};

function startViewTransition(update: () => void | Promise<void>): ViewTransition {
  return document.startViewTransition!(update);
}

function shouldInterceptLink(anchor: HTMLAnchorElement, event: MouseEvent) {
  if (event.defaultPrevented) return false;
  if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return false;
  if (anchor.target && anchor.target !== "_self") return false;
  if (anchor.hasAttribute("download")) return false;
  if (anchor.dataset.noViewTransition != null) return false;
  if (anchor.classList.contains("map-open")) return false;

  const href = anchor.getAttribute("href");
  if (!href || href.startsWith("mailto:") || href.startsWith("tel:")) return false;

  let url: URL;
  try {
    url = new URL(href, window.location.href);
  } catch {
    return false;
  }
  if (url.origin !== window.location.origin) return false;
  if (url.pathname === window.location.pathname && url.search === window.location.search) return false;
  return true;
}

/**
 * Page enter / route morph animations.
 * - spring-slide: CSS spring based on route depth (template remount)
 * - view-morph: native View Transitions API (Chromium); falls back to spring-slide
 * AssistantDock / PageGuide stay in layout and keep stable view-transition names.
 */
export function PageTransition({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() || "/";
  const router = useRouter();
  const mode = PAGE_TRANSITION_MODE;
  const useMorph = mode === "view-morph" && supportsViewTransition();
  const from = lastPath || (typeof window !== "undefined" ? window.location.pathname : "");
  const direction = resolveDirection(from, pathname);
  const navigating = useRef(false);

  useEffect(() => {
    lastPath = pathname;
    if (pendingResolve) {
      const resolve = pendingResolve;
      pendingResolve = null;
      // Let the new route paint once before finishing the VT snapshot.
      requestAnimationFrame(() => resolve());
    }
    navigating.current = false;
  }, [pathname]);

  useEffect(() => {
    if (!useMorph) return;

    const onClick = (event: MouseEvent) => {
      const target = event.target;
      if (!(target instanceof Element)) return;
      const anchor = target.closest("a");
      if (!(anchor instanceof HTMLAnchorElement)) return;
      if (!shouldInterceptLink(anchor, event)) return;

      const url = new URL(anchor.getAttribute("href") || "", window.location.href);
      const href = `${url.pathname}${url.search}${url.hash}`;
      event.preventDefault();
      if (navigating.current) return;
      navigating.current = true;

      document.documentElement.dataset.vtDirection = resolveDirection(window.location.pathname, url.pathname);

      const run = startViewTransition(async () => {
        router.push(href);
        await new Promise<void>((resolve) => {
          pendingResolve = resolve;
          window.setTimeout(resolve, 900);
        });
      });

      void run.finished.finally(() => {
        navigating.current = false;
        delete document.documentElement.dataset.vtDirection;
      });
    };

    document.addEventListener("click", onClick, true);
    return () => document.removeEventListener("click", onClick, true);
  }, [router, useMorph]);

  const className = useMorph
    ? "page-transition page-transition--view-morph"
    : mode === "fade"
      ? `page-transition page-transition--fade page-transition--${direction}`
      : `page-transition page-transition--spring page-transition--${direction}`;

  return (
    <div
      className={className}
      data-page-transition={useMorph ? "view-morph" : mode}
      data-direction={direction}
    >
      {children}
    </div>
  );
}
