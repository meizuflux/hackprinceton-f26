import { describe, expect, it } from "vitest";
import {
  arrangePins,
  freePinPosition,
  getPinDimensions,
  PIN_HEIGHT,
  PIN_WIDTH,
  threadHandles,
  settlePinMoves,
} from "./board-layout";

describe("board geometry", () => {
  it("separates coincident cards without changing their identities", () => {
    const pins = arrangePins(
      Array.from({ length: 30 }, (_, index) => ({
        id: String(index),
        position: { x: 0, y: 0 },
      })),
    );
    expect(new Set(pins.map((pin) => pin.id)).size).toBe(30);
    for (let i = 0; i < pins.length; i++) {
      for (let j = i + 1; j < pins.length; j++) {
        expect(
          Math.abs(pins[i].position.x - pins[j].position.x) >= PIN_WIDTH + 40 ||
            Math.abs(pins[i].position.y - pins[j].position.y) >=
              PIN_HEIGHT + 40,
        ).toBe(true);
      }
    }
  });

  it("keeps a free drop in place and clears an occupied drop", () => {
    const other = [{ id: "other", position: { x: 0, y: 0 } }];
    expect(freePinPosition({ x: 500, y: 500 }, other)).toEqual({
      x: 500,
      y: 500,
    });
    const dropped = freePinPosition({ x: 15, y: 10 }, other);
    expect(
      Math.abs(dropped.x) >= PIN_WIDTH + 40 ||
        Math.abs(dropped.y) >= PIN_HEIGHT + 40,
    ).toBe(true);
  });

  it("connects a card on the right through the facing sides", () => {
    expect(threadHandles({ x: 1000, y: 300 }, { x: 400, y: 250 })).toEqual({
      sourceHandle: "source-left",
      targetHandle: "target-right",
    });
    expect(threadHandles({ x: 400, y: 250 }, { x: 1000, y: 300 })).toEqual({
      sourceHandle: "source-right",
      targetHandle: "target-left",
    });
  });

  it("uses facing vertical sides for vertically arranged cards", () => {
    expect(threadHandles({ x: 100, y: 0 }, { x: 120, y: 400 })).toEqual({
      sourceHandle: "source-bottom",
      targetHandle: "target-top",
    });
  });
  it("settles a group without moving a stationary card or changing list order", () => {
    const pins = [
      { id: "a", position: { x: 0, y: 0 } },
      { id: "b", position: { x: 10, y: 10 } },
      { id: "c", position: { x: 20, y: 20 } },
    ];
    const settled = settlePinMoves(pins, ["b", "c"]);
    expect(settled.map((pin) => pin.id)).toEqual(["a", "b", "c"]);
    expect(settled[0].position).toEqual({ x: 0, y: 0 });
    for (const pin of settled) {
      expect(
        freePinPosition(
          pin.position,
          settled.filter((other) => other.id !== pin.id),
        ),
      ).toEqual(pin.position);
    }
  });

  it("calculates varied card dimensions tailored to evidence roles", () => {
    // Location hub: wider anchor node
    expect(getPinDimensions({ type: "location" })).toEqual({
      width: 276,
      height: 236,
    });
    // Statement memo: taller document aspect ratio
    expect(getPinDimensions({ type: "statement" })).toEqual({
      width: 256,
      height: 252,
    });
    // Incident event with open question: extra room for question alert
    expect(getPinDimensions({ type: "event", gapId: "gap-1" })).toEqual({
      width: 264,
      height: 244,
    });
    // Device with recording gap
    expect(getPinDimensions({ type: "device", gapId: "gap-cam" })).toEqual({
      width: 252,
      height: 236,
    });
    // Standard hardware reader
    expect(getPinDimensions({ type: "device" })).toEqual({
      width: 240,
      height: 216,
    });
    // Compact person card
    expect(getPinDimensions({ type: "person" })).toEqual({
      width: 236,
      height: 216,
    });
    // Explicit size override
    expect(
      getPinDimensions({
        type: "person",
        size: { width: 300, height: 260 },
      }),
    ).toEqual({
      width: 300,
      height: 260,
    });
  });

  it("maintains 40px clearance when placing variable-sized cards", () => {
    const raw = [
      { id: "loc", position: { x: 0, y: 0 }, width: 276, height: 236 },
      { id: "stmt", position: { x: 50, y: 50 }, width: 256, height: 252 },
      { id: "evt", position: { x: 100, y: 100 }, width: 264, height: 244 },
    ];
    const placed = arrangePins(raw);
    for (let i = 0; i < placed.length; i++) {
      for (let j = i + 1; j < placed.length; j++) {
        const a = placed[i];
        const b = placed[j];
        const overlapX =
          a.position.x < b.position.x + b.width + 40 &&
          a.position.x + a.width + 40 > b.position.x;
        const overlapY =
          a.position.y < b.position.y + b.height + 40 &&
          a.position.y + a.height + 40 > b.position.y;
        expect(overlapX && overlapY).toBe(false);
      }
    }
  });
});
