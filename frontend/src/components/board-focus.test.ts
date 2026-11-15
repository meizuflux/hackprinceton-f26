import { describe, expect, it } from "vitest";
import { demoCase } from "../api/fixtures";
import {
  getFocusFitOptions,
  getFocusPadding,
  getNodesForSelection,
  getNodesForTab,
} from "./board-focus";

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

  it("calculates string pixel padding to avoid percentage distortion in ReactFlow", () => {
    const desktopOpen = getFocusPadding({ isNarrow: false, dockOpen: true });
    expect(desktopOpen.right).toBe("440px");
    expect(desktopOpen.top.endsWith("px")).toBe(true);
    expect(desktopOpen.bottom.endsWith("px")).toBe(true);
    expect(desktopOpen.bottom).toBe("200px");
    expect(desktopOpen.left.endsWith("px")).toBe(true);

    const desktopClosed = getFocusPadding({ isNarrow: false, dockOpen: false });
    expect(desktopClosed.right).toBe("60px");

    const mobileOpen = getFocusPadding({ isNarrow: true, dockOpen: true });
    expect(mobileOpen.right).toBe("60px");
  });

  it("configures comfortable zoom scale limits for single vs multi-node focus", () => {
    const single = getFocusFitOptions({ nodeCount: 1, dockOpen: true });
    expect(single.maxZoom).toBe(1.15);
    expect(single.minZoom).toBe(0.65);
    expect(single.padding.right).toBe("440px");

    const multi = getFocusFitOptions({ nodeCount: 4, dockOpen: true });
    expect(multi.maxZoom).toBe(1.05);
    expect(multi.minZoom).toBe(0.65);
    expect(multi.padding.right).toBe("440px");
  });
});
