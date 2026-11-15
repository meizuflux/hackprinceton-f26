import { memo } from "react";
import {
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  Position,
  type Edge,
  type EdgeProps,
} from "@xyflow/react";
import { threadColors, type ThreadCategory } from "./board-colors";

export type ThreadData = {
  kind: "observed" | "claim" | "inference";
  category: ThreadCategory;
  /** Color-independent wording for claims, inferences and contradictions. */
  badge?: string;
  label: string;
  directed: boolean;
  isFocused?: boolean;
  isDimmed?: boolean;
  onInspect: () => void;
};

export const ThreadEdge = memo(function ThreadEdge(
  props: EdgeProps<Edge<ThreadData>>,
) {
  const [path, x, y] = getBezierPath({ ...props, curvature: 0.22 });
  const data = props.data;
  if (!data) return null;
  const horizontal =
    props.sourcePosition === Position.Left ||
    props.sourcePosition === Position.Right;
  const labelWidth = horizontal
    ? Math.max(64, Math.min(166, Math.abs(props.targetX - props.sourceX) - 4))
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
          className={`thread-label nodrag nopan ${data.kind} thread-${data.category} ${props.selected || data.isFocused ? "is-selected" : ""} ${data.isDimmed ? "is-dimmed" : ""}`}
          style={{
            transform: `translate(-50%, -50%) translate(${x}px, ${y}px)`,
            maxWidth: labelWidth,
          }}
          onClick={(event) => {
            event.stopPropagation();
            data.onInspect();
          }}
          aria-label={`${data.kind === "observed" ? "Observed" : data.kind === "claim" ? "Claim" : "Inference"}, ${threadColors[data.category].label.toLowerCase()}: ${data.label}. Inspect relationship and sources`}
          title={`${threadColors[data.category].label}: ${data.label}`}
        >
          {data.badge && <strong>{data.badge}</strong>}
          <span>{data.label}</span>
        </button>
      </EdgeLabelRenderer>
    </>
  );
});
