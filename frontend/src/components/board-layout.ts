import { rawLabelNote } from "./readable";

export const DEFAULT_PIN_WIDTH = 248;
export const DEFAULT_PIN_HEIGHT = 184;
/** The paper outline's drawing space, and the size assumed for a card without one. */
export const PIN_WIDTH = 248;
export const PIN_HEIGHT = 224;
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

/** Card shape by role: a person is a name tag, phones, accounts and places are compact. */
export type CardVariant = "person" | "compact" | "full";

/** Analysis cards (ML, agent, LLM) carry a sentence of reasoning, so they keep the full shape. */
const DERIVED_ORIGINS = new Set(["ml", "agent", "llm"]);

export function cardVariant(node: {
  type?: string;
  origin?: string;
  media?: unknown;
}): CardVariant {
  if (node.media) return "full";
  if (DERIVED_ORIGINS.has(node.origin ?? "")) return "full";
  if (node.type === "person") return "person";
  if (node.type === "device" || node.type === "location") return "compact";
  return "full";
}

/**
 * Card dimensions by role, sized to what each card shows: a person is a small
 * name tag, a phone or place a compact card, events, statements and analysis
 * cards carry a summary, and media cards a print. Presentation only.
 */
export function getPinDimensions(node: {
  type?: string;
  gapId?: string;
  origin?: string;
  label?: string;
  displayLabel?: string;
  size?: { width: number; height: number };
  media?: { kind: "photo" | "video" };
}): PinDimensions {
  if (node.size?.width && node.size?.height) {
    return { width: node.size.width, height: node.size.height };
  }
  // A readable title keeps the record's own label as one extra metadata line.
  const raw =
    node.label !== undefined &&
    rawLabelNote({ label: node.label, displayLabel: node.displayLabel })
      ? 16
      : 0;

  // Photo-on-corkboard cards: a 4:3 photo or 16:9 clip frame above the label.
  if (node.media) {
    return node.media.kind === "video"
      ? { width: 224, height: 256 + raw }
      : { width: 224, height: 288 + raw };
  }

  const variant = cardVariant(node);
  if (variant === "person") return { width: 232, height: 80 + raw };
  if (variant === "compact")
    return {
      width: node.type === "location" ? 228 : 224,
      height: 112 + raw + (node.gapId ? 36 : 0),
    };

  const gap = node.gapId ? 32 : 0;
  if (DERIVED_ORIGINS.has(node.origin ?? ""))
    return { width: 256, height: 200 + raw + gap };
  if (node.type === "statement") return { width: 256, height: 196 + raw + gap };
  return {
    width: node.gapId ? 252 : DEFAULT_PIN_WIDTH,
    height: DEFAULT_PIN_HEIGHT + raw + gap,
  };
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
