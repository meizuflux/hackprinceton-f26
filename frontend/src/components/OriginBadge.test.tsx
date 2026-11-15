import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { OriginBadge } from "./OriginBadge";

describe("OriginBadge", () => {
  it("names ML and agent origins in words", () => {
    const ml = renderToStaticMarkup(
      <OriginBadge origin="ml" stage="ml_signals" />,
    );
    expect(ml).toContain("ML model");
    expect(ml).toContain("Produced by Traditional ML model");
    const agent = renderToStaticMarkup(<OriginBadge origin="agent" />);
    expect(agent).toContain("AI agent");
    expect(agent).toContain("Produced by AI agent investigator");
  });
  it("leaves record, rules and missing origins unbadged", () => {
    for (const origin of ["record", "rules", undefined] as const)
      expect(renderToStaticMarkup(<OriginBadge origin={origin} />)).toBe("");
  });
});
