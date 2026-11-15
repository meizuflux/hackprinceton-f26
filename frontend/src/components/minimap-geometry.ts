/** Pure geometry for the board minimap; no React, so it can be unit tested. */
export type Bounds = { x: number; y: number; width: number; height: number };
export type Point = { x: number; y: number };

export interface MapFrame {
  /** Map size in SVG units; the width is fixed and the height follows the pins. */
  width: number;
  height: number;
  /** Flow units to map units. */
  scale: number;
  /** Map position of the content origin. */
  offsetX: number;
  offsetY: number;
  /** The pins, unpadded, in flow units. */
  content: Bounds;
}

export const MAP_WIDTH = 240;
export const MAP_MIN_HEIGHT = 96;
export const MAP_MAX_HEIGHT = 176;
/** Inset of the pins from the map edge, in map units. */
export const MAP_INSET = 7;

export function boundsOf(
  boxes: Array<{ x: number; y: number; width: number; height: number }>,
): Bounds {
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const box of boxes) {
    minX = Math.min(minX, box.x);
    minY = Math.min(minY, box.y);
    maxX = Math.max(maxX, box.x + box.width);
    maxY = Math.max(maxY, box.y + box.height);
  }
  if (!Number.isFinite(minX)) return { x: 0, y: 0, width: 1, height: 1 };
  return {
    x: minX,
    y: minY,
    width: Math.max(maxX - minX, 1),
    height: Math.max(maxY - minY, 1),
  };
}

/**
 * Frames the pins alone. The visible area is deliberately excluded, so the map
 * keeps one scale while the view pans or zooms, and its height follows the
 * pins' aspect ratio so they fill the map instead of floating in margins.
 */
export function frameContent(
  content: Bounds,
  options: {
    width?: number;
    minHeight?: number;
    maxHeight?: number;
    inset?: number;
  } = {},
): MapFrame {
  const width = options.width ?? MAP_WIDTH;
  const minHeight = options.minHeight ?? MAP_MIN_HEIGHT;
  const maxHeight = options.maxHeight ?? MAP_MAX_HEIGHT;
  const inset = options.inset ?? MAP_INSET;
  const innerWidth = width - inset * 2;
  const natural = (content.height / content.width) * innerWidth + inset * 2;
  const height = Math.round(clamp(natural, minHeight, maxHeight));
  const scale = Math.min(
    innerWidth / content.width,
    (height - inset * 2) / content.height,
  );
  return {
    width,
    height,
    scale,
    offsetX: (width - content.width * scale) / 2,
    offsetY: (height - content.height * scale) / 2,
    content,
  };
}

export function flowToMap(frame: MapFrame, point: Point): Point {
  return {
    x: frame.offsetX + (point.x - frame.content.x) * frame.scale,
    y: frame.offsetY + (point.y - frame.content.y) * frame.scale,
  };
}

export function mapToFlow(frame: MapFrame, point: Point): Point {
  return {
    x: frame.content.x + (point.x - frame.offsetX) / frame.scale,
    y: frame.content.y + (point.y - frame.offsetY) / frame.scale,
  };
}

/**
 * The view rectangle in map units, clipped to the map so all four edges stay
 * visible. A view larger than the pins simply outlines the whole map.
 */
export function viewRect(frame: MapFrame, view: Bounds, stroke = 1.5): Bounds {
  const start = flowToMap(frame, view);
  const end = flowToMap(frame, {
    x: view.x + view.width,
    y: view.y + view.height,
  });
  const half = stroke / 2;
  const x0 = clamp(start.x, half, frame.width - half);
  const y0 = clamp(start.y, half, frame.height - half);
  const x1 = clamp(end.x, half, frame.width - half);
  const y1 = clamp(end.y, half, frame.height - half);
  return {
    x: x0,
    y: y0,
    width: Math.max(x1 - x0, 2),
    height: Math.max(y1 - y0, 2),
  };
}

export function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

function clampSpan(
  origin: number,
  size: number,
  contentOrigin: number,
  contentSize: number,
) {
  const span = Math.max(size, 0);
  const contentSpan = Math.max(contentSize, 1);
  // A view larger than the pins may slide only until the pins touch its edge.
  // A smaller view stays inside the pins, so the minimap cannot leave the board.
  if (span >= contentSpan) {
    return clamp(origin, contentOrigin + contentSpan - span, contentOrigin);
  }
  return clamp(origin, contentOrigin, contentOrigin + contentSpan - span);
}

/** Keep a minimap-driven viewport over the pins. Canvas panning is not clamped. */
export function clampViewToContent(view: Bounds, content: Bounds) {
  return {
    x: clampSpan(view.x, view.width, content.x, content.width),
    y: clampSpan(view.y, view.height, content.y, content.height),
  };
}

/**
 * Where a drag should grab the view. Pressing inside the rectangle keeps the
 * grabbed point under the pointer; pressing elsewhere centres the view there.
 * Returns the pointer's offset from the view origin, in flow units.
 */
export function grabOffset(view: Bounds, pointer: Point): Point {
  const inside =
    pointer.x >= view.x &&
    pointer.x <= view.x + view.width &&
    pointer.y >= view.y &&
    pointer.y <= view.y + view.height;
  return inside
    ? { x: pointer.x - view.x, y: pointer.y - view.y }
    : { x: view.width / 2, y: view.height / 2 };
}

/** The clamped view origin for a pointer position and a grab offset. */
export function dragView(
  view: Bounds,
  pointer: Point,
  offset: Point,
  content: Bounds,
): Point {
  return clampViewToContent(
    {
      x: pointer.x - offset.x,
      y: pointer.y - offset.y,
      width: view.width,
      height: view.height,
    },
    content,
  );
}
