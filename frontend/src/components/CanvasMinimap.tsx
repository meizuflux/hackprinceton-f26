import { useId, useMemo, useRef } from "react";
import {
  getBezierPath,
  Position,
  useReactFlow,
  useStore,
  type Edge,
  type Node,
} from "@xyflow/react";
import { relationshipKind } from "./relationships";
import { PIN_WIDTH, PIN_HEIGHT, threadHandles } from "./board-layout";
import { paperOutline } from "./paper-note";

const MAP_WIDTH = 240;
const MAP_HEIGHT = 148;
const MAP_PADDING = 22;

type Bounds = { x: number; y: number; width: number; height: number };

function nodeSize(node: Node) {
  return {
    width: node.measured?.width ?? node.width ?? PIN_WIDTH,
    height: node.measured?.height ?? node.height ?? PIN_HEIGHT,
  };
}

function sceneBounds(nodes: Node[]): Bounds {
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const node of nodes) {
    const { width, height } = nodeSize(node);
    minX = Math.min(minX, node.position.x);
    minY = Math.min(minY, node.position.y);
    maxX = Math.max(maxX, node.position.x + width);
    maxY = Math.max(maxY, node.position.y + height);
  }
  if (!Number.isFinite(minX)) return { x: 0, y: 0, width: 1, height: 1 };
  return {
    x: minX,
    y: minY,
    width: Math.max(maxX - minX, 1),
    height: Math.max(maxY - minY, 1),
  };
}

function unionBounds(a: Bounds, b: Bounds): Bounds {
  const minX = Math.min(a.x, b.x);
  const minY = Math.min(a.y, b.y);
  const maxX = Math.max(a.x + a.width, b.x + b.width);
  const maxY = Math.max(a.y + a.height, b.y + b.height);
  return {
    x: minX,
    y: minY,
    width: Math.max(maxX - minX, 1),
    height: Math.max(maxY - minY, 1),
  };
}

function clamp(value: number, min: number, max: number) {
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

function frameScene(bounds: Bounds) {
  const scale = Math.min(
    (MAP_WIDTH - MAP_PADDING * 2) / bounds.width,
    (MAP_HEIGHT - MAP_PADDING * 2) / bounds.height,
  );
  const offsetX = (MAP_WIDTH - bounds.width * scale) / 2;
  const offsetY = (MAP_HEIGHT - bounds.height * scale) / 2;
  return { scale, offsetX, offsetY };
}

/** Overview of the pins, with a viewport rectangle that tracks pan and zoom. */
export function CanvasMinimap() {
  const rawId = useId();
  const markerId = `minimap-arrow-${rawId.replace(/:/g, "")}`;
  const nodes = useStore((state) => state.nodes);
  const edges = useStore((state) => state.edges);
  const transform = useStore((state) => state.transform);
  const flowWidth = useStore((state) => state.width);
  const flowHeight = useStore((state) => state.height);
  const { setViewport } = useReactFlow();
  const dragging = useRef(false);
  const zoom = transform[2] || 1;
  const view = {
    x: -transform[0] / zoom,
    y: -transform[1] / zoom,
    width: Math.max(flowWidth, 1) / zoom,
    height: Math.max(flowHeight, 1) / zoom,
  };
  // Frame the pins and the visible area together, then scale just enough
  // that the viewport rectangle stays inside the map. Navigation uses the
  // pins alone, so a drag cannot follow the rectangle off the board.
  const scene = useMemo(() => sceneBounds(nodes), [nodes]);
  const bounds = unionBounds(scene, view);
  const { scale, offsetX, offsetY } = frameScene(bounds);
  const frame = useRef({
    bounds,
    scene,
    scale,
    offsetX,
    offsetY,
    flowWidth,
    flowHeight,
  });
  frame.current = {
    bounds,
    scene,
    scale,
    offsetX,
    offsetY,
    flowWidth,
    flowHeight,
  };

  const viewX = (view.x - bounds.x) * scale + offsetX;
  const viewY = (view.y - bounds.y) * scale + offsetY;
  const viewWidth = view.width * scale;
  const viewHeight = view.height * scale;
  const byId = useMemo(
    () => new Map(nodes.map((node) => [node.id, node])),
    [nodes],
  );

  function focusAt(clientX: number, clientY: number, target: Element) {
    const rect = target.getBoundingClientRect();
    const current = frame.current;
    const mapX = ((clientX - rect.left) / rect.width) * MAP_WIDTH;
    const mapY = ((clientY - rect.top) / rect.height) * MAP_HEIGHT;
    const flowX = current.bounds.x + (mapX - current.offsetX) / current.scale;
    const flowY = current.bounds.y + (mapY - current.offsetY) / current.scale;
    const nextZoom = transform[2] || 1;
    const nextView = clampViewToContent(
      {
        x: flowX - Math.max(current.flowWidth, 1) / nextZoom / 2,
        y: flowY - Math.max(current.flowHeight, 1) / nextZoom / 2,
        width: Math.max(current.flowWidth, 1) / nextZoom,
        height: Math.max(current.flowHeight, 1) / nextZoom,
      },
      current.scene,
    );
    void setViewport({
      x: -nextView.x * nextZoom,
      y: -nextView.y * nextZoom,
      zoom: nextZoom,
    });
  }

  return (
    <div className="board-minimap nopan nodrag nowheel">
      <svg
        className="board-minimap-map"
        viewBox={`0 0 ${MAP_WIDTH} ${MAP_HEIGHT}`}
        role="application"
        aria-label="Canvas overview. Drag to move the view."
        onPointerDown={(event) => {
          if (event.button !== 0) return;
          event.stopPropagation();
          dragging.current = true;
          event.currentTarget.setPointerCapture(event.pointerId);
          focusAt(event.clientX, event.clientY, event.currentTarget);
        }}
        onPointerMove={(event) => {
          if (!dragging.current) return;
          focusAt(event.clientX, event.clientY, event.currentTarget);
        }}
        onPointerUp={() => {
          dragging.current = false;
        }}
        onPointerCancel={() => {
          dragging.current = false;
        }}
        onWheel={(event) => {
          event.stopPropagation();
        }}
      >
        <defs>
          <marker
            id={markerId}
            viewBox="0 0 8 8"
            refX={7}
            refY={4}
            markerWidth={4}
            markerHeight={4}
            orient="auto"
          >
            <path d="M0 0 L8 4 L0 8 Z" fill="#a1372f" />
          </marker>
        </defs>
        {edges.map((edge) => (
          <MinimapEdge
            key={edge.id}
            edge={edge}
            nodes={byId}
            frame={{ bounds, scale, offsetX, offsetY }}
            markerId={markerId}
          />
        ))}
        {nodes.map((node) => {
          const { width, height } = nodeSize(node);
          const x = offsetX + (node.position.x - bounds.x) * scale;
          const y = offsetY + (node.position.y - bounds.y) * scale;
          return (
            <g key={node.id}>
              <path
                d={paperOutline(node.id)}
                transform={`translate(${x} ${y}) scale(${(width * scale) / PIN_WIDTH} ${(height * scale) / PIN_HEIGHT})`}
                className={`board-minimap-pin ${node.data.gapId ? "is-gap" : ""} ${node.data.active ? "is-active" : ""}`}
                vectorEffect="non-scaling-stroke"
              />
              <circle
                className="board-minimap-pushpin"
                cx={x + (width * scale) / 2}
                cy={y + ((9.5 * height) / PIN_HEIGHT) * scale}
                r={Math.max(0.65, 3.5 * scale)}
              />
            </g>
          );
        })}
        <rect
          className="board-minimap-view"
          x={viewX}
          y={viewY}
          width={Math.max(viewWidth, 1)}
          height={Math.max(viewHeight, 1)}
          rx={3}
        />
      </svg>
      <span className="board-minimap-zoom">{Math.round(zoom * 100)}%</span>
    </div>
  );
}

function MinimapEdge({
  edge,
  nodes,
  frame,
  markerId,
}: {
  edge: Edge;
  nodes: Map<string, Node>;
  frame: { bounds: Bounds; scale: number; offsetX: number; offsetY: number };
  markerId: string;
}) {
  const source = nodes.get(edge.source);
  const target = nodes.get(edge.target);
  if (!source || !target) return null;
  const sourceSize = nodeSize(source);
  const targetSize = nodeSize(target);
  const handles = threadHandles(source.position, target.position);
  const sourceSide = handles.sourceHandle.slice("source-".length) as Position;
  const targetSide = handles.targetHandle.slice("target-".length) as Position;
  const attachment = (
    node: Node,
    size: { width: number; height: number },
    side: Position,
  ) => ({
    x:
      frame.offsetX +
      (node.position.x +
        (side === Position.Left
          ? 0
          : side === Position.Right
            ? size.width
            : size.width / 2) -
        frame.bounds.x) *
        frame.scale,
    y:
      frame.offsetY +
      (node.position.y +
        (side === Position.Top
          ? 0
          : side === Position.Bottom
            ? size.height
            : size.height / 2) -
        frame.bounds.y) *
        frame.scale,
  });
  const start = attachment(source, sourceSize, sourceSide);
  const end = attachment(target, targetSize, targetSide);
  const [path] = getBezierPath({
    sourceX: start.x,
    sourceY: start.y,
    sourcePosition: sourceSide,
    targetX: end.x,
    targetY: end.y,
    targetPosition: targetSide,
    curvature: 0.22,
  });
  const inferred = edge.data?.kind
    ? edge.data.kind !== "observed"
    : relationshipKind(edge.type ?? "") !== "observed";
  return (
    <path
      d={path}
      className={`board-minimap-thread ${inferred ? "is-inferred" : ""} ${edge.selected ? "is-active" : ""}`}
      markerEnd={edge.data?.directed === true ? `url(#${markerId})` : undefined}
    />
  );
}
