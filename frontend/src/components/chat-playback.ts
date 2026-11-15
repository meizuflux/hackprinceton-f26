import type { ChatStep } from "../api/chat";

/** Replay pacing for a chat answer's steps. Presentation only: it never changes what the backend returned. */
export const TOOL_STEP_MS = 450;
const SPEEDUP = 4;
const MIN_TOTAL_MS = 2500;
const MAX_TOTAL_MS = 6000;
const MIN_STEP_MS = 220;
const MIN_TYPE_MS = 700;
const MAX_TYPE_MS = 2000;
const WORD_MS = 28;

export type PlaybackPlan = {
  /** When each step appears, in ms from the start. */
  starts: number[];
  /** How long all steps take before the answer starts to type. */
  stepsMs: number;
  typeMs: number;
};

export function planPlayback(
  steps: readonly ChatStep[],
  words: number,
): PlaybackPlan {
  const typeMs = Math.min(MAX_TYPE_MS, Math.max(MIN_TYPE_MS, words * WORD_MS));
  if (!steps.length) return { starts: [], stepsMs: 0, typeMs };
  const raw = steps.map((s) =>
    s.type === "model_call"
      ? Math.max(s.durationMs, 0)
      : TOOL_STEP_MS * SPEEDUP,
  );
  const sum = raw.reduce((a, b) => a + b, 0) || 1;
  const target = Math.min(MAX_TOTAL_MS, Math.max(MIN_TOTAL_MS, sum / SPEEDUP));
  const durations = raw.map((r) => Math.max(MIN_STEP_MS, (r / sum) * target));
  const starts: number[] = [];
  let at = 0;
  for (const d of durations) {
    starts.push(at);
    at += d;
  }
  return { starts, stepsMs: at, typeMs };
}

export type PlaybackState = {
  phase: "steps" | "typing" | "done";
  stepsShown: number;
  /** Fraction of the answer text typed, 0 to 1. */
  typed: number;
};

export function playbackAt(plan: PlaybackPlan, elapsed: number): PlaybackState {
  const stepsShown = plan.starts.filter((s) => s <= elapsed).length;
  if (elapsed < plan.stepsMs) return { phase: "steps", stepsShown, typed: 0 };
  const typed = (elapsed - plan.stepsMs) / plan.typeMs;
  if (typed >= 1)
    return { phase: "done", stepsShown: plan.starts.length, typed: 1 };
  return { phase: "typing", stepsShown: plan.starts.length, typed };
}

/** Truncates segments to a shared word budget so they type out one after another. */
export function revealSegments(
  segments: readonly string[],
  words: number,
): string[] {
  let left = words;
  return segments.map((text) => {
    const parts = text.match(/\S+\s*/g) ?? [];
    const take = Math.max(0, Math.min(parts.length, left));
    left -= take;
    return parts.slice(0, take).join("").trimEnd();
  });
}

export function countWords(segments: readonly string[]) {
  return segments.reduce((n, t) => n + (t.match(/\S+/g)?.length ?? 0), 0);
}

export function formatTokens(n: number) {
  return n >= 1000
    ? `${(n / 1000).toFixed(1).replace(/\.0$/, "")}k`
    : String(n);
}

export function formatCost(usd: number) {
  if (usd <= 0) return "$0";
  return usd < 0.01 ? `$${usd.toFixed(3)}` : `$${usd.toFixed(2)}`;
}

const toolTitles: Record<string, string> = {
  search_records: "Searching records",
  get_record: "Reading record",
  list_open_questions: "Listing open questions",
  list_explanations: "Reviewing competing explanations",
  list_ml_signals: "Checking model signals",
  list_items: "Listing analysis results",
  get_item: "Opening analysis item",
};

export function stepLabel(step: ChatStep): { title: string; detail: string } {
  if (step.type === "model_call") {
    return {
      title: "Claude",
      detail: `${formatTokens(step.inputTokens)} in / ${formatTokens(step.outputTokens)} out · ${formatCost(step.costUsd)}`,
    };
  }
  const detail = Object.entries(step.args ?? {})
    .filter(([, v]) => v !== "" && v !== null && v !== undefined)
    .map(([k, v]) => `${k}: ${typeof v === "string" ? v : JSON.stringify(v)}`)
    .join(" · ");
  return { title: toolTitles[step.tool] ?? step.tool, detail };
}

export function summarizeSteps(steps: readonly ChatStep[], replayed?: boolean) {
  const tools = steps.filter((s) => s.type === "tool_call").length;
  const models = steps.filter((s) => s.type === "model_call");
  const cost = models.reduce(
    (n, s) => n + (s.type === "model_call" ? s.costUsd : 0),
    0,
  );
  return [
    `Used ${tools} ${tools === 1 ? "tool" : "tools"}`,
    `${models.length} model ${models.length === 1 ? "call" : "calls"}`,
    formatCost(cost),
    replayed === undefined ? "" : replayed ? "replayed" : "live",
  ]
    .filter(Boolean)
    .join(" · ");
}
