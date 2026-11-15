import { describe, expect, it } from "vitest";
import { demoCase } from "../api/fixtures";
import { getNodesForSelection, getNodesForTab } from "./board-focus";

describe("board-focus helpers", () => {
  it("resolves nodes with gaps when focusing gaps tab", () => {
    const gapNodeIds = getNodesForTab("gaps", demoCase);
    expect(gapNodeIds).toEqual(new Set(["camera", "loss", "van"]));
  });

  it("resolves inference-related nodes when focusing insights tab", () => {
    const insightNodeIds = getNodesForTab("insights", demoCase);
    expect(insightNodeIds.has("alex")).toBe(true);
    expect(insightNodeIds.has("wh4")).toBe(true);
    expect(insightNodeIds.has("camera")).toBe(true);
    expect(insightNodeIds.has("loss")).toBe(true);
  });

  it("resolves direct node and supporting citations for a specific gap", () => {
    const videoGapNodes = getNodesForSelection(
      { kind: "gap", id: "gap-video" },
      demoCase,
    );
    expect(videoGapNodes.has("camera")).toBe(true);
    expect(videoGapNodes.has("wh4")).toBe(true);
    expect(videoGapNodes.has("van")).toBe(true);
  });

  it("resolves cited evidence nodes for an insight", () => {
    const insight1Nodes = getNodesForSelection(
      { kind: "insight", id: "I1" },
      demoCase,
    );
    expect(insight1Nodes).toEqual(
      new Set(["alex", "wh4", "loss", "statement"]),
    );
  });

  it("resolves individual node and edge selections", () => {
    expect(
      getNodesForSelection({ kind: "node", id: "jordan" }, demoCase),
    ).toEqual(new Set(["jordan"]));

    expect(getNodesForSelection({ kind: "edge", id: "e1" }, demoCase)).toEqual(
      new Set(["alex", "wh4"]),
    );
  });
});
