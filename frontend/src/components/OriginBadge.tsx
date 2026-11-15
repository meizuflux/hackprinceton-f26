import { Bot, ScatterChart, Sparkles } from "lucide-react";
import type { Origin } from "../api/types";
import { markedOrigin, originMarks } from "./board-colors";

const originIcons = { ml: ScatterChart, agent: Bot, llm: Sparkles };

export function OriginIcon({
  origin,
  size = 11,
}: {
  origin?: Origin;
  size?: number;
}) {
  const mark = markedOrigin(origin);
  if (!mark) return null;
  const Icon = originIcons[mark];
  return <Icon size={size} strokeWidth={2.4} aria-hidden="true" />;
}

/** Graphite stamp: icon plus word, so origin never relies on colour. */
export function OriginBadge({
  origin,
  stage,
}: {
  origin?: Origin;
  stage?: string;
}) {
  const mark = markedOrigin(origin);
  if (!mark) return null;
  const { chip, label } = originMarks[mark];
  return (
    <span
      className={`origin-badge origin-${mark}`}
      title={stage ? `${label} · stage ${stage}` : label}
    >
      <OriginIcon origin={origin} />
      <span aria-hidden="true">{chip}</span>
      <span className="sr-only">{`Produced by ${label}`}</span>
    </span>
  );
}
