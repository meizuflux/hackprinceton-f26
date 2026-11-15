import { describe, expect, it } from "vitest";
import { clampViewToContent } from "./CanvasMinimap";

const pins = { x: 100, y: 200, width: 800, height: 500 };

describe("minimap navigation bounds", () => {
  it("leaves a view that already covers the pins unchanged", () => {
    expect(
      clampViewToContent({ x: 180, y: 240, width: 300, height: 200 }, pins),
    ).toEqual({ x: 180, y: 240 });
  });

  it("stops a smaller view at the pin edges", () => {
    expect(
      clampViewToContent({ x: 2000, y: -400, width: 300, height: 200 }, pins),
    ).toEqual({ x: 600, y: 200 });
    expect(
      clampViewToContent({ x: -500, y: 900, width: 300, height: 200 }, pins),
    ).toEqual({ x: 100, y: 500 });
  });

  it("keeps the pins inside a zoomed-out view", () => {
    expect(
      clampViewToContent({ x: 4000, y: 4000, width: 2000, height: 1200 }, pins),
    ).toEqual({ x: 100, y: 200 });
    expect(
      clampViewToContent(
        { x: -4000, y: -4000, width: 2000, height: 1200 },
        pins,
      ),
    ).toEqual({ x: -1100, y: -500 });
  });
});
