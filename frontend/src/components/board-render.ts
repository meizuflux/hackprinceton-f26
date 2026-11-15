/**
 * Render helpers for the board canvas: stable node and thread objects (so
 * React Flow re-renders only what changed), label spots that clear cards,
 * hover highlighting without React state, and a zoom level flag. Presentation
 * only; nothing here creates or changes case facts.
 */
import { useCallback, useEffect, useRef } from "react";
import { useStore, type Edge, type Node } from "@xyflow/react";
import type { CaseData, EvidenceNode } from "../api/types";
import { markedOrigin } from "./board-colors";
import { threadHandles, type Point } from "./board-layout";
import {
  cardSummary,
  cardTitle,
  rawLabelNote,
  shortMethod,
  signalFor,
} from "./readable";
import {
  labelBox,
  placeThreadLabels,
  sideOf,
  type LabelRequest,
  type Rect,
} from "./thread-geometry";
import type { ThreadData } from "./ThreadEdge";

/** Readable card wording for an API node; values are never changed. */
export function cardWording(node: EvidenceNode, data: CaseData) {
  const method = signalFor(node, data.signals)?.method?.name;
  return {
    title: cardTitle(node),
    rawLabel: rawLabelNote(node),
    summary: cardSummary(node),
    labelOrigin: node.labelOrigin,
    method: shortMethod(method),
    methodFull: method,
  };
}

/** Text a search matches for a card: readable and raw wording alike. */
export function searchText(node: {
  label: string;
  title?: string;
  summary?: string;
  displayLabel?: string;
  displaySummary?: string;
}) {
  return [
    node.title,
    node.displayLabel,
    node.label,
    node.displaySummary,
    node.summary,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

/**
 * Returns `build()` for a key unless its inputs are shallow-equal to the
 * previous call's, in which case the previous object is returned, so memoized
 * React Flow nodes and edges skip their render.
 */
export function createReuse<T>() {
  const previous = new Map<string, { inputs: unknown[]; value: T }>();
  return (key: string, inputs: unknown[], build: () => T): T => {
    const entry = previous.get(key);
    if (
      entry &&
      entry.inputs.length === inputs.length &&
      entry.inputs.every((input, index) => Object.is(input, inputs[index]))
    )
      return entry.value;
    const value = build();
    previous.set(key, { inputs, value });
    return value;
  };
}

type Placed = { id: string; position: Point; width?: number; height?: number };

const rectOf = (node: Placed): Rect => ({
  x: node.position.x,
  y: node.position.y,
  width: node.width ?? 0,
  height: node.height ?? 0,
});
const centre = (node: Placed): Point => ({
  x: node.position.x + (node.width ?? 0) / 2,
  y: node.position.y + (node.height ?? 0) / 2,
});

/** Thread priority for label placement: contradictions, then focus, then observed. */
function rank(edge: Edge<ThreadData>) {
  const data = edge.data;
  if (!data) return 9;
  if (data.category === "contradicts") return 0;
  if (data.aggregateCount) return 3;
  return data.kind === "observed" ? 1 : 2;
}

/**
 * Handles (by card centres) and a label spot for every thread whose cards are
 * placed. Label spots avoid every card and earlier labels.
 */
export function threadLayout(
  edges: Edge<ThreadData>[],
  placed: Placed[],
  obstacles: Rect[] = [],
) {
  const byId = new Map(placed.map((node) => [node.id, node]));
  const handles = new Map<string, ReturnType<typeof threadHandles>>();
  const requests: Array<LabelRequest & { order: number }> = [];
  edges.forEach((edge, order) => {
    const source = byId.get(edge.source);
    const target = byId.get(edge.target);
    if (!source || !target) return;
    const pair = threadHandles(centre(source), centre(target));
    handles.set(edge.id, pair);
    const data = edge.data;
    if (!data) return;
    const badge = data.category === "contradicts" ? (data.badge ?? "") : "";
    const box = data.aggregateCount
      ? { width: 30, height: 28 }
      : labelBox(
          badge.length > data.label.length ? badge : data.label,
          166,
          markedOrigin(data.origin) ? 14 : 0,
        );
    requests.push({
      id: edge.id,
      order,
      source: rectOf(source),
      target: rectOf(target),
      sourceSide: sideOf(pair.sourceHandle.replace("source-", "")),
      targetSide: sideOf(pair.targetHandle.replace("target-", "")),
      width: box.width + 6,
      height: box.height + (badge ? 18 : 0),
    });
  });
  requests.sort(
    (a, b) => rank(edges[a.order]) - rank(edges[b.order]) || a.order - b.order,
  );
  const covered = new Set<string>();
  const spots = placeThreadLabels(
    requests,
    [...placed.map(rectOf), ...obstacles],
    covered,
  );
  return { handles, spots, covered };
}

/** Escapes a value for a quoted CSS attribute selector. */
const attr = (value: string) => value.replace(/["\\]/g, "\\$&");

/**
 * Hovering a card or thread reveals its thread labels through one injected
 * stylesheet, so pointer movement never re-renders the board.
 */
export function useHoverLabels() {
  const sheet = useRef<HTMLStyleElement | null>(null);
  useEffect(() => {
    const style = document.createElement("style");
    style.dataset.boardHover = "";
    document.head.appendChild(style);
    sheet.current = style;
    return () => {
      style.remove();
      sheet.current = null;
    };
  }, []);
  const show = useCallback((selector: string | null) => {
    if (!sheet.current) return;
    sheet.current.textContent = selector
      ? `${selector}{opacity:1!important;pointer-events:all!important;background:#fff9e9;z-index:2}` +
        `:is(${selector}) > .thread-badge,:is(${selector}).is-aggregate > .thread-text{display:block!important}` +
        `:is(${selector}).is-covered{width:auto!important;height:auto!important;padding:2px 6px!important;border-radius:3px!important;box-shadow:none!important}` +
        `:is(${selector}).is-covered > .thread-text{display:inline-flex!important}`
      : "";
  }, []);
  return {
    onNodeMouseEnter: useCallback(
      (_: unknown, node: Node) =>
        show(
          `.thread-label[data-source="${attr(node.id)}"],.thread-label[data-target="${attr(node.id)}"]`,
        ),
      [show],
    ),
    onEdgeMouseEnter: useCallback(
      (_: unknown, edge: Edge) =>
        show(`.thread-label[data-edge="${attr(edge.id)}"]`),
      [show],
    ),
    onLeave: useCallback(() => show(null), [show]),
  };
}

/** Below this zoom, cards show only their titles and most thread labels wait for hover. */
export const FAR_ZOOM = 0.6;

/** Reports when the board crosses the far-zoom threshold; re-renders only on a crossing. */
export function ZoomLevelWatcher({
  onFarChange,
}: {
  onFarChange: (far: boolean) => void;
}) {
  const far = useStore((state) => state.transform[2] < FAR_ZOOM);
  useEffect(() => onFarChange(far), [far, onFarChange]);
  return null;
}
