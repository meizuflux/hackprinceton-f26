import { useCallback, useEffect, useState } from "react";

export type AppRoute =
  | { kind: "welcome" }
  | { kind: "case"; caseId: string }
  | { kind: "not-found" };

/** Parse only the routes supported by the prototype. Case existence is checked against CaseApi data. */
export function parseRoute(pathname: string): AppRoute {
  if (pathname === "/") return { kind: "welcome" };

  const match = /^\/cases\/([^/]+)\/?$/.exec(pathname);
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
  return { kind: "case", caseId };
}

export function casePath(caseId: string): string {
  if (
    !caseId ||
    caseId === "." ||
    caseId === ".." ||
    /[\u0000-\u001f\u007f/\\]/.test(caseId)
  ) {
    throw new Error("Case ID must be a non-empty path segment");
  }
  return `/cases/${encodeURIComponent(caseId)}`;
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
