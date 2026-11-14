export const PIN_WIDTH = 248;
export const PIN_HEIGHT = 224;
const PIN_GAP = 40;

type Point = { x: number; y: number };
type Pin = { id: string; position: Point };

/** Presentation geometry only; never changes evidence or relationships. */
export function freePinPosition(position: Point, others: Pin[]): Point {
  const collides = (point: Point) =>
    others.some(
      (other) =>
        Math.abs(point.x - other.position.x) < PIN_WIDTH + PIN_GAP &&
        Math.abs(point.y - other.position.y) < PIN_HEIGHT + PIN_GAP,
    );
  if (!collides(position)) return position;
  const candidates = others.flatMap(({ position: other }) => [
    { x: other.x - PIN_WIDTH - PIN_GAP, y: position.y },
    { x: other.x + PIN_WIDTH + PIN_GAP, y: position.y },
    { x: position.x, y: other.y - PIN_HEIGHT - PIN_GAP },
    { x: position.x, y: other.y + PIN_HEIGHT + PIN_GAP },
  ]);
  return (
    candidates
      .filter((candidate) => !collides(candidate))
      .sort(
        (a, b) =>
          Math.hypot(a.x - position.x, a.y - position.y) -
          Math.hypot(b.x - position.x, b.y - position.y),
      )[0] ?? position
  );
}

export function arrangePins<T extends Pin>(pins: T[]): T[] {
  const placed: T[] = [];
  for (const pin of pins) {
    placed.push({ ...pin, position: freePinPosition(pin.position, placed) });
  }
  return placed;
}

/** Settle a group drop or keyboard move while keeping stationary cards still. */
export function settlePinMoves<T extends Pin>(
  pins: T[],
  movedIds: string[],
): T[] {
  const moving = new Set(movedIds);
  const settled = arrangePins([
    ...pins.filter((pin) => !moving.has(pin.id)),
    ...pins.filter((pin) => moving.has(pin.id)),
  ]);
  const byId = new Map(settled.map((pin) => [pin.id, pin]));
  return pins.map((pin) => byId.get(pin.id)!);
}

export function threadHandles(source: Point, target: Point) {
  const dx = target.x - source.x;
  const dy = target.y - source.y;
  if (Math.abs(dx) > Math.abs(dy)) {
    return dx >= 0
      ? { sourceHandle: "source-right", targetHandle: "target-left" }
      : { sourceHandle: "source-left", targetHandle: "target-right" };
  }
  return dy >= 0
    ? { sourceHandle: "source-bottom", targetHandle: "target-top" }
    : { sourceHandle: "source-top", targetHandle: "target-bottom" };
}
