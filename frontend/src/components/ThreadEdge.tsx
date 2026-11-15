import { memo } from "react";
import {
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  Position,
  type Edge,
  type EdgeProps,
} from "@xyflow/react";
import type { Origin } from "../api/types";
import {
  markedOrigin,
  originMarks,
  threadColors,
  type ThreadCategory,
} from "./board-colors";
import { OriginIcon } from "./OriginBadge";

export type ThreadData = {
  kind: "observed" | "claim" | "inference";
  category: ThreadCategory;
  /** Color-independent wording for claims, inferences and contradictions. */
  badge?: string;
  label: string;
  directed: boolean;
  origin?: Origin;
  isFocused?: boolean;
  isDimmed?: boolean;
  /** Story view: the label waits for hover, focus or selection. */
  quiet?: boolean;
  /** The thread or one of its cards is under the pointer. */
  hovered?: boolean;
  /** Label offset for parallel threads between the same cards, across the thread. */
  labelOffset?: number;
  /** Stands for this many real threads into a group's hidden cards. */
  aggregateCount?: number;
  ariaLabel?: string;
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
    ? Math.max(88, Math.min(166, Math.abs(props.targetX - props.sourceX) - 4))
    : 166;
  const mark = markedOrigin(data.origin);
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
          className={`thread-label nodrag nopan ${data.kind} thread-${data.category} ${props.selected || data.isFocused ? "is-selected" : ""} ${data.isDimmed ? "is-dimmed" : ""} ${data.quiet ? "is-quiet" : ""} ${data.hovered ? "is-hovered" : ""} ${data.aggregateCount ? "is-aggregate" : ""} ${mark ? `has-origin origin-${mark}` : ""}`}
          style={{
            transform: `translate(-50%, -50%) translate(${x + (horizontal ? 0 : (data.labelOffset ?? 0) * 4.25)}px, ${y + (horizontal ? (data.labelOffset ?? 0) : 0)}px)`,
            maxWidth: labelWidth,
          }}
          onClick={(event) => {
            event.stopPropagation();
            data.onInspect();
          }}
          aria-label={
            data.ariaLabel ??
            `${data.kind === "observed" ? "Observed" : data.kind === "claim" ? "Claim" : "Inference"}${mark ? `, from ${originMarks[mark].label}` : ""}, ${threadColors[data.category].label.toLowerCase()}: ${data.label}. Inspect relationship and sources`
          }
          title={
            data.aggregateCount
              ? data.label
              : `${threadColors[data.category].label}: ${data.label}`
          }
        >
          {mark && <OriginIcon origin={data.origin} size={11} />}
          {data.aggregateCount ? (
            <strong className="thread-count">{data.aggregateCount}</strong>
          ) : (
            data.badge && <strong>{data.badge}</strong>
          )}
          <span>{data.label}</span>
        </button>
      </EdgeLabelRenderer>
    </>
  );
});
