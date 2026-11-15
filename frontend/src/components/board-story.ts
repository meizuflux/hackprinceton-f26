/**
 * Story view geometry and grouping. Presentation only: the backend chooses the
 * story; this module arranges those cards, folds the rest of the board into
 * labelled group cards and reveals cards on request. It never merges, adds or
 * re-types evidence or relationships, and every group member keeps its own
 * card, citations and threads once it is on the board.
 */
import type {
  BoardStory,
  CaseData,
  EvidenceEdge,
  EvidenceNode,
  NodeType,
} from "../api/types";
import { PIN_GAP, type Pin, type Point } from "./board-layout";
import {
  threadCategory,
  threadColors,
  type ThreadCategory,
} from "./board-colors";
import { relationshipKind, type RelationshipKind } from "./relationships";

export type Size = { width: number; height: number };

/** Compact story card, the hero (story centre) and a group card. */
export const STORY_CARD: Size = { width: 196, height: 96 };
export const STORY_HERO: Size = { width: 300, height: 140 };
export const STORY_GROUP: Size = { width: 196, height: 96 };
/** An expanded card overlays its neighbours at this width, growing downward. */
export const STORY_EXPANDED: Size = { width: 336, height: 420 };
/** Above this many hidden targets, a focus flow highlights groups instead of revealing every card. */
export const REVEAL_LIMIT = 8;

export const GROUP_PREFIX = "group:";
export const isGroupId = (id: string) => id.startsWith(GROUP_PREFIX);

export interface StoryGroup {
  id: string;
  kind: "contacts" | "type";
  /** Card type the members share, for the icon and ink. */
  nodeType: NodeType | "other";
  title: string;
  /** Plain description of the rule that put members here. */
  rule: string;
  memberIds: string[];
  /** Story person whose contacts these are. */
  anchorId?: string;
}

/** Returns the backend story when its centre and cards exist on this board. */
export function resolveStory(data: CaseData): BoardStory | null {
  const story = data.story;
  if (!story) return null;
  const ids = new Set(data.nodes.map((node) => node.id));
  if (!ids.has(story.centerId)) return null;
  const nodeIds = [
    story.centerId,
    ...story.nodeIds.filter((id) => id !== story.centerId && ids.has(id)),
  ];
  return { ...story, nodeIds: Array.from(new Set(nodeIds)) };
}

function edgesByNode(edges: EvidenceEdge[]) {
  const map = new Map<string, EvidenceEdge[]>();
  for (const edge of edges) {
    for (const id of [edge.source, edge.target]) {
      const list = map.get(id) ?? [];
      list.push(edge);
      map.set(id, list);
    }
  }
  return map;
}

const otherEnd = (edge: EvidenceEdge, id: string) =>
  edge.source === id ? edge.target : edge.source;

const TYPE_GROUPS: Array<[NodeType, string, string]> = [
  ["person", "Other people", "People not in the story"],
  ["event", "Other events", "Events not in the story"],
  ["location", "Other places", "Places not in the story"],
  [
    "device",
    "Other phones & accounts",
    "Phones, accounts and devices not in the story",
  ],
  ["statement", "Other statements", "Statements not in the story"],
];

/**
 * Folds every non-story card into a few groups, in order:
 * 1. Contacts of a story person: phones and accounts (device cards) whose
 *    threads are all communication threads, at least one of them with that
 *    person. Formed only with two or more members.
 * 2. The remaining cards by record type ("Other people", "Other events", ...),
 *    then any unrecognised type as "Other records".
 * Every hidden card lands in exactly one group.
 */
export function buildStoryGroups(
  nodes: EvidenceNode[],
  edges: EvidenceEdge[],
  storyIds: string[],
): StoryGroup[] {
  const story = new Set(storyIds);
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const linked = edgesByNode(edges);
  const hidden = nodes.filter((node) => !story.has(node.id));
  const assigned = new Set<string>();
  const groups: StoryGroup[] = [];

  for (const personId of storyIds) {
    const person = byId.get(personId);
    if (person?.type !== "person") continue;
    const members = hidden.filter((node) => {
      if (assigned.has(node.id) || node.type !== "device") return false;
      const own = linked.get(node.id) ?? [];
      return (
        own.length > 0 &&
        own.every((edge) => threadCategory(edge.type) === "communication") &&
        own.some((edge) => otherEnd(edge, node.id) === personId)
      );
    });
    if (members.length < 2) continue;
    members.forEach((node) => assigned.add(node.id));
    groups.push({
      id: `${GROUP_PREFIX}contacts:${personId}`,
      kind: "contacts",
      nodeType: "device",
      title: `${person.label}'s contacts`,
      rule: `Phones and accounts linked only by communication threads, including at least one with ${person.label}`,
      memberIds: members.map((node) => node.id),
      anchorId: personId,
    });
  }

  const known = new Set<string>(TYPE_GROUPS.map(([type]) => type));
  for (const [type, title, rule] of TYPE_GROUPS) {
    const members = hidden.filter(
      (node) => !assigned.has(node.id) && node.type === type,
    );
    if (!members.length) continue;
    members.forEach((node) => assigned.add(node.id));
    groups.push({
      id: `${GROUP_PREFIX}type:${type}`,
      kind: "type",
      nodeType: type,
      title,
      rule,
      memberIds: members.map((node) => node.id),
    });
  }
  const rest = hidden.filter(
    (node) => !assigned.has(node.id) && !known.has(node.type),
  );
  if (rest.length) {
    groups.push({
      id: `${GROUP_PREFIX}type:other`,
      kind: "type",
      nodeType: "other",
      title: "Other records",
      rule: "Records not in the story",
      memberIds: rest.map((node) => node.id),
    });
  }
  return groups;
}

export function groupLookup(groups: StoryGroup[]) {
  const map = new Map<string, StoryGroup>();
  for (const group of groups)
    for (const id of group.memberIds) map.set(id, group);
  return map;
}

export type AggregateKind = RelationshipKind | "mixed";

/** Several real threads from one card into a group's hidden members, drawn as one. */
export interface AggregateThread {
  id: string;
  source: string;
  target: string;
  count: number;
  /** Shared family, or null when the threads differ. */
  category: ThreadCategory | null;
  kind: AggregateKind;
  edgeIds: string[];
}

/**
 * Splits the board's threads for the visible cards: threads between visible
 * cards are drawn as they are; threads from a visible card into a group's
 * hidden members become one aggregate per card and group; threads between
 * hidden cards are not drawn.
 */
export function storyThreads(
  edges: EvidenceEdge[],
  visible: Set<string>,
  groups: StoryGroup[],
): { shown: EvidenceEdge[]; aggregates: AggregateThread[] } {
  const groupOf = groupLookup(groups);
  const shown: EvidenceEdge[] = [];
  const buckets = new Map<
    string,
    { source: string; target: string; edges: EvidenceEdge[] }
  >();
  for (const edge of edges) {
    const sourceShown = visible.has(edge.source);
    const targetShown = visible.has(edge.target);
    if (sourceShown && targetShown) {
      shown.push(edge);
      continue;
    }
    if (sourceShown === targetShown) continue;
    const from = sourceShown ? edge.source : edge.target;
    const hiddenId = sourceShown ? edge.target : edge.source;
    const group = groupOf.get(hiddenId);
    if (!group || groupOf.get(from) === group) continue;
    const key = `${from}|${group.id}`;
    const bucket = buckets.get(key) ?? {
      source: from,
      target: group.id,
      edges: [],
    };
    bucket.edges.push(edge);
    buckets.set(key, bucket);
  }
  const aggregates = Array.from(buckets.values()).map(
    ({ source, target, edges: list }) => {
      const categories = new Set(list.map((edge) => threadCategory(edge.type)));
      const kinds = new Set(
        list.map((edge) => relationshipKind(edge.type, edge.certainty)),
      );
      return {
        id: `aggregate:${source}|${target}`,
        source,
        target,
        count: list.length,
        category: categories.size === 1 ? [...categories][0] : null,
        kind: kinds.size === 1 ? [...kinds][0] : ("mixed" as const),
        edgeIds: list.map((edge) => edge.id),
      };
    },
  );
  return { shown, aggregates };
}

/** Wording for an aggregate that is true of every thread it stands for. */
export function aggregateLabel(
  thread: Pick<AggregateThread, "count" | "category" | "kind">,
) {
  const noun = thread.count === 1 ? "thread" : "threads";
  const family = thread.category
    ? `${threadColors[thread.category].label.toLowerCase()} `
    : "";
  const certainty =
    thread.kind === "mixed"
      ? " · observed and inferred"
      : thread.kind === "inference"
        ? " · inferred"
        : thread.kind === "claim"
          ? " · claims"
          : "";
  return `${thread.count} ${family}${noun}${certainty}`;
}

const TAU = Math.PI * 2;
const angleOf = (point: Point) => Math.atan2(point.y, point.x);
const angularDistance = (a: number, b: number) => {
  const d = Math.abs(a - b) % TAU;
  return d > Math.PI ? TAU - d : d;
};

/**
 * Ring order for the story's satellites: cards linked to the centre in thread
 * order, each followed by the story cards that hang off it, so linked cards
 * sit side by side.
 */
export function storyRingOrder(
  story: BoardStory,
  edges: EvidenceEdge[],
): string[] {
  const inStory = new Set(story.nodeIds);
  const linked = edgesByNode(edges);
  const neighbours = (id: string) =>
    (linked.get(id) ?? [])
      .map((edge) => otherEnd(edge, id))
      .filter((other) => inStory.has(other));
  const direct = Array.from(new Set(neighbours(story.centerId))).filter(
    (id) => id !== story.centerId,
  );
  const order: string[] = [];
  const placed = new Set<string>([story.centerId]);
  const place = (id: string) => {
    if (placed.has(id)) return;
    placed.add(id);
    order.push(id);
  };
  const ordered = story.nodeIds.filter((id) => direct.includes(id));
  for (const id of ordered) {
    place(id);
    for (const child of story.nodeIds) {
      if (placed.has(child) || direct.includes(child)) continue;
      if (neighbours(child).includes(id)) place(child);
    }
  }
  for (const id of story.nodeIds) place(id);

  // Swap cards while that shortens the threads between them around the ring.
  const n = order.length;
  const pairs: Array<[string, string]> = [];
  for (const edge of edges) {
    if (edge.source === story.centerId || edge.target === story.centerId)
      continue;
    if (inStory.has(edge.source) && inStory.has(edge.target))
      pairs.push([edge.source, edge.target]);
  }
  const cost = (ring: string[]) => {
    const index = new Map(ring.map((id, i) => [id, i]));
    return pairs.reduce((sum, [a, b]) => {
      const d = Math.abs(index.get(a)! - index.get(b)!);
      return sum + Math.min(d, n - d) ** 2;
    }, 0);
  };
  let best = cost(order);
  for (let improved = true, rounds = 0; improved && rounds < 20; rounds++) {
    improved = false;
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        [order[i], order[j]] = [order[j], order[i]];
        const next = cost(order);
        if (next < best) {
          best = next;
          improved = true;
        } else [order[i], order[j]] = [order[j], order[i]];
      }
    }
  }
  return order;
}

function overlaps(a: Pin, b: Pin, gap = PIN_GAP) {
  const aw = a.width ?? STORY_CARD.width;
  const ah = a.height ?? STORY_CARD.height;
  const bw = b.width ?? STORY_CARD.width;
  const bh = b.height ?? STORY_CARD.height;
  return (
    a.position.x < b.position.x + bw + gap &&
    a.position.x + aw + gap > b.position.x &&
    a.position.y < b.position.y + bh + gap &&
    a.position.y + ah + gap > b.position.y
  );
}

/** Column gap in the story frame: room for a short thread label between cards. */
export const STORY_COLUMN_GAP = 64;
/**
 * The visible canvas a 1440×900 screen leaves beside the open review dock
 * (see getStoryPadding); the frame is sized to fill it at about 90% zoom.
 */
const TARGET_VIEW = { width: 890, height: 736 };
/** A thread drawn under another card reads as a link to it; avoid that strongly. */
const CROSSING_PENALTY = 600;

/** Perimeter cells of a columns × rows grid, clockwise from the top-left. */
function perimeter(columns: number, rows: number) {
  const cells: Array<{ column: number; row: number }> = [];
  for (let column = 0; column < columns; column++)
    cells.push({ column, row: 0 });
  for (let row = 1; row < rows; row++) cells.push({ column: columns - 1, row });
  for (let column = columns - 2; column >= 0; column--)
    cells.push({ column, row: rows - 1 });
  for (let row = rows - 2; row > 0; row--) cells.push({ column: 0, row });
  return cells;
}

/**
 * Lays out the story as a frame around the hero: the centre sits in the
 * middle, and the other story cards and the group cards fill the cells of a
 * compact grid's perimeter. The grid is the smallest that holds them and best
 * fills the canvas beside the open dock. Cards then swap cells while that
 * shortens their threads (to each other, to the hero and into groups), so
 * linked cards sit side by side. Returns top-left positions keyed by node or
 * group ID; every card keeps PIN_GAP clearance.
 */
export function layoutStory(
  story: BoardStory,
  edges: EvidenceEdge[],
  groups: StoryGroup[],
): Map<string, Point> {
  const satellites = storyRingOrder(story, edges);
  const { aggregates } = storyThreads(edges, new Set(story.nodeIds), groups);
  // Each group starts beside the story card with the most threads into it.
  const sequence = [...satellites];
  for (const group of groups) {
    const strongest = aggregates
      .filter((thread) => thread.target === group.id)
      .sort((a, b) => b.count - a.count)[0];
    const at = strongest ? sequence.indexOf(strongest.source) : -1;
    if (at >= 0) sequence.splice(at + 1, 0, group.id);
    else sequence.push(group.id);
  }

  const cellWidth = STORY_CARD.width + STORY_COLUMN_GAP;
  const cellHeight = STORY_CARD.height + PIN_GAP;
  let grid = { columns: 4, rows: 4, score: Infinity };
  for (let columns = 4; columns <= 9; columns++) {
    for (let rows = 4; rows <= 12; rows++) {
      if (2 * columns + 2 * (rows - 2) < sequence.length) continue;
      const width = columns * cellWidth - STORY_COLUMN_GAP;
      const height = rows * cellHeight - PIN_GAP;
      const score = Math.max(
        width / TARGET_VIEW.width,
        height / TARGET_VIEW.height,
      );
      if (score < grid.score - 1e-9) grid = { columns, rows, score };
    }
  }
  const cells = perimeter(grid.columns, grid.rows);
  // Start the clockwise fill at the middle of the left side.
  const leftMiddle = cells.findIndex(
    (cell) => cell.column === 0 && cell.row === Math.floor(grid.rows / 2),
  );
  const slots = [...cells.slice(leftMiddle), ...cells.slice(0, leftMiddle)];
  const offsetX = -(grid.columns * cellWidth - STORY_COLUMN_GAP) / 2;
  const offsetY = -(grid.rows * cellHeight - PIN_GAP) / 2;
  const slotPoint = (index: number): Point => ({
    x: offsetX + slots[index].column * cellWidth,
    y: offsetY + slots[index].row * cellHeight,
  });
  const centre = (index: number): Point => {
    const point = slotPoint(index);
    return {
      x: point.x + STORY_CARD.width / 2,
      y: point.y + STORY_CARD.height / 2,
    };
  };

  // Static geometry: distance between any two cells (the hero is cell S) and
  // the cells a straight thread between them would run underneath.
  const S = slots.length;
  const HERO = S;
  const at = (k: number) => (k === HERO ? { x: 0, y: 0 } : centre(k));
  const sizeOf = (k: number) => (k === HERO ? STORY_HERO : STORY_CARD);
  const span = S + 1;
  const distance: number[] = new Array(span * span).fill(0);
  const under: number[][] = Array.from({ length: span * span }, () => []);
  for (let a = 0; a < span; a++) {
    for (let b = a + 1; b < span; b++) {
      const pa = at(a);
      const pb = at(b);
      distance[a * span + b] = distance[b * span + a] = Math.hypot(
        pa.x - pb.x,
        pa.y - pb.y,
      );
      const crossed: number[] = [];
      for (let k = 0; k < span; k++) {
        if (k === a || k === b) continue;
        const box = at(k);
        const size = sizeOf(k);
        for (let step = 1; step < 16; step++) {
          const t = step / 16;
          if (
            Math.abs(pa.x + (pb.x - pa.x) * t - box.x) < size.width / 2 &&
            Math.abs(pa.y + (pb.y - pa.y) * t - box.y) < size.height / 2
          ) {
            crossed.push(k);
            break;
          }
        }
      }
      under[a * span + b] = under[b * span + a] = crossed;
    }
  }

  // Threads the arrangement should keep short, by item index (-1 is the hero).
  const itemIndex = new Map(sequence.map((id, index) => [id, index]));
  const indexOf = (id: string) =>
    id === story.centerId ? -1 : (itemIndex.get(id) ?? null);
  const pairs: Array<[number, number, number]> = [];
  const inStory = new Set(story.nodeIds);
  for (const edge of edges) {
    if (!inStory.has(edge.source) || !inStory.has(edge.target)) continue;
    const a = indexOf(edge.source);
    const b = indexOf(edge.target);
    if (a !== null && b !== null) pairs.push([a, b, 1]);
  }
  for (const thread of aggregates) {
    const a = indexOf(thread.source);
    const b = indexOf(thread.target);
    if (a !== null && b !== null) pairs.push([a, b, Math.sqrt(thread.count)]);
  }

  const cost = (slotOf: number[], occupant: number[]) => {
    let sum = 0;
    for (const [a, b, weight] of pairs) {
      const sa = a < 0 ? HERO : slotOf[a];
      const sb = b < 0 ? HERO : slotOf[b];
      let length = distance[sa * span + sb];
      for (const k of under[sa * span + sb])
        if (k === HERO || occupant[k] >= 0) length += CROSSING_PENALTY;
      sum += weight * length;
    }
    return sum;
  };
  /** Swaps cells (empty ones included) while that lowers the cost. */
  const settle = (start: number, order: number[]) => {
    const slotOf: number[] = new Array(sequence.length);
    const occupant: number[] = new Array(S).fill(-1);
    order.forEach((item, i) => {
      const slot = (start + i) % S;
      slotOf[item] = slot;
      occupant[slot] = item;
    });
    let best = cost(slotOf, occupant);
    for (let improved = true, round = 0; improved && round < 40; round++) {
      improved = false;
      for (let i = 0; i < S; i++) {
        for (let j = i + 1; j < S; j++) {
          const a = occupant[i];
          const b = occupant[j];
          if (a < 0 && b < 0) continue;
          occupant[i] = b;
          occupant[j] = a;
          if (a >= 0) slotOf[a] = j;
          if (b >= 0) slotOf[b] = i;
          const next = cost(slotOf, occupant);
          if (next < best - 1e-6) {
            best = next;
            improved = true;
          } else {
            occupant[i] = a;
            occupant[j] = b;
            if (a >= 0) slotOf[a] = i;
            if (b >= 0) slotOf[b] = j;
          }
        }
      }
    }
    return { slotOf, best };
  };
  // Deterministic restarts from every starting cell, in both directions.
  const forward = sequence.map((_, index) => index);
  const backward = [...forward].reverse();
  let chosen = settle(0, forward);
  for (let start = 0; start < S; start++) {
    for (const order of [forward, backward]) {
      const attempt = settle(start, order);
      if (attempt.best < chosen.best - 1e-6) chosen = attempt;
    }
  }

  const positions = new Map<string, Point>();
  positions.set(story.centerId, {
    x: -STORY_HERO.width / 2,
    y: -STORY_HERO.height / 2,
  });
  sequence.forEach((id, index) =>
    positions.set(id, slotPoint(chosen.slotOf[index])),
  );
  return positions;
}

const centreOf = (pin: Pin): Point => ({
  x: pin.position.x + (pin.width ?? STORY_CARD.width) / 2,
  y: pin.position.y + (pin.height ?? STORY_CARD.height) / 2,
});

/**
 * Finds clear spots for new cards around an anchor card, nearest first and
 * favouring the side that faces away from `away` (usually the story centre),
 * keeping PIN_GAP clearance from every obstacle. Returns top-left positions.
 */
export function placeAround(
  anchor: Pin,
  items: Array<{ id: string } & Size>,
  obstacles: Pin[],
  away?: Point,
): Map<string, Point> {
  const centre = centreOf(anchor);
  const outward =
    away && (centre.x !== away.x || centre.y !== away.y)
      ? angleOf({ x: centre.x - away.x, y: centre.y - away.y })
      : Math.PI / 2;
  const placed: Pin[] = [];
  const result = new Map<string, Point>();
  const anchorReach =
    Math.max(
      anchor.width ?? STORY_CARD.width,
      anchor.height ?? STORY_CARD.height,
    ) / 2;
  for (const item of items) {
    const candidates: Array<{ point: Point; score: number }> = [];
    for (let ring = 0; ring < 14; ring++) {
      const radius =
        anchorReach +
        Math.max(item.width, item.height) / 2 +
        PIN_GAP +
        ring * 110;
      const steps = Math.max(8, Math.round((TAU * radius) / 90));
      for (let step = 0; step < steps; step++) {
        const angle = outward + (TAU * step) / steps;
        const diff = angularDistance(angle, outward);
        candidates.push({
          point: {
            x: centre.x + Math.cos(angle) * radius * 1.25 - item.width / 2,
            y: centre.y + Math.sin(angle) * radius * 0.85 - item.height / 2,
          },
          score: radius + diff * 150,
        });
      }
    }
    candidates.sort((a, b) => a.score - b.score);
    const all = [anchor, ...obstacles, ...placed];
    const spot =
      candidates.find(
        ({ point }) =>
          !all.some((other) => overlaps({ ...item, position: point }, other)),
      )?.point ?? candidates[candidates.length - 1].point;
    result.set(item.id, spot);
    placed.push({ ...item, position: spot });
  }
  return result;
}

/** Cards linked to `id` by any thread that are not on the board yet. */
export function hiddenNeighbours(
  id: string,
  edges: EvidenceEdge[],
  visible: Set<string>,
): string[] {
  const ids: string[] = [];
  for (const edge of edges) {
    if (edge.source !== id && edge.target !== id) continue;
    const other = otherEnd(edge, id);
    if (!visible.has(other) && !ids.includes(other)) ids.push(other);
  }
  return ids;
}

/**
 * Where a focus flow should look: visible cards stay as they are and hidden
 * cards are represented by their group card. With `reveal`, up to
 * REVEAL_LIMIT hidden cards are returned to be revealed instead.
 */
export function planFocus(
  targetIds: Iterable<string>,
  visible: Set<string>,
  groups: StoryGroup[],
  reveal: boolean,
): { reveal: string[]; focus: string[] } {
  const groupOf = groupLookup(groups);
  const ids = Array.from(new Set(targetIds));
  const hidden = ids.filter((id) => !visible.has(id) && groupOf.has(id));
  const revealIds = reveal && hidden.length <= REVEAL_LIMIT ? hidden : [];
  const focus = new Set<string>();
  for (const id of ids) {
    if (visible.has(id) || revealIds.includes(id)) focus.add(id);
    else {
      const group = groupOf.get(id);
      if (group) focus.add(group.id);
    }
  }
  return { reveal: revealIds, focus: Array.from(focus) };
}

/**
 * The visible card a revealed card should sit beside: its linked visible card
 * with the most threads to it, else its group card.
 */
export function revealAnchor(
  id: string,
  edges: EvidenceEdge[],
  visible: Set<string>,
  groups: StoryGroup[],
): string | undefined {
  const counts = new Map<string, number>();
  for (const edge of edges) {
    if (edge.source !== id && edge.target !== id) continue;
    const other = otherEnd(edge, id);
    if (visible.has(other)) counts.set(other, (counts.get(other) ?? 0) + 1);
  }
  const best = [...counts].sort((a, b) => b[1] - a[1])[0]?.[0];
  if (best) return best;
  const group = groupLookup(groups).get(id);
  return group && visible.has(group.id) ? group.id : undefined;
}
