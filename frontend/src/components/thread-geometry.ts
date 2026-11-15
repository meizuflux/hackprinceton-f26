/**
 * Where each thread's label sits along its curve. Presentation only: labels
 * slide along their own thread to the spot that covers the fewest cards and
 * other labels, so the relationship wording is never hidden under a card.
 */
import { Position } from "@xyflow/react";

export type Rect = { x: number; y: number; width: number; height: number };
export type Side = "top" | "right" | "bottom" | "left";

/** Curvature shared by ThreadEdge's bezier and the label search. */
export const THREAD_CURVATURE = 0.22;
/** Preferred spots first: the middle, then outwards in both directions. */
const SPOTS = [0.5, 0.42, 0.58, 0.34, 0.66, 0.27, 0.73, 0.2, 0.8, 0.14, 0.86];

type End = { x: number; y: number; side: Side };

function controlOffset(distance: number) {
  return distance >= 0
    ? 0.5 * distance
    : THREAD_CURVATURE * 25 * Math.sqrt(-distance);
}

/** React Flow's bezier control point for an end (see @xyflow/system getBezierPath). */
function control(from: End, to: { x: number; y: number }) {
  switch (from.side) {
    case "left":
      return { x: from.x - controlOffset(from.x - to.x), y: from.y };
    case "right":
      return { x: from.x + controlOffset(to.x - from.x), y: from.y };
    case "top":
      return { x: from.x, y: from.y - controlOffset(from.y - to.y) };
    case "bottom":
      return { x: from.x, y: from.y + controlOffset(to.y - from.y) };
  }
}

/** A point at `t` along the thread between two handle positions. */
export function threadPoint(source: End, target: End, t: number) {
  const c1 = control(source, target);
  const c2 = control(target, source);
  const u = 1 - t;
  const a = u * u * u;
  const b = 3 * u * u * t;
  const c = 3 * u * t * t;
  const d = t * t * t;
  return {
    x: a * source.x + b * c1.x + c * c2.x + d * target.x,
    y: a * source.y + b * c1.y + c * c2.y + d * target.y,
  };
}

export function sideOf(position: Position | string): Side {
  return position === Position.Top
    ? "top"
    : position === Position.Right
      ? "right"
      : position === Position.Bottom
        ? "bottom"
        : "left";
}

/** Handle position on a card's side, as React Flow places it. */
export function handlePoint(card: Rect, side: Side): End {
  switch (side) {
    case "top":
      return { x: card.x + card.width / 2, y: card.y, side };
    case "right":
      return { x: card.x + card.width, y: card.y + card.height / 2, side };
    case "bottom":
      return { x: card.x + card.width / 2, y: card.y + card.height, side };
    case "left":
      return { x: card.x, y: card.y + card.height / 2, side };
  }
}

/** Rough label box for a chip of Excalifont text (14.5px) with an optional icon. */
export function labelBox(text: string, maxWidth: number, extra = 0) {
  const natural = 14 + extra + text.length * 8.2;
  const lines = Math.max(1, Math.ceil(natural / maxWidth));
  return {
    width: Math.min(natural, maxWidth),
    height: 8 + lines * 19,
  };
}

function overlap(a: Rect, b: Rect) {
  const w = Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x);
  const h = Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y);
  return w > 0 && h > 0 ? w * h : 0;
}

const CELL = 320;
/** Coarse grid so each label only checks the cards near it. */
class Grid {
  private cells = new Map<string, Rect[]>();
  add(rect: Rect) {
    for (const key of this.keys(rect)) {
      const list = this.cells.get(key);
      if (list) list.push(rect);
      else this.cells.set(key, [rect]);
    }
  }
  near(rect: Rect) {
    const found = new Set<Rect>();
    for (const key of this.keys(rect))
      for (const item of this.cells.get(key) ?? []) found.add(item);
    return found;
  }
  private keys(rect: Rect) {
    const keys: string[] = [];
    for (
      let x = Math.floor(rect.x / CELL);
      x <= Math.floor((rect.x + rect.width) / CELL);
      x++
    )
      for (
        let y = Math.floor(rect.y / CELL);
        y <= Math.floor((rect.y + rect.height) / CELL);
        y++
      )
        keys.push(`${x},${y}`);
    return keys;
  }
}

export interface LabelRequest {
  id: string;
  source: Rect;
  target: Rect;
  sourceSide: Side;
  targetSide: Side;
  width: number;
  height: number;
}

/**
 * Picks a spot `t` along each thread for its label: the preferred spot that
 * covers the least card and label area. Earlier requests are placed first, so
 * pass the most important threads first. Deterministic for the same input.
 */
export function placeThreadLabels(
  requests: LabelRequest[],
  cards: Rect[],
  /** Receives the threads whose best spot still lies mostly on a card. */
  covered?: Set<string>,
): Map<string, number> {
  const cardGrid = new Grid();
  for (const card of cards) cardGrid.add(card);
  const labelGrid = new Grid();
  const placed = new Map<string, number>();
  for (const request of requests) {
    const from = handlePoint(request.source, request.sourceSide);
    const to = handlePoint(request.target, request.targetSide);
    let best = 0.5;
    let bestCost = Infinity;
    let bestRect: Rect | null = null;
    let bestOnCards = 0;
    for (const t of SPOTS) {
      const at = threadPoint(from, to, t);
      const rect = {
        x: at.x - request.width / 2,
        y: at.y - request.height / 2,
        width: request.width,
        height: request.height,
      };
      let cost = Math.abs(t - 0.5) * 400;
      let onCards = 0;
      for (const card of cardGrid.near(rect)) onCards += overlap(rect, card);
      cost += onCards * 2;
      for (const label of labelGrid.near(rect))
        cost += overlap(rect, label) * 3;
      if (cost < bestCost) {
        bestCost = cost;
        best = t;
        bestRect = rect;
        bestOnCards = onCards;
      }
      if (cost === 0) break;
    }
    placed.set(request.id, best);
    if (bestOnCards > request.width * request.height * 0.3)
      covered?.add(request.id);
    if (bestRect) labelGrid.add(bestRect);
  }
  return placed;
}
