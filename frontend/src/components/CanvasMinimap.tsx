import { useEffect, useId, useMemo, useRef, type KeyboardEvent } from "react";
import {
  ControlButton,
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
import {
  THREAD_CATEGORIES,
  threadCategory,
  threadColors,
} from "./board-colors";
import {
  boundsOf,
  clampViewToContent,
  dragView,
  flowToMap,
  frameContent,
  grabOffset,
  mapToFlow,
  viewRect,
  type Bounds,
  type MapFrame,
  type Point,
} from "./minimap-geometry";

export { clampViewToContent } from "./minimap-geometry";

function nodeSize(node: Node) {
  return {
    width: node.measured?.width ?? node.width ?? PIN_WIDTH,
    height: node.measured?.height ?? node.height ?? PIN_HEIGHT,
  };
}

/** Current viewport in flow units. */
function useFlowView(): Bounds & { zoom: number } {
  const transform = useStore((state) => state.transform);
  const flowWidth = useStore((state) => state.width);
  const flowHeight = useStore((state) => state.height);
  const zoom = transform[2] || 1;
  return {
    x: -transform[0] / zoom,
    y: -transform[1] / zoom,
    width: Math.max(flowWidth, 1) / zoom,
    height: Math.max(flowHeight, 1) / zoom,
    zoom,
  };
}

/**
 * Overview of the pins. The map frames the pins alone, so its scale holds still
 * while the view moves; the viewport rectangle tracks pan and zoom, and dragging
 * it moves the board as if holding the rectangle.
 */
export function CanvasMinimap() {
  const rawId = useId();
  const markerId = `minimap-arrow-${rawId.replace(/:/g, "")}`;
  const nodes = useStore((state) => state.nodes);
  const edges = useStore((state) => state.edges);
  const view = useFlowView();
  const { setViewport } = useReactFlow();
  const frame = useMemo(
    () =>
      frameContent(
        boundsOf(
          nodes.map((node) => ({ ...node.position, ...nodeSize(node) })),
        ),
      ),
    [nodes],
  );
  const latest = useRef({ frame, view });
  latest.current = { frame, view };
  const drag = useRef<{ offset: Point; pointerId: number } | null>(null);
  const byId = useMemo(
    () => new Map(nodes.map((node) => [node.id, node])),
    [nodes],
  );
  const rect = viewRect(frame, view);

  function pointerToFlow(clientX: number, clientY: number, target: Element) {
    const box = target.getBoundingClientRect();
    const { frame: current } = latest.current;
    return mapToFlow(current, {
      x: ((clientX - box.left) / box.width) * current.width,
      y: ((clientY - box.top) / box.height) * current.height,
    });
  }

  function moveTo(origin: Point, duration = 0) {
    const zoom = latest.current.view.zoom;
    void setViewport(
      { x: -origin.x * zoom, y: -origin.y * zoom, zoom },
      duration ? { duration } : undefined,
    );
  }

  function onKeyDown(event: KeyboardEvent<SVGSVGElement>) {
    const step = event.shiftKey ? 0.5 : 0.2;
    const { view: current, frame: currentFrame } = latest.current;
    const delta =
      event.key === "ArrowLeft"
        ? { x: -current.width * step, y: 0 }
        : event.key === "ArrowRight"
          ? { x: current.width * step, y: 0 }
          : event.key === "ArrowUp"
            ? { x: 0, y: -current.height * step }
            : event.key === "ArrowDown"
              ? { x: 0, y: current.height * step }
              : null;
    if (!delta) return;
    event.preventDefault();
    moveTo(
      clampViewToContent(
        { ...current, x: current.x + delta.x, y: current.y + delta.y },
        currentFrame.content,
      ),
      180,
    );
  }

  // Overlays stacked above the minimap (the Ask widget) position themselves from its rendered height,
  // which follows the board's aspect ratio. Published on the board panel, which both share.
  const rootRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const root = rootRef.current;
    const host = root?.closest<HTMLElement>(".case-board-panel");
    if (!root || !host || typeof ResizeObserver === "undefined") return;
    const publish = () =>
      host.style.setProperty("--minimap-height", `${root.offsetHeight}px`);
    publish();
    const observer = new ResizeObserver(publish);
    observer.observe(root);
    return () => {
      observer.disconnect();
      host.style.removeProperty("--minimap-height");
    };
  }, []);

  return (
    <div ref={rootRef} className="board-minimap nopan nodrag nowheel">
      <svg
        className="board-minimap-map"
        viewBox={`0 0 ${frame.width} ${frame.height}`}
        style={{ aspectRatio: `${frame.width} / ${frame.height}` }}
        role="application"
        tabIndex={0}
        aria-label="Canvas overview. Drag the highlighted area, or use the arrow keys, to move the view."
        onKeyDown={onKeyDown}
        onPointerDown={(event) => {
          if (event.button !== 0) return;
          event.stopPropagation();
          event.preventDefault();
          event.currentTarget.focus({ preventScroll: true });
          event.currentTarget.setPointerCapture(event.pointerId);
          const pointer = pointerToFlow(
            event.clientX,
            event.clientY,
            event.currentTarget,
          );
          const { view: current, frame: currentFrame } = latest.current;
          const offset = grabOffset(current, pointer);
          drag.current = { offset, pointerId: event.pointerId };
          moveTo(dragView(current, pointer, offset, currentFrame.content));
        }}
        onPointerMove={(event) => {
          if (drag.current?.pointerId !== event.pointerId) return;
          const pointer = pointerToFlow(
            event.clientX,
            event.clientY,
            event.currentTarget,
          );
          const { view: current, frame: currentFrame } = latest.current;
          moveTo(
            dragView(
              current,
              pointer,
              drag.current.offset,
              currentFrame.content,
            ),
          );
        }}
        onPointerUp={() => {
          drag.current = null;
        }}
        onPointerCancel={() => {
          drag.current = null;
        }}
        onWheel={(event) => {
          event.stopPropagation();
        }}
      >
        <defs>
          {THREAD_CATEGORIES.map((category) => (
            <marker
              key={category}
              id={`${markerId}-${category}`}
              viewBox="0 0 8 8"
              refX={7}
              refY={4}
              markerWidth={4}
              markerHeight={4}
              orient="auto"
            >
              <path d="M0 0 L8 4 L0 8 Z" fill={threadColors[category].ink} />
            </marker>
          ))}
        </defs>
        {edges.map((edge) => (
          <MinimapEdge
            key={edge.id}
            edge={edge}
            nodes={byId}
            frame={frame}
            markerId={markerId}
          />
        ))}
        {nodes.map((node) => {
          const { width, height } = nodeSize(node);
          const { x, y } = flowToMap(frame, node.position);
          const isFocused = Boolean(node.data?.active || node.data?.isFocused);
          return (
            <g
              key={node.id}
              className={`board-minimap-node ${String(node.data?.type ?? "")}`}
            >
              <path
                d={paperOutline(node.id)}
                transform={`translate(${x} ${y}) scale(${(width * frame.scale) / PIN_WIDTH} ${(height * frame.scale) / PIN_HEIGHT})`}
                className={`board-minimap-pin ${node.data.gapId ? "is-gap" : ""} ${node.data.certainty === "inferred" ? "is-inferred" : ""} ${isFocused ? "is-active" : ""}`}
                vectorEffect="non-scaling-stroke"
              />
              <circle
                className="board-minimap-pushpin"
                cx={x + (width * frame.scale) / 2}
                cy={y + ((9.5 * height) / PIN_HEIGHT) * frame.scale}
                r={Math.max(0.9, 4 * frame.scale)}
              />
            </g>
          );
        })}
        <path
          className="board-minimap-mask"
          fillRule="evenodd"
          d={`M0 0H${frame.width}V${frame.height}H0Z M${rect.x} ${rect.y}h${rect.width}v${rect.height}h${-rect.width}Z`}
        />
        <rect
          className="board-minimap-view"
          x={rect.x}
          y={rect.y}
          width={rect.width}
          height={rect.height}
          rx={2}
        />
      </svg>
    </div>
  );
}

/** Zoom readout inside the zoom controls; pressing it returns to 100%. */
export function ZoomReadout() {
  const zoom = useStore((state) => state.transform[2] || 1);
  const { zoomTo } = useReactFlow();
  const percent = Math.round(zoom * 100);
  return (
    <ControlButton
      className="zoom-readout"
      onClick={() => void zoomTo(1, { duration: 200 })}
      aria-label={`Zoom ${percent}%. Reset zoom to 100%`}
      title="Reset zoom to 100%"
    >
      <span>{percent}%</span>
    </ControlButton>
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
  frame: MapFrame;
  markerId: string;
}) {
  const source = nodes.get(edge.source);
  const target = nodes.get(edge.target);
  if (!source || !target) return null;
  const handles = threadHandles(source.position, target.position);
  const sourceSide = handles.sourceHandle.slice("source-".length) as Position;
  const targetSide = handles.targetHandle.slice("target-".length) as Position;
  const attachment = (node: Node, side: Position) => {
    const size = nodeSize(node);
    return flowToMap(frame, {
      x:
        node.position.x +
        (side === Position.Left
          ? 0
          : side === Position.Right
            ? size.width
            : size.width / 2),
      y:
        node.position.y +
        (side === Position.Top
          ? 0
          : side === Position.Bottom
            ? size.height
            : size.height / 2),
    });
  };
  const start = attachment(source, sourceSide);
  const end = attachment(target, targetSide);
  const [path] = getBezierPath({
    sourceX: start.x,
    sourceY: start.y,
    sourcePosition: sourceSide,
    targetX: end.x,
    targetY: end.y,
    targetPosition: targetSide,
    curvature: 0.22,
  });
  const kind = edge.data?.kind ?? relationshipKind(edge.type ?? "");
  const isEdgeActive = Boolean(edge.selected || edge.data?.isFocused);
  return (
    <path
      d={path}
      className={`board-minimap-thread ${String(edge.data?.category ?? "")} ${kind !== "observed" ? `is-${kind}` : ""} ${isEdgeActive ? "is-active" : ""}`}
      markerEnd={
        edge.data?.directed === true
          ? `url(#${markerId}-${threadCategory(String(edge.data?.category ?? edge.type ?? ""))})`
          : undefined
      }
    />
  );
}
