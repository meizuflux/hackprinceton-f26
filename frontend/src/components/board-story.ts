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
export const STORY_CARD: Size = { width: 220, height: 108 };
export const STORY_HERO: Size = { width: 312, height: 164 };
export const STORY_GROUP: Size = { width: 228, height: 112 };
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

/**
 * Lays out the story: the centre as the hero at the origin, the other story
 * cards on an ellipse around it, and the group cards on an outer ring, each
 * turned toward the story cards it has threads with. Returns top-left
 * positions keyed by node or group ID.
 */
export function layoutStory(
  story: BoardStory,
  edges: EvidenceEdge[],
  groups: StoryGroup[],
): Map<string, Point> {
  const positions = new Map<string, Point>();
  positions.set(story.centerId, {
    x: -STORY_HERO.width / 2,
    y: -STORY_HERO.height / 2,
  });
  const ring = storyRingOrder(story, edges);
  const n = ring.length;
  const rx = Math.max(400, (1.1 * n * (STORY_CARD.width + PIN_GAP)) / TAU);
  const ry = Math.max(240, rx * 0.6);
  // The satellite with the most story threads sits at the left, where the
  // landscape canvas has room for the cards around it.
  const inStory = new Set(story.nodeIds);
  const degree = (id: string) =>
    edges.filter(
      (edge) =>
        (edge.source === id && inStory.has(edge.target)) ||
        (edge.target === id && inStory.has(edge.source)),
    ).length;
  const hubIndex = ring.reduce(
    (best, id, index) => (degree(id) > degree(ring[best]) ? index : best),
    0,
  );
  const angles = new Map<string, number>();
  const ringPins: Pin[] = [
    {
      id: story.centerId,
      position: positions.get(story.centerId)!,
      ...STORY_HERO,
    },
  ];
  ring.forEach((id, index) => {
    const angle = Math.PI + (TAU * (index - hubIndex)) / Math.max(n, 1);
    angles.set(id, angle);
    let position = {
      x: rx * Math.cos(angle) - STORY_CARD.width / 2,
      y: ry * Math.sin(angle) - STORY_CARD.height / 2,
    };
    // Step outward until clear of the cards already placed.
    for (let step = 0; step < 16; step++) {
      const pin = { id, position, ...STORY_CARD };
      if (!ringPins.some((other) => overlaps(pin, other))) break;
      position = {
        x: position.x + Math.cos(angle) * 24,
        y: position.y + Math.sin(angle) * 24,
      };
    }
    positions.set(id, position);
    ringPins.push({ id, position, ...STORY_CARD });
  });

  // Each group faces the story cards its hidden members have threads with.
  const { aggregates } = storyThreads(edges, new Set(story.nodeIds), groups);
  const wanted = groups.map((group) => {
    let x = 0;
    let y = 0;
    for (const thread of aggregates) {
      if (thread.target !== group.id) continue;
      const angle = angles.get(thread.source);
      if (angle === undefined) continue;
      x += Math.cos(angle) * thread.count;
      y += Math.sin(angle) * thread.count;
    }
    return { group, angle: x || y ? Math.atan2(y, x) : null };
  });

  // Groups stand in two columns at the sides, each on the side nearer the
  // story cards it has threads with; a column may run at most three taller.
  const ringBounds = ringPins.reduce(
    (box, pin) => ({
      minX: Math.min(box.minX, pin.position.x),
      maxX: Math.max(box.maxX, pin.position.x + (pin.width ?? 0)),
    }),
    { minX: Infinity, maxX: -Infinity },
  );
  const leftX = ringBounds.minX - PIN_GAP * 1.5 - STORY_GROUP.width;
  const rightX = ringBounds.maxX + PIN_GAP * 1.5;
  const reach = (group: StoryGroup, x: number) =>
    aggregates
      .filter((thread) => thread.target === group.id)
      .reduce((sum, thread) => {
        const at = positions.get(thread.source)!;
        return sum + thread.count * Math.abs(at.x + STORY_CARD.width / 2 - x);
      }, 0);
  /** Extra thread length from standing on the right rather than the left. */
  const preference = (entry: (typeof wanted)[number]) =>
    reach(entry.group, rightX + STORY_GROUP.width / 2) -
    reach(entry.group, leftX + STORY_GROUP.width / 2);
  const left = wanted.filter((entry) => preference(entry) > 0);
  const right = wanted.filter((entry) => preference(entry) < 0);
  for (const entry of wanted.filter((item) => preference(item) === 0))
    (left.length <= right.length ? left : right).push(entry);
  while (Math.abs(left.length - right.length) > 3) {
    const [from, to] =
      left.length > right.length ? [left, right] : [right, left];
    from.sort((a, b) => Math.abs(preference(a)) - Math.abs(preference(b)));
    to.push(from.shift()!);
  }
  const rowHeight = STORY_GROUP.height + PIN_GAP;
  const column = (entries: typeof wanted, x: number) => {
    const desired = (entry: (typeof wanted)[number]) =>
      entry.angle === null ? 0 : ry * Math.sin(entry.angle);
    const sorted = [...entries].sort((a, b) => desired(a) - desired(b));
    const top = -((sorted.length - 1) * rowHeight) / 2 - STORY_GROUP.height / 2;
    sorted.forEach((entry, index) =>
      positions.set(entry.group.id, { x, y: top + index * rowHeight }),
    );
  };
  column(left, leftX);
  column(right, rightX);
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
