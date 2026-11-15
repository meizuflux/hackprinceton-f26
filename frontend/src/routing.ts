import { useCallback, useEffect, useState } from "react";

export type WorkspaceView =
  "board" | "evidence" | "files" | "insights" | "chat";

/** Insights subsections: open questions, what records show, what analysis infers. */
export const insightsTabs = ["questions", "evidence", "inferences"] as const;
export type InsightsTab = (typeof insightsTabs)[number];

export type AppRoute =
  | { kind: "welcome" }
  | { kind: "projects" }
  | { kind: "new-project" }
  | {
      kind: "case";
      caseId: string;
      view?: WorkspaceView;
      sourceId?: string;
      insightsTab?: InsightsTab;
    }
  | { kind: "not-found" };

/** Parse only the routes supported by the prototype. Case existence is checked against CaseApi data. */
export function parseRoute(pathname: string): AppRoute {
  if (pathname === "/") return { kind: "welcome" };
  if (/^\/projects\/?$/.test(pathname)) return { kind: "projects" };
  if (/^\/projects\/new\/?$/.test(pathname)) return { kind: "new-project" };

  const match =
    /^\/cases\/([^/]+)(?:\/(evidence|files|insights|chat)(?:\/([^/]+))?)?\/?$/.exec(
      pathname,
    );
  if (!match) return { kind: "not-found" };

  let caseId: string;
  try {
    caseId = decodeURIComponent(match[1]);
  } catch {
    return { kind: "not-found" };
  }
  if (
    !caseId ||
    caseId === "." ||
    caseId === ".." ||
    /[\u0000-\u001f\u007f/\\]/.test(caseId)
  ) {
    return { kind: "not-found" };
  }
  const view = match[2] as WorkspaceView | undefined;
  if (match[3] && view === "insights") {
    const tab = match[3] as InsightsTab;
    if (!insightsTabs.includes(tab)) return { kind: "not-found" };
    return { kind: "case", caseId, view, insightsTab: tab };
  }
  if (match[3] && view !== "evidence") return { kind: "not-found" };
  let sourceId: string | undefined;
  if (match[3]) {
    try {
      sourceId = decodeURIComponent(match[3]);
    } catch {
      return { kind: "not-found" };
    }
    if (!isSafeSegment(sourceId)) return { kind: "not-found" };
  }
  return {
    kind: "case",
    caseId,
    ...(view ? { view } : {}),
    ...(sourceId ? { sourceId } : {}),
  };
}

function isSafeSegment(value: string): boolean {
  return (
    !!value &&
    value !== "." &&
    value !== ".." &&
    !/[\u0000-\u001f\u007f/\\]/.test(value)
  );
}

export function casePath(
  caseId: string,
  view: WorkspaceView = "board",
  sourceId?: string,
): string {
  if (!isSafeSegment(caseId)) {
    throw new Error("Case ID must be a non-empty path segment");
  }
  if (
    sourceId !== undefined &&
    (view !== "evidence" || !isSafeSegment(sourceId))
  ) {
    throw new Error(
      "Source links require a safe source ID and the evidence view",
    );
  }
  return `/cases/${encodeURIComponent(caseId)}${view === "board" ? "" : `/${view}`}${sourceId ? `/${encodeURIComponent(sourceId)}` : ""}`;
}

export function insightsPath(caseId: string, tab: InsightsTab): string {
  if (!insightsTabs.includes(tab))
    throw new Error(`Unknown insights tab: ${tab}`);
  return `${casePath(caseId, "insights")}/${tab}`;
}

export interface NavigateOptions {
  replace?: boolean;
}

/** Minimal browser-history router; URLs remain the source of truth for back/forward and reloads. */
export function useRouter() {
  const [route, setRoute] = useState<AppRoute>(() =>
    typeof window === "undefined"
      ? { kind: "welcome" }
      : parseRoute(window.location.pathname),
  );

  useEffect(() => {
    const syncRoute = () => setRoute(parseRoute(window.location.pathname));
    window.addEventListener("popstate", syncRoute);
    return () => window.removeEventListener("popstate", syncRoute);
  }, []);

  const navigate = useCallback(
    (path: string, options: NavigateOptions = {}) => {
      const next = parseRoute(path);
      if (next.kind === "not-found")
        throw new Error(`Unsupported application route: ${path}`);
      if (options.replace) window.history.replaceState(null, "", path);
      else window.history.pushState(null, "", path);
      setRoute(next);
    },
    [],
  );

  return { route, navigate };
}
