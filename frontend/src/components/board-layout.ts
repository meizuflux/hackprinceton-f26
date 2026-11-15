export const DEFAULT_PIN_WIDTH = 248;
export const DEFAULT_PIN_HEIGHT = 224;
export const PIN_WIDTH = DEFAULT_PIN_WIDTH;
export const PIN_HEIGHT = DEFAULT_PIN_HEIGHT;
export const PIN_GAP = 40;

export type Point = { x: number; y: number };
export type Pin = {
  id: string;
  position: Point;
  width?: number;
  height?: number;
};

export interface PinDimensions {
  width: number;
  height: number;
}

/** Computes natural, content- and role-aware card dimensions for an organic corkboard look. */
export function getPinDimensions(node: {
  type?: string;
  gapId?: string;
  size?: { width: number; height: number };
}): PinDimensions {
  if (node.size?.width && node.size?.height) {
    return { width: node.size.width, height: node.size.height };
  }

  switch (node.type) {
    case "location":
      // Primary location anchor: wider presence as the hub of activity
      return { width: 276, height: 236 };

    case "statement":
      // Witness / closing statement memo: taller document aspect ratio
      return { width: 256, height: 252 };

    case "event":
      // Incident events: wider with extra vertical space if linked to an open question
      return node.gapId
        ? { width: 264, height: 244 }
        : { width: 252, height: 228 };

    case "device":
      // Hardware devices: camera with recording gap gets extra room; standard reader is compact
      return node.gapId
        ? { width: 252, height: 236 }
        : { width: 240, height: 216 };

    case "person":
      // Person cards: classic compact portrait index card
      return { width: 236, height: 216 };

    default:
      return node.gapId
        ? { width: 256, height: 236 }
        : { width: DEFAULT_PIN_WIDTH, height: DEFAULT_PIN_HEIGHT };
  }
}

/** Presentation geometry only; never changes evidence or relationships. */
export function freePinPosition(
  pinOrPoint: Point | Pin,
  others: Pin[],
  size?: { width?: number; height?: number },
): Point {
  const isPin = "id" in pinOrPoint;
  const position: Point = isPin ? pinOrPoint.position : pinOrPoint;
  const pinWidth = (isPin ? pinOrPoint.width : size?.width) ?? PIN_WIDTH;
  const pinHeight = (isPin ? pinOrPoint.height : size?.height) ?? PIN_HEIGHT;

  const collides = (point: Point) =>
    others.some((other) => {
      const otherWidth = other.width ?? PIN_WIDTH;
      const otherHeight = other.height ?? PIN_HEIGHT;
      return (
        point.x < other.position.x + otherWidth + PIN_GAP &&
        point.x + pinWidth + PIN_GAP > other.position.x &&
        point.y < other.position.y + otherHeight + PIN_GAP &&
        point.y + pinHeight + PIN_GAP > other.position.y
      );
    });

  if (!collides(position)) return position;

  const candidates = others.flatMap((other) => {
    const otherWidth = other.width ?? PIN_WIDTH;
    const otherHeight = other.height ?? PIN_HEIGHT;
    return [
      { x: other.position.x - pinWidth - PIN_GAP, y: position.y },
      { x: other.position.x + otherWidth + PIN_GAP, y: position.y },
      { x: position.x, y: other.position.y - pinHeight - PIN_GAP },
      { x: position.x, y: other.position.y + otherHeight + PIN_GAP },
    ];
  });

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
    placed.push({ ...pin, position: freePinPosition(pin, placed) });
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
