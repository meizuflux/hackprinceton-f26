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
  media?: { kind: "photo" | "video" };
}): PinDimensions {
  if (node.size?.width && node.size?.height) {
    return { width: node.size.width, height: node.size.height };
  }

  // Photo-on-corkboard cards: a 4:3 photo or 16:9 clip frame above the label.
  if (node.media) {
    return node.media.kind === "video"
      ? { width: 264, height: 304 }
      : { width: 264, height: 348 };
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

/** Left-to-right bands: who and what they used, what they said, what happened, where. */
const BAND_ORDER = ["device", "person", "statement", "event", "location"];
const BAND_GAP_X = 96;
const ROW_GAP_Y = 56;

/**
 * Presentation-only layout for backend graphs, whose nodes arrive with column
 * placeholders. Groups nodes into bands by type, wraps tall bands into
 * sub-columns, orders each band by the average row of its neighbours to
 * shorten threads, and centres every column vertically. Never adds, removes or
 * reorders evidence: it only returns positions.
 */
export function layoutCaseGraph(
  nodes: Array<{
    id: string;
    type: string;
    gapId?: string;
    size?: { width: number; height: number };
    media?: { kind: "photo" | "video" };
  }>,
  edges: Array<{ source: string; target: string }>,
): Map<string, Point> {
  const neighbours = new Map<string, string[]>();
  for (const node of nodes) neighbours.set(node.id, []);
  for (const edge of edges) {
    neighbours.get(edge.source)?.push(edge.target);
    neighbours.get(edge.target)?.push(edge.source);
  }
  const maxRows = Math.max(5, Math.ceil(Math.sqrt(nodes.length) * 1.1));
  const bands = BAND_ORDER.map((type) =>
    nodes.filter((node) => node.type === type),
  );
  const others = nodes.filter((node) => !BAND_ORDER.includes(node.type));
  if (others.length) bands.push(others);

  // Initial order: most connected first, so hubs sit in the middle rows.
  const rank = new Map<string, number>();
  for (const band of bands) {
    band.sort(
      (a, b) =>
        (neighbours.get(b.id)?.length ?? 0) -
          (neighbours.get(a.id)?.length ?? 0) || a.id.localeCompare(b.id),
    );
    band.forEach((node, index) => rank.set(node.id, index / band.length));
  }
  for (let sweep = 0; sweep < 4; sweep++) {
    for (const band of bands) {
      const centre = new Map<string, number>();
      for (const node of band) {
        const around = (neighbours.get(node.id) ?? [])
          .map((id) => rank.get(id))
          .filter((value): value is number => value !== undefined);
        centre.set(
          node.id,
          around.length
            ? around.reduce((sum, value) => sum + value, 0) / around.length
            : (rank.get(node.id) ?? 0.5),
        );
      }
      band.sort(
        (a, b) =>
          centre.get(a.id)! - centre.get(b.id)! || a.id.localeCompare(b.id),
      );
      band.forEach((node, index) =>
        rank.set(node.id, (index + 0.5) / band.length),
      );
    }
  }

  const rowHeight =
    Math.max(...nodes.map((node) => getPinDimensions(node).height), 0) +
    ROW_GAP_Y;
  const positions = new Map<string, Point>();
  let x = 0;
  for (const band of bands) {
    if (!band.length) continue;
    const columns = Math.ceil(band.length / maxRows);
    const perColumn = Math.ceil(band.length / columns);
    for (let column = 0; column < columns; column++) {
      // Interleave so each sub-column spans the band's full vertical order.
      const members = band.filter((_, index) => index % columns === column);
      const width = Math.max(
        ...members.map((node) => getPinDimensions(node).width),
      );
      const top = ((maxRows - perColumn) * rowHeight) / 2;
      const stagger = column % 2 ? rowHeight / 2 : 0;
      members.forEach((node, row) =>
        positions.set(node.id, { x, y: top + stagger + row * rowHeight }),
      );
      x += width + BAND_GAP_X;
    }
    x += BAND_GAP_X;
  }
  return positions;
}
