import { describe, expect, it } from "vitest";
import type { CaseData, TraceEvent } from "../api/types";
import { emptyCase, itemRevealed, revealCase } from "./reveal";
import { countFrame } from "./CountUp";
import {
  buildSchedule,
  clockAtWall,
  countShownBy,
  feedRows,
  describeEvent,
  formatCost,
  formatDuration,
  formatSpeed,
  mergeEvents,
  modelWaitCapMs,
  paceAtWall,
  phaseMinWallMs,
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

describe("trace helpers", () => {
  it("counts entries reached", () => {
    const times = events.map((e) => e.tMs);
    expect(countShownBy(times, -1)).toBe(0);
    expect(countShownBy(times, 100)).toBe(2);
    expect(countShownBy(times, 9999)).toBe(events.length);
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
    expect(formatSpeed(23.4)).toBe("23×");
    expect(formatSpeed(1.25)).toBe("1.3×");
    expect(formatSpeed(0.117)).toBe("0.12×");
  });
});

describe("summarize", () => {
  it("accumulates counters up to the clock", () => {
    const p = summarize(
      events.slice(
        0,
        countShownBy(
          events.map((e) => e.tMs),
          450,
        ),
      ),
    );
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

describe("pacing schedule", () => {
  let n = 0;
  const at = (
    tMs: number,
    phase: TraceEvent["phase"],
    type: TraceEvent["type"] = "agent_tool",
  ) => ({ seq: ++n, tMs, phase, type }) as TraceEvent;
  const trace = [
    at(0, "ingest", "run_started"),
    at(300, "ingest", "file_parsed"),
    at(400, "rules", "stage_finished"),
    at(60_400, "llm", "llm_call"), // a one-minute model wait
    at(61_400, "agent", "llm_call"), // a one-second wait
    at(61_400, "agent", "insight_recorded"),
    at(61_401, "agent", "insight_recorded"),
    at(61_402, "agent", "agent_tool"),
    at(70_000, "output", "run_finished"),
  ];
  const end = 70_000;
  const s10 = buildSchedule(trace, end, 10);

  it("gives short phases their minimum on-screen time, stated as slowed", () => {
    expect(s10.wall[1]).toBeCloseTo(phaseMinWallMs.ingest!);
    expect(s10.wall[2] - s10.wall[1]).toBeCloseTo(phaseMinWallMs.rules!);
    expect(paceAtWall(s10, 100)).toMatchObject({
      kind: "slowed",
      phase: "ingest",
    });
    expect((paceAtWall(s10, 100) as { speed: number }).speed).toBeCloseTo(
      300 / phaseMinWallMs.ingest!,
    );
  });

  it("shortens long model waits below the cap and says so", () => {
    const wait = s10.wall[3] - s10.wall[2];
    expect(wait).toBeLessThan(modelWaitCapMs);
    expect(wait).toBeGreaterThan(modelWaitCapMs * 0.9);
    expect(paceAtWall(s10, s10.wall[2] + 1)).toMatchObject({
      kind: "compressed",
      phase: "llm",
      realMs: 60_000,
    });
    // A short wait keeps its length at the chosen speed.
    expect(s10.wall[4] - s10.wall[3]).toBeCloseTo(100);
    expect(paceAtWall(s10, s10.wall[3] + 1)).toBeUndefined();
  });

  it("plays recorded waits in full at 1x", () => {
    const s1 = buildSchedule(trace, end, 1);
    expect(s1.wall[3] - s1.wall[2]).toBeCloseTo(60_000);
    expect(s1.pace[3]).toBeUndefined();
  });

  it("spreads an instant so insights land one at a time", () => {
    expect(s10.wall[5] - s10.wall[4]).toBeGreaterThanOrEqual(400);
    expect(s10.wall[6] - s10.wall[5]).toBeGreaterThanOrEqual(400);
    expect(countShownBy(s10.wall, s10.wall[5])).toBe(6);
    expect([...s10.wall].sort((a, b) => a - b)).toEqual(s10.wall);
  });

  it("shows the real clock at every wall position", () => {
    expect(clockAtWall(s10, 0)).toBe(0);
    expect(clockAtWall(s10, s10.wall[3])).toBe(60_400);
    const mid = (s10.wall[2] + s10.wall[3]) / 2;
    expect(clockAtWall(s10, mid)).toBeCloseTo(30_400);
    expect(clockAtWall(s10, s10.totalMs + 1)).toBe(end);
    expect(clockAtWall(s10, Infinity)).toBe(end);
  });

  it("ends in a fraction of the real run at the default speed", () => {
    expect(s10.totalMs).toBeLessThan(9000);
    expect(buildSchedule(trace, end, 50).totalMs).toBeLessThan(s10.totalMs);
  });

  it("handles an empty trace", () => {
    const empty = buildSchedule([], 0, 10);
    expect(empty.totalMs).toBe(0);
    expect(clockAtWall(empty, 100)).toBe(0);
  });
});

describe("count up", () => {
  it("eases from the old value to the new one and lands on it", () => {
    expect(countFrame(10, 14, 0, 600)).toBe(10);
    const mid = countFrame(10, 14, 300, 600);
    expect(mid).toBeGreaterThan(10);
    expect(mid).toBeLessThanOrEqual(14);
    expect(countFrame(10, 14, 600, 600)).toBe(14);
    expect(countFrame(0, 10, 9999, 600)).toBe(10);
  });
});

describe("feed", () => {
  const ev = (seq: number, tMs: number, extra: Partial<TraceEvent> = {}) =>
    ({ seq, tMs, phase: "agent", type: "agent_tool", ...extra }) as TraceEvent;

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
