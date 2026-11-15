import { describe, expect, it } from "vitest";
import type { ChatStep } from "../api/chat";
import {
  planPlayback,
  playbackAt,
  revealSegments,
  stepLabel,
  summarizeSteps,
} from "./chat-playback";

const model = (durationMs: number): ChatStep => ({
  type: "model_call",
  inputTokens: 1200,
  outputTokens: 300,
  costUsd: 0.004,
  durationMs,
  durationSource: "estimated",
});
const tool: ChatStep = {
  type: "tool_call",
  tool: "search_records",
  args: { query: "badge", start: "" },
  resultChars: 10,
};

describe("planPlayback", () => {
  it("compresses a typical answer into 2.5 to 6 seconds", () => {
    const plan = planPlayback([model(4000), tool, tool, model(5000)], 60);
    expect(plan.stepsMs).toBeGreaterThanOrEqual(2500);
    expect(plan.stepsMs).toBeLessThanOrEqual(6000);
    expect(plan.starts).toHaveLength(4);
    expect(plan.starts[0]).toBe(0);
  });
  it("caps long runs and keeps every step visible", () => {
    const steps = Array.from({ length: 30 }, () => model(20000));
    const plan = planPlayback(steps, 500);
    expect(plan.stepsMs).toBeLessThanOrEqual(6000 + 30 * 220);
    expect(plan.typeMs).toBeLessThanOrEqual(2000);
  });
  it("types at once when there are no steps", () => {
    const plan = planPlayback([], 40);
    expect(plan.stepsMs).toBe(0);
    expect(playbackAt(plan, 0).phase).toBe("typing");
    expect(playbackAt(plan, plan.typeMs).phase).toBe("done");
  });
});

describe("playbackAt", () => {
  it("reveals steps, then types, then finishes", () => {
    const plan = planPlayback([model(4000), tool], 20);
    expect(playbackAt(plan, 0)).toMatchObject({
      phase: "steps",
      stepsShown: 1,
    });
    expect(playbackAt(plan, plan.stepsMs + 10).phase).toBe("typing");
    expect(playbackAt(plan, plan.stepsMs + plan.typeMs).phase).toBe("done");
  });
});

describe("text helpers", () => {
  it("shares a word budget across segments", () => {
    expect(revealSegments(["one two three", "four five"], 4)).toEqual([
      "one two three",
      "four",
    ]);
    expect(revealSegments(["a b"], 0)).toEqual([""]);
  });
  it("labels steps and summarizes the run", () => {
    expect(stepLabel(tool)).toEqual({
      title: "Searching records",
      detail: "query: badge",
    });
    expect(stepLabel(model(1)).detail).toBe("1.2k in / 300 out · $0.004");
    expect(summarizeSteps([model(1), tool, model(1)], true)).toBe(
      "Used 1 tool · 2 model calls · $0.008 · replayed",
    );
  });
});
