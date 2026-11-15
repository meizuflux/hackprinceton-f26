import { describe, expect, it } from "vitest";
import type { CaseData, TraceEvent } from "../api/types";
import { emptyCase, itemRevealed, revealCase } from "./reveal";
import {
  advanceClock,
  countUpTo,
  countShownBy,
  displayTimes,
  feedRows,
  describeEvent,
  formatCost,
  formatDuration,
  mergeEvents,
  phaseSegments,
  playbackRate,
  playbackTime,
  slowedPhase,
  runEndMs,
  summarize,
} from "./trace";

let seq = 0;
const ev = (
  tMs: number,
  type: TraceEvent["type"],
  phase: TraceEvent["phase"],
  extra: Record<string, unknown> = {},
): TraceEvent => ({ seq: ++seq, tMs, type, phase, ...extra });

const events: TraceEvent[] = [
  ev(0, "run_started", "ingest", { model: "m" }),
  ev(100, "file_parsed", "ingest", {
    evidenceId: "EV-001",
    filename: "a.csv",
    records: 10,
    recordTypes: { call: 10 },
  }),
  ev(200, "phase_finished", "ingest", { durationMs: 200 }),
  ev(300, "stage_finished", "rules", { stage: "gaps" }),
  ev(400, "llm_call", "agent", {
    inputTokens: 1000,
    outputTokens: 500,
    cacheReadTokens: 100,
    costUsd: 0.25,
    purpose: "investigator",
  }),
  ev(450, "insight_recorded", "agent", { id: "I-1", key: "k1", title: "t" }),
  ev(500, "run_finished", "output", { status: "ready", durationMs: 500 }),
];

const data = {
  id: "c",
  title: "t",
  nodes: [
    { id: "n1", origin: "record", evidenceIds: ["EV-001"] },
    { id: "n2", origin: "record", evidenceIds: ["EV-002"] },
    { id: "n3", origin: "agent", key: "k1", stage: "agent_insights" },
    { id: "plain" },
  ],
  edges: [
    { id: "e1", source: "n1", target: "plain" },
    {
      id: "e2",
      source: "n1",
      target: "n2",
      origin: "record",
      evidenceIds: ["EV-001"],
    },
  ],
  gaps: [{ id: "g1" }],
  insights: [
    { id: "i1", key: "k1", origin: "agent" },
    { id: "i2", key: "k2", origin: "agent" },
  ],
  suggestions: [],
  signals: [],
} as unknown as CaseData;

describe("clock pacing", () => {
  it("scales wall time by speed and caps at the end", () => {
    expect(advanceClock(0, 100, 10, 5000)).toBe(1000);
    expect(advanceClock(4900, 100, 10, 5000)).toBe(5000);
    expect(advanceClock(100, -5, 10, 5000)).toBe(100);
  });
  it("counts events reached", () => {
    expect(countUpTo(events, -1)).toBe(0);
    expect(countUpTo(events, 100)).toBe(2);
    expect(countUpTo(events, 9999)).toBe(events.length);
  });
  it("merges polled pages without repeats", () => {
    const merged = mergeEvents(events.slice(0, 3), events.slice(1, 5));
    expect(merged.map((e) => e.seq)).toEqual(
      events.slice(0, 5).map((e) => e.seq),
    );
  });
  it("finds the end", () => expect(runEndMs(events)).toBe(500));
  it("formats", () => {
    expect(formatDuration(292_000)).toBe("4:52");
    expect(formatCost(1.3)).toBe("$1.30");
    expect(formatCost(0.0123)).toBe("$0.012");
  });
});

describe("summarize", () => {
  it("accumulates counters up to the clock", () => {
    const p = summarize(events.slice(0, countUpTo(events, 450)));
    expect(p.records).toBe(10);
    expect(p.recordTypes).toEqual({ call: 10 });
    expect(p.inputTokens).toBe(1100);
    expect(p.costUsd).toBeCloseTo(0.25);
    expect(p.phases.ingest.status).toBe("done");
    expect(p.phases.agent.status).toBe("running");
    expect(p.finished).toBe(false);
    expect(summarize(events).finished).toBe(true);
  });
  it("describes tool calls", () => {
    expect(
      describeEvent(
        ev(1, "agent_tool", "agent", {
          tool: "search_records",
          args: { query: "badge" },
        }),
      ),
    ).toBe("agent → search_records {query: 'badge'}");
  });
});

describe("reveal", () => {
  it("shows record nodes once their file is parsed", () => {
    const p = summarize(events.slice(0, 2));
    const shown = revealCase(data, p);
    expect(shown.nodes.map((n) => n.id)).toEqual(["n1", "plain"]);
    // e2 needs both endpoints.
    expect(shown.edges.map((e) => e.id)).toEqual(["e1"]);
    expect(shown.gaps).toHaveLength(0);
  });
  it("reveals gaps with their stage and agent items at their recorded key", () => {
    const p = summarize(events.slice(0, 6));
    const shown = revealCase(data, p);
    expect(shown.gaps).toHaveLength(1);
    expect(shown.nodes.map((n) => n.id)).toContain("n3");
    expect(shown.insights.map((i) => i.id)).toEqual(["i1"]);
  });
  it("shows everything when the run finished or provenance is missing", () => {
    expect(revealCase(data, summarize(events))).toBe(data);
    expect(itemRevealed({}, summarize([]))).toBe(true);
  });
  it("builds an empty placeholder case", () => {
    expect(emptyCase("x", "X").nodes).toEqual([]);
  });
});

describe("per-phase pacing", () => {
  const pe = [
    ev(0, "run_started", "ingest"),
    ev(1500, "file_parsed", "ingest"),
    ev(1800, "stage_finished", "rules"),
    ev(1900, "ml_signal", "ml"),
    ev(2000, "llm_call", "llm"),
    ev(102_000, "run_finished", "output"),
  ];
  const segs = phaseSegments(pe, 102_000);
  it("segments the clock at each phase start", () => {
    expect(segs.map((s) => [s.phase, s.startMs, s.endMs])).toEqual([
      ["ingest", 0, 1800],
      ["rules", 1800, 1900],
      ["ml", 1900, 2000],
      ["llm", 2000, 102_000],
      ["output", 102_000, 102_000],
    ]);
  });
  it("slows short phases but keeps the chosen speed for long ones", () => {
    expect(playbackRate(100, segs, 10)).toBeCloseTo(1800 / 4000);
    expect(playbackRate(1850, segs, 10)).toBeCloseTo(100 / 2000);
    expect(playbackRate(50_000, segs, 10)).toBe(10);
    expect(slowedPhase(50_000, segs, 10)).toBeUndefined();
    expect(slowedPhase(100, segs, 10)?.phase).toBe("ingest");
  });
  it("maps wall time to replay time", () => {
    expect(playbackTime(2000, segs, 10, 102_000)).toBeCloseTo(900);
    expect(playbackTime(4000, segs, 10, 102_000)).toBeCloseTo(1800);
    expect(playbackTime(4000 + 2000 + 2500, segs, 10, 102_000)).toBeCloseTo(
      2000,
    );
    expect(playbackTime(8500 + 1000, segs, 10, 102_000)).toBeCloseTo(12_000);
    expect(playbackTime(1e9, segs, 10, 102_000)).toBe(102_000);
  });
});

describe("display pacing", () => {
  const ev = (seq: number, tMs: number, extra: Partial<TraceEvent> = {}) =>
    ({ seq, tMs, phase: "agent", type: "agent_tool", ...extra }) as TraceEvent;

  it("spreads a burst across the gap before the next event, in order", () => {
    const burst = [1, 2, 3, 4].map((s) => ev(s, 1000));
    const times = displayTimes([...burst, ev(5, 11000)]);
    expect(times[0]).toBe(1000);
    expect(times[3]).toBeLessThanOrEqual(1000 + 10000 * 0.8);
    expect([...times].sort((a, b) => a - b)).toEqual(times);
    expect(times[4]).toBe(11000);
    expect(countShownBy(times, 1000)).toBe(1);
  });

  it("keeps a lone event and a final burst at their own times", () => {
    expect(displayTimes([ev(1, 10), ev(2, 500), ev(3, 500)])).toEqual([
      10, 500, 500,
    ]);
  });

  it("folds consecutive calls of one tool into a counted row", () => {
    const rows = feedRows(
      [
        ev(1, 0, { tool: "search_records" }),
        ev(2, 1, { tool: "get_record" }),
        ev(3, 2, { tool: "get_record" }),
      ],
      10,
    );
    expect(rows.map((r) => [r.event.seq, r.count])).toEqual([
      [3, 2],
      [1, 1],
    ]);
  });
});
