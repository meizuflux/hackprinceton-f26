import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { OriginBadge } from "./OriginBadge";

describe("OriginBadge", () => {
  it("names ML and agent origins in words", () => {
    const ml = renderToStaticMarkup(
      <OriginBadge origin="ml" stage="ml_signals" />,
    );
    expect(ml).toContain("ML");
    expect(ml).toContain("Produced by Traditional ML");
    expect(renderToStaticMarkup(<OriginBadge origin="agent" />)).toContain(
      "Produced by Agent investigator",
    );
  });
  it("leaves record, rules and missing origins unbadged", () => {
    for (const origin of ["record", "rules", undefined] as const)
      expect(renderToStaticMarkup(<OriginBadge origin={origin} />)).toBe("");
  });
});
