import type { TraceEvent, TracePhase } from "../api/types";

/**
 * Pure helpers for the run replay. They only pace and summarise what the
 * backend trace recorded; they never create case facts.
 */

export const phaseOrder: ReadonlyArray<{
  id: TracePhase;
  label: string;
}> = [
  { id: "ingest", label: "Ingest" },
  { id: "rules", label: "Rules" },
  { id: "ml", label: "ML" },
  { id: "llm", label: "LLM claims" },
  { id: "agent", label: "Agent" },
  { id: "output", label: "Output" },
];

export const speeds = [1, 10, 50] as const;
export const defaultSpeed = 10;

const num = (value: unknown): number =>
  typeof value === "number" && Number.isFinite(value) ? value : 0;
const str = (value: unknown): string =>
  typeof value === "string" ? value : "";

/** Advance the replay clock by wall time at a speed, never past `capMs`. */
export function advanceClock(
  tMs: number,
  wallDeltaMs: number,
  speed: number,
  capMs: number,
): number {
  if (wallDeltaMs <= 0 || speed <= 0) return Math.min(tMs, capMs);
  return Math.min(capMs, tMs + wallDeltaMs * speed);
}

/** Number of events (sorted by seq/tMs) at or before the clock. */
export function countUpTo(events: readonly TraceEvent[], tMs: number): number {
  let lo = 0;
  let hi = events.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (events[mid].tMs <= tMs) lo = mid + 1;
    else hi = mid;
  }
  return lo;
}

/** Merge a polled page into the events already held, keeping seq order and dropping repeats. */
export function mergeEvents(
  held: readonly TraceEvent[],
  incoming: readonly TraceEvent[],
): TraceEvent[] {
  const last = held.at(-1)?.seq ?? 0;
  const fresh = incoming.filter((event) => event.seq > last);
  return fresh.length ? [...held, ...fresh] : (held as TraceEvent[]);
}

/** The clock position that ends the run: the final event's time. */
export function runEndMs(events: readonly TraceEvent[]): number {
  const finished = [...events].reverse().find((e) => e.type === "run_finished");
  return Math.max(num(finished?.durationMs), events.at(-1)?.tMs ?? 0);
}

export type PhaseState = {
  status: "pending" | "running" | "done";
  durationMs?: number;
};

export interface TraceProgress {
  filesHashed: number;
  filesParsed: number;
  records: number;
  recordTypes: Record<string, number>;
  entities: number;
  links: number;
  mlSignals: number;
  llmCalls: number;
  toolCalls: number;
  insights: number;
  inputTokens: number;
  outputTokens: number;
  costUsd: number;
  phases: Record<TracePhase, PhaseState>;
  parsedEvidence: Set<string>;
  stagesFinished: Set<string>;
  insightKeys: Set<string>;
  insightIds: Set<string>;
  signalIds: Set<string>;
  /** `run_finished` has been reached on the clock. */
  finished: boolean;
  failed: boolean;
  /** Model reported by `run_started`, if any. */
  model: string | null;
}

export function emptyProgress(): TraceProgress {
  return {
    filesHashed: 0,
    filesParsed: 0,
    records: 0,
    recordTypes: {},
    entities: 0,
    links: 0,
    mlSignals: 0,
    llmCalls: 0,
    toolCalls: 0,
    insights: 0,
    inputTokens: 0,
    outputTokens: 0,
    costUsd: 0,
    phases: Object.fromEntries(
      phaseOrder.map((p) => [p.id, { status: "pending" }]),
    ) as Record<TracePhase, PhaseState>,
    parsedEvidence: new Set(),
    stagesFinished: new Set(),
    insightKeys: new Set(),
    insightIds: new Set(),
    signalIds: new Set(),
    finished: false,
    failed: false,
    model: null,
  };
}

/** Fold the events revealed so far into counters, phase states and reveal sets. */
export function summarize(events: readonly TraceEvent[]): TraceProgress {
  const p = emptyProgress();
  for (const e of events) {
    const phase = p.phases[e.phase];
    if (phase && phase.status === "pending") phase.status = "running";
    switch (e.type) {
      case "run_started":
        p.model = str(e.model) || null;
        break;
      case "phase_finished":
        if (phase) {
          phase.status = "done";
          phase.durationMs = num(e.durationMs);
        }
        break;
      case "file_hashed":
        p.filesHashed += 1;
        break;
      case "file_parsed": {
        p.filesParsed += 1;
        p.records += num(e.records);
        p.parsedEvidence.add(str(e.evidenceId));
        const types = e.recordTypes;
        if (types && typeof types === "object")
          for (const [name, count] of Object.entries(types))
            p.recordTypes[name] = (p.recordTypes[name] ?? 0) + num(count);
        break;
      }
      case "entities_linked":
        p.entities = num(e.entities);
        p.links = num(e.links);
        break;
      case "stage_finished":
        p.stagesFinished.add(str(e.stage));
        break;
      case "ml_signal":
        p.mlSignals += 1;
        p.signalIds.add(str(e.id));
        break;
      case "llm_call":
        p.llmCalls += 1;
        p.inputTokens +=
          num(e.inputTokens) + num(e.cacheReadTokens) + num(e.cacheWriteTokens);
        p.outputTokens += num(e.outputTokens);
        p.costUsd += num(e.costUsd);
        break;
      case "agent_tool":
        p.toolCalls += 1;
        break;
      case "insight_recorded":
        p.insights += 1;
        p.insightIds.add(str(e.id));
        if (e.key) p.insightKeys.add(str(e.key));
        break;
      case "run_finished":
        p.finished = true;
        p.failed = e.status === "failed";
        if (phase) phase.status = "done";
        break;
    }
  }
  return p;
}

const short = (value: unknown, max = 60) => {
  const text = typeof value === "string" ? value : JSON.stringify(value);
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
};

/** One feed line for an event, e.g. "agent → search_records {query: 'badge'}". */
export function describeEvent(e: TraceEvent): string {
  switch (e.type) {
    case "run_started":
      return `run started${e.model ? ` · ${str(e.model)}` : ""}`;
    case "phase_started":
      return str(e.label) || `${e.phase} started`;
    case "phase_finished":
      return `${str(e.label) || e.phase} done in ${formatDuration(num(e.durationMs))}`;
    case "file_hashed":
      return `hashed ${str(e.evidenceId)} ${str(e.filename)}${e.manifestMatch === false ? " (manifest mismatch)" : ""}`;
    case "file_parsed":
      return `parsed ${str(e.evidenceId)} ${str(e.filename)} · ${num(e.records)} records`;
    case "entities_linked":
      return `linked ${num(e.entities)} entities (${num(e.links)} links)`;
    case "stage_finished":
      return `${str(e.label) || str(e.stage)} finished`;
    case "ml_signal":
      return `ML ${str(e.id)} ${str(e.title)}`;
    case "llm_call":
      return `${e.phase} → ${str(e.purpose)} call · ${formatTokens(num(e.inputTokens) + num(e.outputTokens))} tokens · ${formatCost(num(e.costUsd))}`;
    case "agent_tool": {
      const args = e.args && typeof e.args === "object" ? e.args : {};
      const body = Object.entries(args as Record<string, unknown>)
        .map(
          ([k, v]) =>
            `${k}: ${typeof v === "string" ? `'${short(v, 40)}'` : short(v, 20)}`,
        )
        .join(", ");
      return `agent → ${str(e.tool)} {${body}}`;
    }
    case "insight_recorded":
      return `insight ${str(e.id)} ${str(e.title)}`;
    case "run_finished":
      return e.status === "failed" ? "run failed" : "run finished";
    default:
      return String(e.type);
  }
}

/** m:ss for a clock reading. */
export function formatDuration(ms: number): string {
  const total = Math.max(0, Math.round(ms / 1000));
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

export function formatTokens(count: number): string {
  if (count >= 1_000_000) return `${(count / 1_000_000).toFixed(2)}M`;
  if (count >= 1000) return `${(count / 1000).toFixed(1)}k`;
  return String(Math.round(count));
}

export function formatCost(usd: number): string {
  return `$${usd.toFixed(usd < 1 ? 3 : 2)}`;
}

/** Minimum on-screen time per phase, so short phases stay watchable. */
export const phaseMinWallMs: Partial<Record<TracePhase, number>> = {
  ingest: 4000,
  rules: 2000,
  ml: 2500,
};

export interface PhaseSegment {
  phase: TracePhase;
  startMs: number;
  endMs: number;
}

/**
 * Split the replay clock into phase segments at each phase's first event.
 * Phases without events get no segment. The last segment ends at `endMs`.
 */
export function phaseSegments(
  events: readonly TraceEvent[],
  endMs: number,
): PhaseSegment[] {
  const starts: Array<{ phase: TracePhase; startMs: number }> = [];
  for (const e of events) {
    if (!starts.some((s) => s.phase === e.phase))
      starts.push({ phase: e.phase, startMs: e.tMs });
  }
  starts.sort((a, b) => a.startMs - b.startMs);
  return starts.map((s, i) => ({
    phase: s.phase,
    startMs: i === 0 ? 0 : s.startMs,
    endMs:
      i + 1 < starts.length
        ? starts[i + 1].startMs
        : Math.max(endMs, s.startMs),
  }));
}

function segmentAt(
  segments: readonly PhaseSegment[],
  tMs: number,
): PhaseSegment | undefined {
  return (
    segments.find(
      (s) => s.endMs > s.startMs && tMs >= s.startMs && tMs < s.endMs,
    ) ?? undefined
  );
}

/** Replay-clock milliseconds advanced per wall millisecond at `tMs`. */
export function playbackRate(
  tMs: number,
  segments: readonly PhaseSegment[],
  speed: number,
): number {
  const seg = segmentAt(segments, tMs);
  const min = seg ? (phaseMinWallMs[seg.phase] ?? 0) : 0;
  if (!seg || !min) return speed;
  return Math.min(speed, (seg.endMs - seg.startMs) / min);
}

/** The phase being slowed for legibility at `tMs`, with its effective speed; undefined at the chosen speed. */
export function slowedPhase(
  tMs: number,
  segments: readonly PhaseSegment[],
  speed: number,
): { phase: TracePhase; speed: number } | undefined {
  const seg = segmentAt(segments, tMs);
  if (!seg) return undefined;
  const rate = playbackRate(tMs, segments, speed);
  return rate < speed ? { phase: seg.phase, speed: rate } : undefined;
}

/**
 * Replay-clock time reached after `wallMs` of playback from the start at a
 * speed: each phase takes max(real length / speed, its minimum on-screen time).
 */
export function playbackTime(
  wallMs: number,
  segments: readonly PhaseSegment[],
  speed: number,
  endMs: number,
): number {
  let left = Math.max(0, wallMs);
  let t = 0;
  for (const seg of segments) {
    const length = seg.endMs - seg.startMs;
    if (length <= 0) continue;
    const wall = Math.max(length / speed, phaseMinWallMs[seg.phase] ?? 0);
    if (left < wall) return seg.startMs + (left / wall) * length;
    left -= wall;
    t = seg.endMs;
  }
  return Math.min(endMs, t + left * speed);
}
