import { useRef } from "react";
import { useReactFlow, useStore, type Edge, type Node } from "@xyflow/react";

const MAP_WIDTH = 240;
const MAP_HEIGHT = 148;
const MAP_PADDING = 22;

type Bounds = { x: number; y: number; width: number; height: number };

function nodeSize(node: Node) {
  return {
    width: node.measured?.width ?? node.width ?? 210,
    height: node.measured?.height ?? node.height ?? 118,
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
  // that the viewport rectangle stays inside the map.
  const bounds = unionBounds(sceneBounds(nodes), view);
  const { scale, offsetX, offsetY } = frameScene(bounds);
  const frame = useRef({
    bounds,
    scale,
    offsetX,
    offsetY,
    flowWidth,
    flowHeight,
  });
  frame.current = { bounds, scale, offsetX, offsetY, flowWidth, flowHeight };

  const viewX = (view.x - bounds.x) * scale + offsetX;
  const viewY = (view.y - bounds.y) * scale + offsetY;
  const viewWidth = view.width * scale;
  const viewHeight = view.height * scale;
  const byId = new Map(nodes.map((node) => [node.id, node]));

  function focusAt(clientX: number, clientY: number, target: Element) {
    const rect = target.getBoundingClientRect();
    const current = frame.current;
    const mapX = ((clientX - rect.left) / rect.width) * MAP_WIDTH;
    const mapY = ((clientY - rect.top) / rect.height) * MAP_HEIGHT;
    const flowX = current.bounds.x + (mapX - current.offsetX) / current.scale;
    const flowY = current.bounds.y + (mapY - current.offsetY) / current.scale;
    const nextZoom = transform[2] || 1;
    void setViewport({
      x: current.flowWidth / 2 - flowX * nextZoom,
      y: current.flowHeight / 2 - flowY * nextZoom,
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
        {edges.map((edge) => (
          <MinimapEdge
            key={edge.id}
            edge={edge}
            nodes={byId}
            frame={{ bounds, scale, offsetX, offsetY }}
          />
        ))}
        {nodes.map((node) => {
          const { width, height } = nodeSize(node);
          const x = offsetX + (node.position.x - bounds.x) * scale;
          const y = offsetY + (node.position.y - bounds.y) * scale;
          return (
            <rect
              key={node.id}
              x={x}
              y={y}
              width={Math.max(width * scale, 1.5)}
              height={Math.max(height * scale, 1.5)}
              rx={1.5}
              className={node.data.gapId ? "is-gap" : undefined}
            />
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
}: {
  edge: Edge;
  nodes: Map<string, Node>;
  frame: { bounds: Bounds; scale: number; offsetX: number; offsetY: number };
}) {
  const source = nodes.get(edge.source);
  const target = nodes.get(edge.target);
  if (!source || !target) return null;
  const sourceSize = nodeSize(source);
  const targetSize = nodeSize(target);
  const x1 =
    frame.offsetX +
    (source.position.x + sourceSize.width / 2 - frame.bounds.x) * frame.scale;
  const y1 =
    frame.offsetY +
    (source.position.y + sourceSize.height / 2 - frame.bounds.y) * frame.scale;
  const x2 =
    frame.offsetX +
    (target.position.x + targetSize.width / 2 - frame.bounds.x) * frame.scale;
  const y2 =
    frame.offsetY +
    (target.position.y + targetSize.height / 2 - frame.bounds.y) * frame.scale;
  const inferred = [
    "claim",
    "describes",
    "reported_near",
    "time_overlap",
  ].includes(edge.type ?? "");
  return (
    <line
      x1={x1}
      y1={y1}
      x2={x2}
      y2={y2}
      className={inferred ? "is-inferred" : undefined}
    />
  );
}
