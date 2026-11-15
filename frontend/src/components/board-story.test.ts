import { describe, expect, it } from "vitest";
import type {
  BoardStory,
  CaseData,
  EvidenceEdge,
  EvidenceNode,
} from "../api/types";
import { PIN_GAP } from "./board-layout";
import {
  REVEAL_LIMIT,
  STORY_CARD,
  STORY_GROUP,
  STORY_HERO,
  aggregateLabel,
  buildStoryGroups,
  hiddenNeighbours,
  layoutStory,
  placeAround,
  planFocus,
  resolveStory,
  revealAnchor,
  storyRingOrder,
  storyThreads,
} from "./board-story";

const node = (
  id: string,
  type: EvidenceNode["type"],
  extra: Partial<EvidenceNode> = {},
): EvidenceNode => ({
  id,
  type,
  label: id,
  citations: [`src-${id}`],
  position: { x: 0, y: 0 },
  summary: "",
  subtitle: type,
  ...extra,
});
const edge = (
  source: string,
  target: string,
  type: string,
  certainty: EvidenceEdge["certainty"] = "observed",
): EvidenceEdge => ({
  id: `${type}:${source}:${target}`,
  source,
  target,
  type,
  label: type,
  citations: [`src-${source}-${target}`],
  certainty,
});

// A small board shaped like the Kestrel case: a key event, a person who is
// the hub of most hidden cards, their contacts and some unrelated records.
const nodes: EvidenceNode[] = [
  node("event", "event", { label: "Key event" }),
  node("room", "location"),
  node("door", "location"),
  node("person", "person", { label: "Richard Halvorsen" }),
  node("phone", "device"),
  node("statement", "statement"),
  node("held", "event"),
  node("c1", "device"),
  node("c2", "device"),
  node("c3", "device"),
  node("shared", "device"),
  node("colocated", "device"),
  node("alias", "person"),
  node("other-person", "person"),
  node("other-event", "event"),
  node("other-place", "location"),
  node("lone", "device"),
];
const edges: EvidenceEdge[] = [
  edge("event", "room", "spatial"),
  edge("event", "door", "spatial"),
  edge("person", "event", "temporal"),
  edge("statement", "event", "contradicts", "inferred"),
  edge("person", "statement", "claim"),
  edge("phone", "person", "communication"),
  edge("person", "phone", "spatial", "inferred"),
  edge("held", "door", "spatial"),
  edge("person", "c1", "communication"),
  edge("person", "c2", "communication"),
  edge("c3", "person", "communication"),
  // Talks to the person and to a hidden person: still only communication.
  edge("person", "shared", "communication"),
  edge("shared", "other-person", "communication"),
  // Co-location is not communication, so this is not a contact.
  edge("phone", "colocated", "spatial", "inferred"),
  edge("alias", "person", "identity", "inferred"),
  edge("person", "other-event", "temporal", "inferred"),
  edge("other-event", "room", "spatial"),
  edge("other-event", "other-place", "spatial"),
];
const story: BoardStory = {
  centerId: "event",
  nodeIds: ["event", "room", "door", "person", "phone", "statement", "held"],
  headline: { kind: "contradiction", id: "X-01" },
  reason: "test",
};
const caseData = (overrides: Partial<CaseData> = {}): CaseData => ({
  id: "case",
  title: "Case",
  subtitle: "",
  timeRange: { start: "", end: "" },
  nodes,
  edges,
  gaps: [],
  insights: [],
  suggestions: [],
  sources: [],
  audit: [],
  story,
  ...overrides,
});
const groups = buildStoryGroups(nodes, edges, story.nodeIds);
const byTitle = (title: string) => groups.find((g) => g.title === title)!;

describe("resolveStory", () => {
  it("keeps the backend story, centre first, dropping unknown cards", () => {
    const resolved = resolveStory(
      caseData({
        story: { ...story, nodeIds: ["room", "missing", "event", "room"] },
      }),
    );
    expect(resolved?.nodeIds).toEqual(["event", "room"]);
  });
  it("is null without a story or when its centre is not on the board", () => {
    expect(resolveStory(caseData({ story: undefined }))).toBeNull();
    expect(resolveStory(caseData({ story: null }))).toBeNull();
    expect(
      resolveStory(caseData({ story: { ...story, centerId: "missing" } })),
    ).toBeNull();
  });
});

describe("buildStoryGroups", () => {
  it("folds every hidden card into exactly one group and never a story card", () => {
    const members = groups.flatMap((group) => group.memberIds);
    const hidden = nodes
      .filter((n) => !story.nodeIds.includes(n.id))
      .map((n) => n.id);
    expect(members.sort()).toEqual(hidden.sort());
    expect(new Set(members).size).toBe(members.length);
  });
  it("groups a story person's contacts: devices linked only by communication", () => {
    const contacts = byTitle("Richard Halvorsen's contacts");
    expect(contacts.kind).toBe("contacts");
    expect(contacts.anchorId).toBe("person");
    expect(contacts.memberIds).toEqual(["c1", "c2", "c3", "shared"]);
  });
  it("puts the rest in type groups with exact counts", () => {
    expect(byTitle("Other phones & accounts").memberIds).toEqual([
      "colocated",
      "lone",
    ]);
    expect(byTitle("Other people").memberIds).toEqual([
      "alias",
      "other-person",
    ]);
    expect(byTitle("Other events").memberIds).toEqual(["other-event"]);
    expect(byTitle("Other places").memberIds).toEqual(["other-place"]);
    expect(groups.find((g) => g.title === "Other statements")).toBeUndefined();
  });
  it("needs two contacts to form a contacts group", () => {
    const few = buildStoryGroups(
      nodes,
      edges.filter(
        (e) => !["c2", "c3", "shared"].includes(e.target) && e.source !== "c3",
      ),
      story.nodeIds,
    );
    expect(few.some((g) => g.kind === "contacts")).toBe(false);
  });
});

describe("storyThreads", () => {
  const visible = new Set(story.nodeIds);
  const { shown, aggregates } = storyThreads(edges, visible, groups);
  it("draws threads between visible cards as they are", () => {
    expect(shown.map((e) => e.id)).toContain("claim:person:statement");
    expect(
      shown.every((e) => visible.has(e.source) && visible.has(e.target)),
    ).toBe(true);
  });
  it("hides threads between hidden cards", () => {
    const ids = [
      ...shown.map((e) => e.id),
      ...aggregates.flatMap((a) => a.edgeIds),
    ];
    expect(ids).not.toContain("communication:shared:other-person");
    expect(ids).not.toContain("spatial:other-event:other-place");
  });
  it("aggregates threads into a group per visible card, with exact counts", () => {
    const contacts = aggregates.find(
      (a) =>
        a.source === "person" &&
        a.target === byTitle("Richard Halvorsen's contacts").id,
    )!;
    expect(contacts.count).toBe(4);
    expect(contacts.category).toBe("communication");
    expect(contacts.kind).toBe("observed");
    expect(aggregateLabel(contacts)).toBe("4 communication threads");
  });
  it("never claims a family or certainty that is not true of every thread", () => {
    const events = aggregates.find(
      (a) => a.target === byTitle("Other events").id && a.source === "person",
    )!;
    expect(events.kind).toBe("inference");
    expect(aggregateLabel(events)).toBe("1 time thread · inferred");
    const mixed = aggregateLabel({ count: 3, category: null, kind: "mixed" });
    expect(mixed).toBe("3 threads · observed and inferred");
  });
  it("reports revealed members' threads individually", () => {
    const more = new Set([...visible, "c1"]);
    const next = storyThreads(edges, more, groups);
    expect(next.shown.map((e) => e.id)).toContain("communication:person:c1");
    const contacts = next.aggregates.find(
      (a) => a.target === byTitle("Richard Halvorsen's contacts").id,
    )!;
    expect(contacts.count).toBe(3);
  });
});

describe("story layout", () => {
  const positions = layoutStory(story, edges, groups);
  const size = (id: string) =>
    id.startsWith("group:")
      ? STORY_GROUP
      : id === story.centerId
        ? STORY_HERO
        : STORY_CARD;
  it("centres the hero and places every story card and group once", () => {
    const hero = positions.get("event")!;
    expect(hero.x + STORY_HERO.width / 2).toBeCloseTo(0);
    expect(hero.y + STORY_HERO.height / 2).toBeCloseTo(0);
    expect([...positions.keys()].sort()).toEqual(
      [...story.nodeIds, ...groups.map((g) => g.id)].sort(),
    );
  });
  it("keeps clearance between all cards", () => {
    const entries = [...positions];
    for (let i = 0; i < entries.length; i++) {
      for (let j = i + 1; j < entries.length; j++) {
        const [a, pa] = entries[i];
        const [b, pb] = entries[j];
        const sa = size(a);
        const sb = size(b);
        const apart =
          pa.x + sa.width + PIN_GAP <= pb.x ||
          pb.x + sb.width + PIN_GAP <= pa.x ||
          pa.y + sa.height + PIN_GAP <= pb.y ||
          pb.y + sb.height + PIN_GAP <= pa.y;
        expect(apart, `${a} and ${b} overlap`).toBe(true);
      }
    }
  });
  it("orders the ring so linked story cards sit next to each other", () => {
    const ring = storyRingOrder(story, edges);
    expect(ring).toHaveLength(story.nodeIds.length - 1);
    const at = (id: string) => ring.indexOf(id);
    const distance = (a: string, b: string) => {
      const d = Math.abs(at(a) - at(b));
      return Math.min(d, ring.length - d);
    };
    expect(distance("held", "door")).toBe(1);
    expect(distance("phone", "person")).toBe(1);
  });
  it("puts groups beside the ring, nearer the cards they thread to", () => {
    const contacts = positions.get(byTitle("Richard Halvorsen's contacts").id)!;
    const person = positions.get("person")!;
    const hero = positions.get("event")!;
    expect(Math.sign(contacts.x - hero.x)).toBe(Math.sign(person.x - hero.x));
  });
});

describe("reveal", () => {
  const visible = new Set([...story.nodeIds, ...groups.map((g) => g.id)]);
  it("lists a card's hidden neighbours", () => {
    expect(hiddenNeighbours("phone", edges, visible)).toEqual(["colocated"]);
    expect(hiddenNeighbours("room", edges, visible)).toEqual(["other-event"]);
  });
  it("places revealed cards clear of every card, facing away from the centre", () => {
    const anchor = { id: "person", position: { x: -500, y: 0 }, ...STORY_CARD };
    const obstacles = [
      { id: "event", position: { x: -150, y: -80 }, ...STORY_HERO },
    ];
    const items = ["c1", "c2", "c3", "shared"].map((id) => ({
      id,
      ...STORY_CARD,
    }));
    const spots = placeAround(anchor, items, obstacles, { x: 0, y: 0 });
    const pins = [
      anchor,
      ...obstacles,
      ...items.map((item) => ({ ...item, position: spots.get(item.id)! })),
    ];
    for (let i = 0; i < pins.length; i++)
      for (let j = i + 1; j < pins.length; j++) {
        const a = pins[i];
        const b = pins[j];
        const apart =
          a.position.x + a.width + PIN_GAP <= b.position.x ||
          b.position.x + b.width + PIN_GAP <= a.position.x ||
          a.position.y + a.height + PIN_GAP <= b.position.y ||
          b.position.y + b.height + PIN_GAP <= a.position.y;
        expect(apart, `${a.id} and ${b.id} overlap`).toBe(true);
      }
    // The first card goes on the far side of the anchor from the centre.
    expect(spots.get("c1")!.x).toBeLessThan(anchor.position.x);
  });
  it("reveals a few hidden focus targets and stands groups in for many", () => {
    const plan = planFocus(["event", "c1"], visible, groups, true);
    expect(plan.reveal).toEqual(["c1"]);
    expect(plan.focus.sort()).toEqual(["c1", "event"]);
    const broad = planFocus(["event", "c1"], visible, groups, false);
    expect(broad.reveal).toEqual([]);
    expect(broad.focus.sort()).toEqual(
      ["event", byTitle("Richard Halvorsen's contacts").id].sort(),
    );
    const many = Array.from({ length: REVEAL_LIMIT + 1 }, (_, i) => `x${i}`);
    const manyGroups = [{ ...groups[0], memberIds: many }];
    expect(planFocus(many, visible, manyGroups, true).reveal).toEqual([]);
    expect(planFocus(many, visible, manyGroups, true).focus).toEqual([
      manyGroups[0].id,
    ]);
  });
  it("anchors a revealed card on its most-linked visible card, else its group", () => {
    expect(revealAnchor("c1", edges, visible, groups)).toBe("person");
    expect(revealAnchor("lone", edges, visible, groups)).toBe(
      byTitle("Other phones & accounts").id,
    );
  });
});
