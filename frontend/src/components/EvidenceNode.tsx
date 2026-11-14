import { Handle, Position, type NodeProps, type Node } from "@xyflow/react";
import {
  UserRound,
  MapPin,
  Smartphone,
  CalendarClock,
  FileText,
  Link2,
  ArrowUpRight,
  AlertTriangle,
} from "lucide-react";
export type PinData = {
  label: string;
  type: string;
  subtitle?: string;
  summary: string;
  citations: string[];
  time?: string;
  gapId?: string;
  gapScore?: number;
  active?: boolean;
  onInspect: () => void;
};
const icons = {
  person: UserRound,
  location: MapPin,
  device: Smartphone,
  event: CalendarClock,
  statement: FileText,
};
export function EvidenceNode({ data }: NodeProps<Node<PinData>>) {
  const Icon = icons[data.type as keyof typeof icons] || FileText;
  return (
    <div
      className={`evidence-pin ${data.type} ${data.gapId ? "has-gap" : ""} ${data.active ? "active" : ""}`}
    >
      <Handle type="target" position={Position.Top} />
      <span className="pushpin" />
      <div className="pin-type">
        <span>
          <Icon size={12} />
          {data.type}
        </span>
        <ArrowUpRight size={13} />
      </div>
      <h3>{data.label}</h3>
      <p className="pin-subtitle">{data.subtitle}</p>
      <p className="pin-summary">{data.summary}</p>
      {data.time && (
        <div className="pin-time">
          <CalendarClock size={11} />
          {data.time}
        </div>
      )}
      {data.gapId && (
        <div className="pin-gap">
          <AlertTriangle size={11} /> Open question
        </div>
      )}
      <div className="pin-footer">
        <span>
          <Link2 size={11} />
          {data.citations.length} source{data.citations.length === 1 ? "" : "s"}
        </span>
        <button
          className="nodrag nopan pin-inspect"
          onClick={data.onInspect}
          aria-label={`Inspect ${data.label} and sources`}
        >
          Inspect <ArrowUpRight size={12} />
        </button>
      </div>
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}
