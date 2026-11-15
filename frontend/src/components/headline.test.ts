import { describe, expect, it } from "vitest";
import { demoCase } from "../api/fixtures";
import type { CaseData, SourceRecord } from "../api/types";
import {
  plainCounts,
  resolveHeadline,
  sourceRow,
  splitStatement,
  supportingSources,
} from "./headline";

const source = (
  id: string,
  evidenceId: string,
  reliability = "recorded",
  extra: Partial<SourceRecord> = {},
): SourceRecord => ({
  id,
  path: `case/evidence/${evidenceId.toLowerCase()}.csv`,
  kind: "event",
  timestamp: "2026-10-18T04:36:31Z",
  hash: "",
  excerpt: `excerpt ${id}`,
  metadata: {
    evidence_id: evidenceId,
    locator: id.split(":")[1] ?? "",
    reliability,
  },
  ...extra,
});

const contradictionCase = (): CaseData => ({
  ...demoCase,
  timezone: "America/Los_Angeles",
  sources: [
    source("EV-090:line=14", "EV-090", "asserted", {
      path: "case/evidence/08_intv/halvorsen_1.txt",
      kind: "interview_turn",
      timestamp: "",
      excerpt: "At home. A quiet night.",
    }),
    source("EV-063:id=PV-1", "EV-063"),
    source("EV-063:id=PV-2", "EV-063"),
    source("EV-070:id=B-1", "EV-070"),
  ],
  contradictions: [
    {
      id: "X-01",
      title: "An account conflicts with records",
      text: 'A Person said: "At home. A quiet night.". 33 record(s) in the same window disagree. 1 record(s) agree.',
      severity: "high",
      kind: "statement_vs_record",
      possibleReasons: ["Someone else may have used the credential."],
      resolvingEvidence: ["cctv_review"],
      citations: [
        "EV-090:line=14",
        "EV-063:id=PV-1",
        "EV-063:id=PV-2",
        "EV-070:id=B-1",
      ],
    },
  ],
  story: {
    centerId: "n1",
    nodeIds: ["n1"],
    headline: { kind: "contradiction", id: "X-01" },
    reason: "",
  },
});

describe("resolveHeadline", () => {
  it("returns null without a story, so the mock board opens as before", () => {
    expect(resolveHeadline(demoCase)).toBeNull();
    expect(resolveHeadline({ ...demoCase, story: null })).toBeNull();
  });

  it("returns null when the headline item is missing", () => {
    const data = contradictionCase();
    expect(resolveHeadline({ ...data, contradictions: [] })).toBeNull();
  });

  it("presents a contradiction with its statement apart from the records", () => {
    const headline = resolveHeadline(contradictionCase())!;
    expect(headline.status).toBe("Possible contradiction");
    expect(headline.statement).toEqual({
      speaker: "A Person",
      quote: "At home. A quiet night.",
    });
    expect(headline.summary).toBe(
      "33 records in the same window disagree. 1 record agree.",
    );
    expect(headline.context.label).toBe("Possible reasons");
    expect(headline.note).toMatch(/not proof/);
  });

  it("labels gap and insight headlines neutrally", () => {
    const gap = demoCase.gaps[0];
    const insight = demoCase.insights[0];
    const story = (kind: "gap" | "insight", id: string) => ({
      centerId: "",
      nodeIds: [],
      headline: { kind, id },
      reason: "",
    });
    expect(
      resolveHeadline({ ...demoCase, story: story("gap", gap.id) })?.status,
    ).toBe("Open question");
    expect(
      resolveHeadline({ ...demoCase, story: story("insight", insight.id) })
        ?.status,
    ).toBe("Insight");
  });
});

describe("splitStatement", () => {
  it("keeps text without a quoted statement whole", () => {
    expect(splitStatement("Two records disagree.")).toEqual({
      rest: "Two records disagree.",
    });
  });
});

describe("plainCounts", () => {
  it("rewrites (s) plurals only", () => {
    expect(plainCounts("2 file(s), 1 call(s), item(s)")).toBe(
      "2 files, 1 call, item(s)",
    );
  });
});

describe("supportingSources", () => {
  it("leads with asserted statements, then spreads records across files", () => {
    const data = contradictionCase();
    const ids = supportingSources(data, data.contradictions![0].citations).map(
      (s) => s.id,
    );
    expect(ids).toEqual([
      "EV-090:line=14",
      "EV-063:id=PV-1",
      "EV-070:id=B-1",
      "EV-063:id=PV-2",
    ]);
    expect(
      supportingSources(data, data.contradictions![0].citations, 3),
    ).toHaveLength(3);
  });

  it("skips unknown and repeated citations", () => {
    const data = contradictionCase();
    expect(
      supportingSources(data, ["missing", "EV-070:id=B-1", "EV-070:id=B-1"]),
    ).toHaveLength(1);
  });
});

describe("sourceRow", () => {
  it("names the record type and file with the time in the case zone", () => {
    const data = contradictionCase();
    const row = sourceRow(data.sources[3], data.timezone);
    expect(row).toMatchObject({
      title: "Logged event",
      file: "ev-070.csv",
      format: "csv",
      locator: "id=B-1",
      time: "Sat 17 Oct, 21:36",
      asserted: false,
    });
  });

  it("marks asserted statements and tolerates a missing time", () => {
    const data = contradictionCase();
    const row = sourceRow(data.sources[0], data.timezone);
    expect(row.title).toBe("Interview statement");
    expect(row.asserted).toBe(true);
    expect(row.time).toBe("");
  });
});
