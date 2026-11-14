import {
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  Position,
  type Edge,
  type EdgeProps,
} from "@xyflow/react";

export type ThreadData = {
  kind: "observed" | "claim" | "inference";
  label: string;
  onInspect: () => void;
};

export function ThreadEdge(props: EdgeProps<Edge<ThreadData>>) {
  const [path, x, y] = getBezierPath({ ...props, curvature: 0.22 });
  const data = props.data;
  if (!data) return null;
  const horizontal =
    props.sourcePosition === Position.Left ||
    props.sourcePosition === Position.Right;
  const labelWidth = horizontal
    ? Math.max(64, Math.min(166, Math.abs(props.targetX - props.sourceX) - 16))
    : 166;
  return (
    <>
      <BaseEdge
        id={props.id}
        path={path}
        markerEnd={props.markerEnd}
        style={props.style}
        interactionWidth={24}
      />
      <EdgeLabelRenderer>
        <button
          type="button"
          className={`thread-label nodrag nopan ${data.kind} ${props.selected ? "is-selected" : ""}`}
          style={{
            transform: `translate(-50%, -50%) translate(${x}px, ${y}px)`,
            maxWidth: labelWidth,
          }}
          onClick={(event) => {
            event.stopPropagation();
            data.onInspect();
          }}
          aria-label={`${data.kind === "observed" ? "Observed link" : data.kind === "claim" ? "Claim" : "Inference"}: ${data.label}. Inspect relationship and sources`}
          title={data.label}
        >
          {data.kind !== "observed" && (
            <strong>{data.kind === "claim" ? "Claim" : "Inference"}</strong>
          )}
          <span>{data.label}</span>
        </button>
      </EdgeLabelRenderer>
    </>
  );
}
