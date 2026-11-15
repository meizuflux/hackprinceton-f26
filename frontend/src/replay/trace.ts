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

/** Number of entries in a sorted list at or before `at` (events shown by a wall position). */
export function countShownBy(times: readonly number[], at: number): number {
  let lo = 0;
  let hi = times.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (times[mid] <= at) lo = mid + 1;
    else hi = mid;
  }
  return lo;
}

export interface FeedRow {
  event: TraceEvent;
  /** Consecutive calls of the same agent tool folded into this row. */
  count: number;
}

/** Feed rows, newest first, folding runs of the same agent tool into one counted row. */
export function feedRows(
  events: readonly TraceEvent[],
  limit: number,
): FeedRow[] {
  const rows: FeedRow[] = [];
  for (let i = events.length - 1; i >= 0 && rows.length < limit; i--) {
    const e = events[i];
    const last = rows.at(-1);
    if (
      last &&
      e.type === "agent_tool" &&
      last.event.type === "agent_tool" &&
      last.event.tool === e.tool
    )
      last.count++;
    else rows.push({ event: e, count: 1 });
  }
  return rows;
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
      return `${e.purpose === "media_vision" ? "vision → image description" : `${e.phase} → ${str(e.purpose)} call`} · ${formatTokens(num(e.inputTokens) + num(e.outputTokens))} tokens · ${formatCost(num(e.costUsd))}`;
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

/*
 * Pacing. A schedule gives every event the wall time (ms after playback
 * starts) at which it shows; the replay clock between two events is
 * interpolated from their real `tMs`, so the clock on screen is always the
 * recorded one. Wall time is the real gap divided by the speed, except:
 *
 * - short phases get a minimum on-screen time (slowed, never skipped);
 * - above 1x, a wait for the model in the LLM, agent and output phases is
 *   shown for at most `modelWaitCapMs` (compressed, and the HUD says so);
 * - events recorded at one instant (the agent's batched tool calls) are
 *   spread a short step apart so they can be seen arriving.
 *
 * Only presentation: no event is dropped, reordered or retimed in the feed.
 */

/** Minimum on-screen time per run of one phase, so short phases stay watchable. */
export const phaseMinWallMs: Partial<Record<TracePhase, number>> = {
  ingest: 3000,
  rules: 1200,
  ml: 2000,
};
/** Above 1x a wait for the model is shown for less than this; long waits approach it. */
export const modelWaitCapMs = 650;
const compressedPhases = new Set<TracePhase>(["llm", "agent", "output"]);
/** Events this close together on the replay clock (chained) are one instant. */
const BURST_WINDOW_MS = 10;
/** Wall step between events of one instant at the default speed, and the most one instant may take. */
const BURST_STEP_MS = 60;
const BURST_MAX_MS = 800;
/** Recorded insights land at least this far apart, so the counters can be seen to count. */
const INSIGHT_STEP_MS = 420;

export type Pace =
  /** A short phase shown slower than the chosen speed. */
  | { kind: "slowed"; phase: TracePhase; speed: number; realMs: number }
  /** A model wait shown faster than the chosen speed: `realMs` of waiting in `wallMs`. */
  | { kind: "compressed"; phase: TracePhase; realMs: number; wallMs: number };

export interface Schedule {
  /** Wall time at which each event shows (non-decreasing). */
  wall: number[];
  /** Each event's replay-clock time. */
  clock: number[];
  /** How the stretch up to each event is paced, when not at the chosen speed. */
  pace: Array<Pace | undefined>;
  /** The clock at the end, and the wall time it is reached. */
  endMs: number;
  totalMs: number;
  /** Pace of the stretch after the last event. */
  tailPace?: Pace;
}

/** Build the wall-time schedule for a trace at a speed. `endMs` is the end of the clock. */
export function buildSchedule(
  events: readonly TraceEvent[],
  endMs: number,
  speed: number,
): Schedule {
  const n = events.length;
  const deltas = new Array<number>(n).fill(0);
  const pace = new Array<Pace | undefined>(n).fill(undefined);
  // Steps within an instant shrink at faster speeds, never grow at slower ones.
  const fast = Math.min(1, defaultSpeed / Math.max(speed, 1e-9));
  const compress = speed > 1;
  const gapWall = (realMs: number, phase: TracePhase): [number, Pace?] => {
    const wall = realMs / speed;
    if (!compress || !compressedPhases.has(phase)) return [wall];
    // Eases toward the cap: short waits keep their length, long ones approach it.
    const shown = modelWaitCapMs * (1 - Math.exp(-wall / modelWaitCapMs));
    return shown < wall * 0.85
      ? [shown, { kind: "compressed", phase, realMs, wallMs: shown }]
      : [wall];
  };

  // Gaps between instants, and steps within an instant.
  let i = 0;
  while (i < n) {
    let j = i + 1;
    while (j < n && events[j].tMs - events[j - 1].tMs <= BURST_WINDOW_MS) j++;
    const before = i ? events[i - 1].tMs : 0;
    [deltas[i], pace[i]] = gapWall(
      Math.max(0, events[i].tMs - before),
      events[i].phase,
    );
    const step = Math.min(BURST_STEP_MS, BURST_MAX_MS / Math.max(1, j - i - 1));
    for (let k = i + 1; k < j; k++)
      deltas[k] =
        (events[k].type === "insight_recorded" ? INSIGHT_STEP_MS : step) * fast;
    i = j;
  }

  // Runs of a phase with a minimum on-screen time are stretched to it.
  let s = 0;
  while (s < n) {
    let e = s;
    while (e + 1 < n && events[e + 1].phase === events[s].phase) e++;
    const phase = events[s].phase;
    const min = (phaseMinWallMs[phase] ?? 0) * fast;
    const realMs = events[e].tMs - (s ? events[s - 1].tMs : 0);
    if (min && realMs / speed < min) {
      // The run takes exactly its minimum, its gaps and instants scaled to fit.
      let sum = 0;
      for (let k = s; k <= e; k++) sum += deltas[k];
      for (let k = s; k <= e; k++) {
        deltas[k] = sum > 0 ? (deltas[k] * min) / sum : min / (e - s + 1);
        pace[k] = { kind: "slowed", phase, speed: realMs / min, realMs };
      }
    }
    s = e + 1;
  }

  const wall: number[] = [];
  let at = 0;
  for (const d of deltas) wall.push((at += d));
  const lastMs = events.at(-1)?.tMs ?? 0;
  const [tailWall, tailPace] = n
    ? gapWall(Math.max(0, endMs - lastMs), events[n - 1].phase)
    : [0];
  return {
    wall,
    clock: events.map((e) => e.tMs),
    pace,
    endMs: Math.max(endMs, lastMs),
    totalMs: at + tailWall,
    tailPace,
  };
}

/** The replay clock (real `tMs`) at a wall position. */
export function clockAtWall(s: Schedule, wallMs: number): number {
  if (wallMs <= 0) return 0;
  if (wallMs >= s.totalMs) return s.endMs;
  const i = countShownBy(s.wall, wallMs);
  const fromWall = i ? s.wall[i - 1] : 0;
  const fromClock = i ? s.clock[i - 1] : 0;
  const toWall = i < s.wall.length ? s.wall[i] : s.totalMs;
  const toClock = i < s.clock.length ? s.clock[i] : s.endMs;
  if (toWall <= fromWall) return fromClock;
  return (
    fromClock +
    ((wallMs - fromWall) / (toWall - fromWall)) * (toClock - fromClock)
  );
}

/** How the stretch being played at a wall position is paced; undefined at the chosen speed. */
export function paceAtWall(s: Schedule, wallMs: number): Pace | undefined {
  if (wallMs >= s.totalMs) return undefined;
  const i = countShownBy(s.wall, wallMs);
  return i < s.pace.length ? s.pace[i] : s.tailPace;
}

/** A playback speed for display: "23×", "1.5×", "0.12×". */
export function formatSpeed(speed: number): string {
  if (speed >= 10) return `${Math.round(speed)}×`;
  if (speed >= 1) return `${Number(speed.toFixed(1))}×`;
  return `${Number(speed.toPrecision(2))}×`;
}
