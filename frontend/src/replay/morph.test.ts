import { describe, expect, it } from "vitest";
import {
  planToFull,
  planToStory,
  registerGrowingBoard,
  takeGrowingBoard,
  type Box,
} from "./morph";

const box = (x: number, y: number): Box => ({ x, y, width: 100, height: 100 });
// Full graph: a story card S, two members of group G and one never shown.
const full = new Map([
  ["S", box(0, 0)],
  ["m1", box(1000, 0)],
  ["m2", box(1000, 400)],
  ["hidden", box(2000, 0)],
]);
const story = new Map([
  ["S", box(300, 300)],
  ["G", box(600, 300)],
]);
const groups = [{ id: "G", memberIds: ["m1", "m2", "hidden"] }];

describe("story morph plans", () => {
  it("glides story cards from their full-graph place and gathers groups", () => {
    const plan = planToStory(full, story, groups, new Set(["S", "m1", "m2"]));
    expect(plan.from.get("S")).toEqual({ x: -300, y: -300, fade: false });
    // The group starts at the centre of its shown members (1050, 250).
    expect(plan.from.get("G")).toEqual({ x: 400, y: -100, fade: true });
  });

  it("sends shown cards to their story card or into their group", () => {
    const plan = planToStory(full, story, groups, new Set(["S", "m1", "m2"]));
    const ghosts = new Map(plan.ghosts.map((g) => [g.id, g]));
    expect(ghosts.get("S")).toMatchObject({ x: 300, y: 300, shrink: false });
    expect(ghosts.get("m1")).toMatchObject({ x: -400, y: 300, shrink: true });
    expect(ghosts.has("hidden")).toBe(false);
  });

  it("fans folded cards out of their group into the full graph", () => {
    const plan = planToFull(full, story, groups);
    expect(plan.from.get("S")).toEqual({ x: 300, y: 300, fade: false });
    expect(plan.from.get("m2")).toEqual({ x: -400, y: -100, fade: true });
    expect(plan.ghosts).toEqual([]);
  });

  it("hands the growing board's camera to the board of the same case only", () => {
    const shown = new Set(["S"]);
    const release = registerGrowingBoard("c1", () => ({
      viewport: { x: 1, y: 2, zoom: 0.2 },
      shown,
    }));
    expect(takeGrowingBoard("c2")).toBeNull();
    expect(takeGrowingBoard("c1")?.viewport.zoom).toBe(0.2);
    release();
    expect(takeGrowingBoard("c1")).toBeNull();
  });
});
