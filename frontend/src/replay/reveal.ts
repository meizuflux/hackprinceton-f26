import type { CaseData, Origin } from "../api/types";
import type { TraceProgress } from "./trace";

/**
 * Presentation-only reveal rules. A board item appears when the run reached
 * the point that produced it; items without provenance (fixtures, older cases)
 * are always shown. Nothing here creates or scores case facts.
 */

interface Provenance {
  id?: string;
  key?: string;
  origin?: Origin;
  stage?: string;
  evidenceIds?: string[];
}

export function itemRevealed(
  item: Provenance,
  progress: TraceProgress,
  defaultStage?: string,
): boolean {
  if (progress.finished) return true;
  if (!item.origin && !item.stage && !defaultStage) return true;
  const origin = item.origin;
  if (origin === "record") {
    const ids = item.evidenceIds ?? [];
    return ids.length
      ? ids.some((id) => progress.parsedEvidence.has(id))
      : progress.phases.ingest.status === "done";
  }
  if (origin === "agent") {
    if (
      (item.key && progress.insightKeys.has(item.key)) ||
      (item.id && progress.insightIds.has(item.id))
    )
      return true;
  }
  if (origin === "ml" && item.id && progress.signalIds.has(item.id))
    return true;
  const stage = item.stage ?? defaultStage;
  return stage ? progress.stagesFinished.has(stage) : true;
}

export interface RevealedIds {
  nodes: Set<string>;
  edges: Set<string>;
}

export function revealedGraph(
  data: Pick<CaseData, "nodes" | "edges">,
  progress: TraceProgress,
): RevealedIds {
  const nodes = new Set(
    data.nodes.filter((n) => itemRevealed(n, progress)).map((n) => n.id),
  );
  const edges = new Set(
    data.edges
      .filter(
        (e) =>
          nodes.has(e.source) &&
          nodes.has(e.target) &&
          itemRevealed(e, progress),
      )
      .map((e) => e.id),
  );
  return { nodes, edges };
}

/** The case as far as the run has got; the full case once the run finished. */
export function revealCase(data: CaseData, progress: TraceProgress): CaseData {
  if (progress.finished) return data;
  const graph = revealedGraph(data, progress);
  return {
    ...data,
    nodes: data.nodes.filter((n) => graph.nodes.has(n.id)),
    edges: data.edges.filter((e) => graph.edges.has(e.id)),
    gaps: data.gaps.filter((g) => itemRevealed(g, progress, "gaps")),
    suggestions: data.suggestions.filter((s) =>
      itemRevealed(s, progress, "next_steps"),
    ),
    insights: data.insights.filter((i) =>
      itemRevealed(
        i,
        progress,
        i.origin === "agent" ? "agent_insights" : "insights",
      ),
    ),
    signals: data.signals?.filter((s) =>
      itemRevealed({ ...s, origin: "ml" }, progress, "ml_signals"),
    ),
    contradictions: data.contradictions?.filter((c) =>
      itemRevealed(c as Provenance, progress, "contradictions"),
    ),
  };
}

/** A case with nothing revealed, for the empty map while a run has not produced the board yet. */
export function emptyCase(id: string, title: string): CaseData {
  return {
    id,
    title,
    subtitle: "Analysis in progress",
    timeRange: { start: "", end: "" },
    nodes: [],
    edges: [],
    gaps: [],
    insights: [],
    suggestions: [],
    sources: [],
    audit: [],
  };
}
