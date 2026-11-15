import type { CaseData } from "../api/types";
import type { Selection } from "./Inspector";

export type Tab = "gaps" | "insights" | "suggestions";

/** Returns the node IDs relevant to a selection (gap, insight, contradiction, node, edge, suggestion, or source). */
export function getNodesForSelection(
  selection: Selection,
  data: CaseData,
): Set<string> {
  const ids = new Set<string>();

  switch (selection.kind) {
    case "node":
      ids.add(selection.id);
      break;

    case "edge": {
      const edge = data.edges.find((e) => e.id === selection.id);
      if (edge) {
        ids.add(edge.source);
        ids.add(edge.target);
      }
      break;
    }

    case "gap": {
      const gap = data.gaps.find((g) => g.id === selection.id);
      if (gap) {
        for (const n of data.nodes) {
          if (n.gapId === gap.id) ids.add(n.id);
        }
        if (gap.nodeIds) {
          // The backend names the nodes a gap concerns; shared citations would
          // be too broad once entity nodes cite every record behind them.
          for (const id of gap.nodeIds) {
            if (data.nodes.some((n) => n.id === id)) ids.add(id);
          }
        } else {
          for (const n of data.nodes) {
            if (n.citations.some((c) => gap.citations.includes(c))) {
              ids.add(n.id);
            }
          }
        }
        for (const claim of gap.affectedClaims) {
          if (data.nodes.some((n) => n.id === claim)) {
            ids.add(claim);
          }
        }
      }
      break;
    }

    case "insight": {
      const insight = data.insights.find((i) => i.id === selection.id);
      if (insight) {
        for (const n of data.nodes) {
          if (n.citations.some((c) => insight.citations.includes(c))) {
            ids.add(n.id);
          }
        }
      }
      break;
    }

    case "suggestion": {
      const suggestion = data.suggestions.find((s) => s.id === selection.id);
      if (suggestion) {
        if (suggestion.gapId) {
          for (const n of data.nodes) {
            if (n.gapId === suggestion.gapId) ids.add(n.id);
          }
        }
        for (const n of data.nodes) {
          if (n.citations.some((c) => suggestion.citations.includes(c))) {
            ids.add(n.id);
          }
        }
      }
      break;
    }

    case "contradiction": {
      const item = data.contradictions?.find((c) => c.id === selection.id);
      if (item) {
        for (const n of data.nodes) {
          if (n.citations.some((c) => item.citations.includes(c))) {
            ids.add(n.id);
          }
        }
      }
      break;
    }

    case "source": {
      for (const n of data.nodes) {
        if (n.citations.includes(selection.id)) ids.add(n.id);
      }
      break;
    }
  }

  return ids;
}

/** Returns the node IDs relevant to an analysis tab (gaps, insights, suggestions). */
export function getNodesForTab(tab: Tab, data: CaseData): Set<string> {
  const ids = new Set<string>();

  if (tab === "gaps") {
    for (const n of data.nodes) {
      if (n.gapId) ids.add(n.id);
    }
  } else if (tab === "insights") {
    const allInsightCitations = new Set(
      data.insights.flatMap((i) => i.citations),
    );
    for (const n of data.nodes) {
      if (n.citations.some((c) => allInsightCitations.has(c))) {
        ids.add(n.id);
      }
    }
  } else if (tab === "suggestions") {
    const suggestionGaps = new Set(
      data.suggestions.map((s) => s.gapId).filter(Boolean) as string[],
    );
    for (const n of data.nodes) {
      if (n.gapId && suggestionGaps.has(n.gapId)) ids.add(n.id);
    }
  }

  return ids;
}

type PaddingPx = `${number}px`;

export interface FocusFitOptions {
  padding: {
    top: PaddingPx;
    bottom: PaddingPx;
    left: PaddingPx;
    right: PaddingPx;
  };
  duration: number;
  maxZoom: number;
  minZoom: number;
}

/** Computes padding strings in pixels so ReactFlow (@xyflow/system) doesn't treat padding as percentage ratios. */
/** Width of the floating case toolbar plus its inset and a margin. */
const TOOLBAR_CLEARANCE: PaddingPx = "80px";

/**
 * Story-view fit padding: clear of the view switch at the top, the case
 * toolbar on the left, and (above 900px) the open review dock plus the zoom
 * controls beside it on the right.
 */
export function getStoryPadding(options: {
  isNarrow?: boolean;
  dockOpen?: boolean;
  /** A replay's run panel (340px, beside the toolbar) is open on the left. */
  runPanelOpen?: boolean;
}): { top: PaddingPx; bottom: PaddingPx; left: PaddingPx; right: PaddingPx } {
  const isNarrow = options.isNarrow ?? false;
  const besideDock = !isNarrow && (options.dockOpen ?? false);
  return {
    top: "108px",
    bottom: "56px",
    // inset 16 + toolbar 48 + gap 12 + run panel 340 + gap 16
    left: !isNarrow && options.runPanelOpen ? "432px" : TOOLBAR_CLEARANCE,
    right: besideDock ? "470px" : "72px",
  };
}

export function getFocusPadding(options: {
  isNarrow?: boolean;
  dockOpen?: boolean;
}): { top: PaddingPx; bottom: PaddingPx; left: PaddingPx; right: PaddingPx } {
  const isNarrow = options.isNarrow ?? false;
  const dockOpen = options.dockOpen ?? false;
  const besideDock = !isNarrow && dockOpen;
  const rightPad: PaddingPx = besideDock ? "440px" : "60px";

  return {
    top: "90px",
    // Beside the open dock, the minimap and zoom controls sit at the bottom of
    // the visible canvas; keep the focused cards above them.
    bottom: besideDock ? "200px" : "100px",
    left: "90px",
    right: rightPad,
  };
}

/** Returns fitView options configured for comfortable legibility (~0.95–1.15x zoom). */
export function getFocusFitOptions(options: {
  nodeCount: number;
  isNarrow?: boolean;
  dockOpen?: boolean;
}): FocusFitOptions {
  return {
    padding: getFocusPadding(options),
    duration: 650,
    maxZoom: options.nodeCount === 1 ? 1.15 : 1.05,
    minZoom: 0.65,
  };
}
