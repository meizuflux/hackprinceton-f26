import { describe, expect, it } from "vitest";
import { formatCaseTime, insightStrength } from "./presentation";
import { relationshipKind, relationshipLabel } from "./relationships";

describe("relationship certainty", () => {
  it("uses API certainty so inferred links never read as observed", () => {
    expect(relationshipKind("identity", "inferred")).toBe("inference");
    expect(relationshipKind("spatial", "inferred")).toBe("inference");
    expect(relationshipKind("communication", "observed")).toBe("observed");
    expect(relationshipLabel("contradicts", "inferred")).toBe("Inference");
  });

  it("keeps claims as claims and fixture types without certainty unchanged", () => {
    expect(relationshipKind("claim", "observed")).toBe("claim");
    expect(relationshipKind("time_overlap")).toBe("inference");
    expect(relationshipKind("made_by")).toBe("observed");
  });
});

describe("case time display", () => {
  it("formats ISO times in the case time zone", () => {
    expect(formatCaseTime("2026-10-18T05:51:00Z", "America/Los_Angeles")).toBe(
      "Sat 17 Oct, 22:51",
    );
    expect(
      formatCaseTime("2026-10-18T05:51:00Z", "America/Los_Angeles", "full"),
    ).toMatch(/^Sat 17 Oct 2026, 22:51:00 (PDT|GMT-7)$/);
  });

  it("passes through values that are not ISO times", () => {
    expect(formatCaseTime("around 11:30 at night")).toBe(
      "around 11:30 at night",
    );
    expect(formatCaseTime(undefined)).toBe("");
  });
});

describe("insight strength", () => {
  it("shows backend confidence as a label, never a percentage", () => {
    expect(insightStrength({ score: 0.88, confidence: "medium" })).toBe(
      "Medium confidence",
    );
  });
});
