import { describe, expect, it } from "vitest";
import {
  CARD_KINDS,
  PAPER,
  THREAD_CATEGORIES,
  cardColors,
  cardKind,
  ORIGIN_INK,
  contrastRatio,
  markedOrigin,
  originLabel,
  threadBadge,
  threadCategory,
  threadColors,
  threadDash,
} from "./board-colors";

describe("board color coding", () => {
  it("maps every backend edge type to its own thread family", () => {
    for (const type of [
      "communication",
      "spatial",
      "temporal",
      "identity",
      "claim",
      "contradicts",
    ]) {
      expect(threadCategory(type)).toBe(type);
    }
  });

  it("folds fixture vocabulary into the same families", () => {
    expect(threadCategory("time_overlap")).toBe("temporal");
    expect(threadCategory("describes")).toBe("claim");
    expect(threadCategory("logged_at")).toBe("spatial");
    expect(threadCategory("assigned_to")).toBe("identity");
    expect(threadCategory("something_new")).toBe("other");
    expect(cardKind("device")).toBe("device");
    expect(cardKind("vehicle")).toBe("other");
  });

  it("gives each card type and thread family a distinct ink", () => {
    const cardInks = CARD_KINDS.map((kind) => cardColors[kind].ink);
    expect(new Set(cardInks).size).toBe(cardInks.length);
    const threadInks = THREAD_CATEGORIES.map((c) => threadColors[c].ink);
    expect(new Set(threadInks).size).toBe(threadInks.length);
  });

  it("keeps every ink legible as text on the paper card and canvas", () => {
    const inks = [
      ...Object.values(cardColors).map((color) => color.ink),
      ...Object.values(threadColors).map((color) => color.ink),
    ];
    for (const ink of inks) {
      expect(contrastRatio(ink, PAPER.card)).toBeGreaterThanOrEqual(4.5);
      expect(contrastRatio(ink, PAPER.canvas)).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("keeps inferences and claims dashed and labeled without relying on color", () => {
    expect(threadDash("observed")).toBeUndefined();
    expect(threadDash("inference")).toBeTruthy();
    expect(threadDash("claim")).toBeTruthy();
    expect(threadDash("claim")).not.toBe(threadDash("inference"));
    expect(threadBadge("communication", "observed")).toBeUndefined();
    expect(threadBadge("identity", "inferred")).toBe("Inferred identity");
    expect(threadBadge("claim", "observed")).toBe("Claim");
    expect(threadBadge("contradicts", "inferred")).toBe(
      "Contradiction · inferred",
    );
  });

  it("marks only ML, agent and LLM origins, in a neutral readable ink", () => {
    expect(markedOrigin("ml")).toBe("ml");
    expect(markedOrigin("agent")).toBe("agent");
    expect(markedOrigin("rules")).toBeUndefined();
    expect(markedOrigin(undefined)).toBeUndefined();
    expect(contrastRatio(ORIGIN_INK, PAPER.card)).toBeGreaterThanOrEqual(4.5);
    expect(contrastRatio(ORIGIN_INK, PAPER.canvas)).toBeGreaterThanOrEqual(4.5);
    expect(originLabel("ml", "ml_signals", "KMeans")).toBe(
      "Traditional ML (KMeans) · stage ml_signals",
    );
    expect(originLabel("agent")).toContain("Deepagents investigator");
  });
});
