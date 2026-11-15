/**
 * Presentation-only plans for animating between the full graph and the story
 * view: where each card starts relative to its final place, and which cards of
 * the outgoing view travel away and fade. Positions come from the two layouts
 * already on screen; nothing here creates, merges or moves case facts.
 */

export interface Box {
  x: number;
  y: number;
  width?: number;
  height?: number;
}
interface Point {
  x: number;
  y: number;
}

/** Morph length in ms; the camera eases to the new fit over the same time. */
export const MORPH_MS = 1150;

export const centreOf = (box: Box): Point => ({
  x: box.x + (box.width ?? 0) / 2,
  y: box.y + (box.height ?? 0) / 2,
});
const minus = (a: Point, b: Point): Point => ({ x: a.x - b.x, y: a.y - b.y });

export interface MorphFrom extends Point {
  /** The card grows in from small and transparent (it was not on screen). */
  fade: boolean;
}
export interface MorphGhost extends Point {
  id: string;
  /** Shrinks away into a group card (else it fades as its new card glides in). */
  shrink: boolean;
}
export interface MorphPlan {
  /** Offset each card of the incoming view starts from, relative to its final place. */
  from: Map<string, MorphFrom>;
  /** Cards of the outgoing view that travel by this offset and fade. */
  ghosts: MorphGhost[];
}

interface Group {
  id: string;
  memberIds: string[];
}

/**
 * Full graph → story. Story cards glide from their full-graph place; each group
 * card gathers from where its members were; the cards that were showing travel
 * to their story card or into their group and fade.
 */
export function planToStory(
  full: ReadonlyMap<string, Box>,
  story: ReadonlyMap<string, Box>,
  groups: readonly Group[],
  shown: ReadonlySet<string>,
): MorphPlan {
  const groupOf = new Map<string, string>();
  for (const group of groups)
    for (const id of group.memberIds)
      if (!story.has(id)) groupOf.set(id, group.id);
  const groupIds = new Set(groups.map((group) => group.id));
  const from = new Map<string, MorphFrom>();
  for (const [id, box] of story) {
    const end = centreOf(box);
    if (groupIds.has(id)) {
      const members = groups
        .find((group) => group.id === id)!
        .memberIds.filter((member) => shown.has(member) && full.has(member))
        .map((member) => centreOf(full.get(member)!));
      const start = members.length
        ? {
            x: members.reduce((sum, p) => sum + p.x, 0) / members.length,
            y: members.reduce((sum, p) => sum + p.y, 0) / members.length,
          }
        : end;
      from.set(id, { ...minus(start, end), fade: true });
    } else if (full.has(id) && shown.has(id))
      from.set(id, { ...minus(centreOf(full.get(id)!), end), fade: false });
    else from.set(id, { x: 0, y: 0, fade: true });
  }
  const ghosts: MorphGhost[] = [];
  for (const [id, box] of full) {
    if (!shown.has(id)) continue;
    const start = centreOf(box);
    const own = story.get(id);
    const group = groupOf.get(id);
    const target = own ?? (group ? story.get(group) : undefined);
    ghosts.push({
      id,
      ...(target ? minus(centreOf(target), start) : { x: 0, y: 0 }),
      shrink: !own,
    });
  }
  return { from, ghosts };
}

/**
 * Story → full graph. Cards on the story board glide to their full-graph place;
 * cards folded into a group fan out of it.
 */
export function planToFull(
  full: ReadonlyMap<string, Box>,
  story: ReadonlyMap<string, Box>,
  groups: readonly Group[],
): MorphPlan {
  const groupOf = new Map<string, string>();
  for (const group of groups)
    for (const id of group.memberIds)
      if (!story.has(id)) groupOf.set(id, group.id);
  const from = new Map<string, MorphFrom>();
  for (const [id, box] of full) {
    const end = centreOf(box);
    const own = story.get(id);
    const group = groupOf.get(id);
    const source = own ?? (group ? story.get(group) : undefined);
    from.set(
      id,
      source
        ? { ...minus(centreOf(source), end), fade: !own }
        : { x: 0, y: 0, fade: true },
    );
  }
  return { from, ghosts: [] };
}

/** Class and CSS variables for a card arriving by a plan. */
export function morphFromStyle(from: MorphFrom): {
  className: string;
  style: Record<string, string>;
} {
  return {
    className: from.fade ? "morph-from morph-fade" : "morph-from",
    style: { "--morph-x": `${from.x}px`, "--morph-y": `${from.y}px` },
  };
}

export const prefersReducedMotion = () =>
  typeof window !== "undefined" &&
  typeof window.matchMedia === "function" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/*
 * Hand-off from the board that grew during a replay to the board that opens on
 * the story when it ends. The board is keyed on `growing`, so the settled board
 * renders while the growing one is still mounted: it asks the growing board for
 * its camera and the cards it was showing, and animates on from there.
 */
export interface GrowingSnapshot {
  viewport: { x: number; y: number; zoom: number };
  shown: ReadonlySet<string>;
}
let growing: { caseId: string; take: () => GrowingSnapshot } | null = null;

export function registerGrowingBoard(
  caseId: string,
  take: () => GrowingSnapshot,
): () => void {
  const entry = { caseId, take };
  growing = entry;
  return () => {
    if (growing === entry) growing = null;
  };
}

export function takeGrowingBoard(caseId: string): GrowingSnapshot | null {
  if (!growing || growing.caseId !== caseId) return null;
  try {
    return growing.take();
  } catch {
    return null;
  }
}
