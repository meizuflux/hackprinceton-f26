import { describe, expect, it } from "vitest";
import {
  clampViewToContent,
  dragView,
  flowToMap,
  frameContent,
  grabOffset,
  mapToFlow,
  unionBounds,
  viewRect,
} from "./minimap-geometry";

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

describe("minimap framing", () => {
  it("sizes the map to the pins so a wide board has no vertical margins", () => {
    const frame = frameContent(
      { x: 0, y: 0, width: 3000, height: 1500 },
      { width: 240, inset: 7 },
    );
    expect(frame.height).toBe(Math.round((1500 / 3000) * 226 + 14));
    const topLeft = flowToMap(frame, { x: 0, y: 0 });
    const bottomRight = flowToMap(frame, { x: 3000, y: 1500 });
    expect(topLeft.x).toBeCloseTo(7);
    expect(bottomRight.x).toBeCloseTo(233);
    expect(topLeft.y).toBeCloseTo(7, 0);
    expect(bottomRight.y).toBeCloseTo(frame.height - 7, 0);
  });

  it("clamps very tall or very flat boards and centres them", () => {
    const flat = frameContent({ x: 0, y: 0, width: 10000, height: 100 });
    expect(flat.height).toBe(96);
    expect(flat.offsetY).toBeGreaterThan(40);
    const tall = frameContent({ x: 0, y: 0, width: 100, height: 10000 });
    expect(tall.height).toBe(176);
    expect(tall.offsetX).toBeGreaterThan(100);
  });

  it("keeps one scale regardless of where the view is", () => {
    const frame = frameContent({ x: -200, y: 50, width: 2400, height: 1200 });
    const point = { x: 900, y: 600 };
    const back = mapToFlow(frame, flowToMap(frame, point));
    expect(back.x).toBeCloseTo(point.x);
    expect(back.y).toBeCloseTo(point.y);
  });

  it("rescales to keep a view that leaves the pins on the map, without resizing it", () => {
    const pins = { x: 0, y: 0, width: 2000, height: 1000 };
    const view = { x: 3000, y: -500, width: 1000, height: 600 };
    const extent = unionBounds(pins, view);
    expect(extent).toEqual({ x: 0, y: -500, width: 4000, height: 1500 });
    const pinsOnly = frameContent(pins);
    const framed = frameContent(extent, { pins });
    // Same map size, smaller scale.
    expect(framed.width).toBe(pinsOnly.width);
    expect(framed.height).toBe(pinsOnly.height);
    expect(framed.scale).toBeLessThan(pinsOnly.scale);
    // The whole view rectangle lands inside the map.
    const start = flowToMap(framed, view);
    const end = flowToMap(framed, {
      x: view.x + view.width,
      y: view.y + view.height,
    });
    expect(start.x).toBeGreaterThanOrEqual(0);
    expect(start.y).toBeGreaterThanOrEqual(0);
    expect(end.x).toBeLessThanOrEqual(framed.width);
    expect(end.y).toBeLessThanOrEqual(framed.height);
  });

  it("frames the pins alone while the view stays over them", () => {
    const pins = { x: 0, y: 0, width: 2000, height: 1000 };
    expect(
      unionBounds(pins, { x: 200, y: 100, width: 600, height: 400 }),
    ).toEqual(pins);
  });

  it("clips the view rectangle to the map so every edge stays visible", () => {
    const frame = frameContent({ x: 0, y: 0, width: 2000, height: 1000 });
    const rect = viewRect(frame, {
      x: -5000,
      y: -5000,
      width: 20000,
      height: 20000,
    });
    expect(rect.x).toBeCloseTo(0.75);
    expect(rect.y).toBeCloseTo(0.75);
    expect(rect.x + rect.width).toBeCloseTo(frame.width - 0.75);
    expect(rect.y + rect.height).toBeCloseTo(frame.height - 0.75);
  });
});

describe("minimap dragging", () => {
  const content = { x: 0, y: 0, width: 2000, height: 1000 };
  const view = { x: 400, y: 200, width: 600, height: 400 };

  it("keeps the grabbed point under the pointer inside the view", () => {
    const pointer = { x: 500, y: 300 };
    const offset = grabOffset(view, pointer);
    expect(offset).toEqual({ x: 100, y: 100 });
    expect(dragView(view, pointer, offset, content)).toEqual({
      x: 400,
      y: 200,
    });
    expect(dragView(view, { x: 800, y: 450 }, offset, content)).toEqual({
      x: 700,
      y: 350,
    });
  });

  it("centres the view on a press outside it", () => {
    const pointer = { x: 1500, y: 700 };
    const offset = grabOffset(view, pointer);
    expect(dragView(view, pointer, offset, content)).toEqual({
      x: 1200,
      y: 500,
    });
  });

  it("stops at the pin edges while dragging", () => {
    const offset = { x: 300, y: 200 };
    expect(dragView(view, { x: 5000, y: -900 }, offset, content)).toEqual({
      x: 1400,
      y: 0,
    });
  });
});
