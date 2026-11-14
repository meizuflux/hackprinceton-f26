import { describe, expect, it } from "vitest";
import {
  arrangePins,
  freePinPosition,
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
});
