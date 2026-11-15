import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { CaseData } from "../api/types";
import { InsightsPage } from "./InsightsPage";
import { buildInsightsModel, tabCounts } from "./insights-sections";

const source = (id: string) => ({
  id,
  path: `evidence/${id}.txt`,
  kind: "record",
  timestamp: "",
  hash: "",
  excerpt: "",
  metadata: {},
});

const board: CaseData = {
  id: "case-1",
  title: "Test",
  subtitle: "",
  timeRange: { start: "", end: "" },
  nodes: [],
  edges: [],
  audit: [],
  sources: ["EV-1:row=1", "EV-2:row=2", "EV-3:row=3", "EV-4:row=4"].map(source),
  gaps: [
    {
      id: "G-01",
      title: "Who was at the door?",
      description: "",
      score: 0.9,
      affectedClaims: [],
      suggestedEvidence: [],
      citations: ["EV-1:row=1"],
      gapType: "conflicting",
      status: "open",
      missing: "records disagree",
      whyItMatters: "every explanation depends on it",
      direction: "review the camera",
      nodeIds: [],
    },
    {
      id: "G-02",
      title: "Where was the phone?",
      description: "No location record.",
      score: 0.5,
      affectedClaims: [],
      suggestedEvidence: [],
      citations: ["EV-2:row=2"],
    },
  ],
  suggestions: [
    {
      id: "S-01",
      title: "CCTV",
      description: "",
      priority: 1,
      query: "Export door camera footage",
      citations: ["EV-1:row=1"],
      gapId: "G-01",
      gapIds: ["G-01", "G-02"],
      artifact: "cctv_review",
    },
    {
      id: "S-02",
      title: "Carrier records",
      description: "",
      priority: 2,
      query: "Request cell records",
      citations: ["EV-2:row=2"],
      gapId: "G-99",
    },
  ],
  insights: [
    {
      id: "I-01",
      title: "Two places at once",
      text: "Observed: x. Inference: y.",
      score: 0.7,
      citations: ["EV-3:row=3"],
      certainty: "inferred",
      confidence: "medium",
      observations: [
        { text: "Badge used at the door", citations: ["EV-3:row=3"] },
      ],
      inference: "Someone else may have used the badge.",
    },
    {
      id: "I-02",
      title: "Shared badge",
      text: "",
      score: 0.4,
      confidence: "low",
      citations: ["EV-3:row=3"],
      observations: [
        { text: "Badge used at the door", citations: ["EV-4:row=4"] },
      ],
      inference: "The badge may be shared.",
    },
  ],
  contradictions: [
    {
      id: "X-01",
      title: "Statement conflicts with records",
      text: "Said home; badge says office.",
      severity: "high",
      kind: "statement_vs_record",
      possibleReasons: ["clock error", "shared credential"],
      resolvingEvidence: ["cctv_review"],
      citations: ["EV-1:row=1", "EV-2:row=2"],
    },
  ],
  explanations: [
    {
      episode: "Key event",
      verdict: "Insufficient evidence to choose between H-01 and H-02.",
      decided: false,
      hypotheses: [
        {
          id: "H-01",
          statement: "Someone else used the badge.",
          label: "best supported",
          points: 4,
          independentSupport: 2,
          supporting: [
            { reason: "recorded elsewhere", citation: "EV-3:row=3" },
            { reason: "recorded elsewhere", citation: "EV-4:row=4" },
          ],
          contradicting: [],
          assumptions: [],
        },
      ],
      discriminatingEvidence: [],
    },
  ],
  signals: [
    {
      id: "ML-01",
      title: "Recurring evening place",
      text: "A lead to check.",
      type: "place_cluster",
      score: 0.71,
      certainty: "inferred",
      method: { name: "DBSCAN" },
      citations: ["EV-4:row=4"],
    },
  ],
  sourceGroups: [
    {
      id: "SG-01",
      title: "2 records repeat one original",
      text: "Counts as one source.",
      citations: ["EV-1:row=1", "EV-2:row=2"],
    },
  ],
  missingPeriods: [
    {
      id: "M-01",
      title: "Door log is silent",
      text: "May be normal inactivity.",
      kind: "source_silence",
      start: "2026-10-17T22:06:49Z",
      end: "2026-10-18T05:51:02Z",
      citations: ["EV-2:row=2"],
    },
  ],
  uncertainTimes: [],
};

const render = (tab?: "questions" | "evidence" | "inferences") =>
  renderToStaticMarkup(
    <InsightsPage
      data={board}
      tab={tab}
      onInspect={() => {}}
      onOpenSource={() => {}}
      onFocusOnBoard={() => {}}
    />,
  );

describe("insights sections model", () => {
  it("ties suggestions to every gap they address and keeps the rest separate", () => {
    const model = buildInsightsModel(board);
    expect(
      model.questions.items.map((item) => [
        item.gap.id,
        item.suggestions.map((s) => s.id),
      ]),
    ).toEqual([
      ["G-01", ["S-01"]],
      ["G-02", ["S-01"]],
    ]);
    expect(model.questions.unlinked.map((s) => s.id)).toEqual(["S-02"]);
  });

  it("lists each observation once with every insight that rests on it", () => {
    const [observation] = buildInsightsModel(board).evidence.observations;
    expect(observation.insights.map((i) => i.id)).toEqual(["I-01", "I-02"]);
    expect(observation.citations).toEqual(["EV-3:row=3", "EV-4:row=4"]);
  });

  it("filters every section with one search and counts matches per tab", () => {
    expect(tabCounts(buildInsightsModel(board))).toEqual({
      questions: 2,
      evidence: 4,
      inferences: 4,
    });
    const model = buildInsightsModel(board, "review the camera");
    expect(model.questions.items.map((item) => item.gap.id)).toEqual(["G-01"]);
    expect(tabCounts(model).inferences).toBe(0);
    expect(
      buildInsightsModel(board, "cell records").questions.unlinked,
    ).toHaveLength(1);
  });
});

describe("insights page", () => {
  it("defaults to questions with typed gaps, next steps and cited sources", () => {
    const html = render();
    expect(html).toContain('aria-current="page"');
    expect(html).toContain("/cases/case-1/insights/questions");
    expect(html).toContain("Records conflict");
    expect(html).toContain("review the camera");
    expect(html).toContain("CCTV review");
    expect(html).toContain("Also helps G-02");
    expect(html).toContain("Open source EV-1:row=1");
    expect(html).toContain("Locate on mind map");
    expect(html).toContain("not proof");
    expect(html).not.toContain("Statement conflicts with records");
  });

  it("shows observed evidence without the inference wording", () => {
    const html = render("evidence");
    expect(html).toContain("Statement conflicts with records");
    expect(html).toContain("none is a finding");
    expect(html).toContain("Badge used at the door");
    expect(html).toContain("Door log is silent");
    expect(html).toContain("2 records repeat one original");
    expect(html).not.toContain("Someone else may have used the badge.");
  });

  it("labels inferences, never shows confidence as a percentage, and keeps undecided verdicts undecided", () => {
    const html = render("inferences");
    expect(html).toContain("Undecided");
    expect(html).toContain("Best supported, undecided");
    expect(html).toContain("Someone else may have used the badge.");
    expect(html).toContain("Medium confidence");
    expect(html).toContain("Lead · Place cluster");
    expect(html).toContain("ML model");
    expect(html).toContain("DBSCAN");
    expect(html).toContain("Model score 0.71");
    expect(html).toContain("Open source EV-4:row=4");
    expect(html).not.toMatch(/\d+%/);
    expect(html).not.toContain("Statement conflicts with records");
  });
});

/*
 * ML leads in the shape `GET /cases/kestrel-demo` returns after `POST /demo`
 * (trimmed copies of ML-05 and ML-19, the ML-05 board card and agent insight I-11).
 */
const liveSource = (id: string) => source(id);
const ml05 = {
  id: "ML-05",
  title: "Unusual day for Richard Halvorsen: Sat 17 Oct 2026",
  text: "Compared with 95 days of their own location data, this day stands out: 5 records away from home after 21:00 (typical: 0). An unusual day is a lead for where to look, not evidence of wrongdoing.",
  type: "routine_outlier",
  score: 0.65,
  certainty: "inferred" as const,
  method: {
    name: "IsolationForest on daily movement profiles",
    n_estimators: 300,
    contamination: 0.032,
    random_state: 7,
    days: 95,
  },
  citations: ["EV-063:id=PV-00248", "EV-063:id=AS-00242"],
  key: "bb496e57c7518722",
  origin: "ml" as const,
  status: "open",
};
const ml19 = {
  id: "ML-19",
  title:
    "Message triage for halvorsen_iphone.csv: 23 of 172 look automated or spam",
  text: "A text classifier marks 23 of 172 messages as automated or spam; 149 look like human conversation.",
  type: "message_triage",
  score: 0.25,
  certainty: "inferred" as const,
  method: {
    name: "TF-IDF (char 3-5 grams) + logistic regression, weakly labelled",
    C: 2.0,
  },
  citations: ["EV-050:record_id=HMSG-00037"],
  key: "2cd98692dbd3f1c4",
  origin: "ml" as const,
  status: "open",
};
const live: CaseData = {
  ...board,
  id: "kestrel-demo",
  gaps: [],
  suggestions: [],
  contradictions: [],
  explanations: [],
  sourceGroups: [],
  missingPeriods: [],
  uncertainTimes: [],
  sources: [...ml05.citations, ...ml19.citations, "EV-071:seq=40162"].map(
    liveSource,
  ),
  nodes: [
    {
      id: "sig-bb496e57c7518722",
      type: "event",
      label: ml05.title,
      citations: ml05.citations,
      position: { x: 80, y: 580 },
      summary: ml05.text,
      subtitle: "ML signal",
      certainty: "inferred",
      origin: "ml",
      stage: "ml_signals",
      itemId: "ML-05",
      key: ml05.key,
      evidenceIds: ["EV-063"],
    },
  ],
  insights: [
    {
      id: "I-11",
      title: "Camera outage was requested in advance",
      text: "",
      score: 0.6,
      citations: ["EV-071:seq=40162"],
      certainty: "inferred",
      confidence: "medium",
      origin: "agent",
      observations: [
        {
          text: "A ticket asked for the outage.",
          citations: ["EV-071:seq=40162"],
        },
      ],
      inference: "The outage was planned rather than a fault.",
    },
    ...board.insights.map((insight) => ({
      ...insight,
      origin: "rules" as const,
    })),
  ],
  // The API lists signals by ID; the page ranks them by model score.
  signals: [ml19, ml05],
};

const renderLive = (onFocusOnBoard?: () => void) =>
  renderToStaticMarkup(
    <InsightsPage
      data={live}
      tab="inferences"
      onInspect={() => {}}
      onOpenSource={() => {}}
      onFocusOnBoard={onFocusOnBoard}
    />,
  );

describe("ML leads from the live backend", () => {
  it("groups every signal as an ML lead, best model score first, apart from agent and rule insights", () => {
    const { signals, agentInsights, ruleInsights } =
      buildInsightsModel(live).inferences;
    expect(signals.map((s) => s.id)).toEqual(["ML-05", "ML-19"]);
    expect(agentInsights.map((i) => i.id)).toEqual(["I-11"]);
    expect(ruleInsights.map((i) => i.id)).toEqual(["I-01", "I-02"]);
    expect(tabCounts(buildInsightsModel(live)).inferences).toBe(5);
    expect(
      buildInsightsModel(live, "isolationforest").inferences.signals,
    ).toHaveLength(1);
    expect(
      buildInsightsModel(live, "routine outlier").inferences.signals,
    ).toHaveLength(1);
  });

  it("lists ML leads in the jump rail and labels them with the model, method and score", () => {
    const html = renderLive(() => {});
    expect(html).toContain('href="#inferences-signals"');
    expect(html).toContain("ML model leads");
    expect(html).toContain(
      "Unusual day for Richard Halvorsen: Sat 17 Oct 2026",
    );
    expect(html).toContain("IsolationForest on daily movement profiles");
    expect(html).toContain("Model score 0.65");
    expect(html).toContain("Model score 0.25");
    expect(html).toContain("Open source EV-063:id=PV-00248");
    expect(html).not.toMatch(/\d+%/);
    // Agent insights come before ML leads, and ML leads before the rules.
    const agent = html.indexOf('id="inferences-agent"');
    const ml = html.indexOf('id="inferences-signals"');
    const rules = html.indexOf('id="inferences-rules"');
    expect(agent).toBeGreaterThan(-1);
    expect(agent).toBeLessThan(ml);
    expect(ml).toBeLessThan(rules);
    expect(html).toContain("AI agent");
  });

  it("reaches a lead's board card through its itemId", () => {
    const html = renderLive(() => {});
    const ml05Card = html.slice(
      html.indexOf("ML-05"),
      html.indexOf("ML-19") > html.indexOf("ML-05")
        ? html.indexOf("ML-19")
        : undefined,
    );
    expect(ml05Card).toContain("Inspect lead");
    expect(ml05Card).toContain("Locate on mind map");
    // ML-19 has no board card, so it offers its sources only.
    const ml19Card = html.slice(html.indexOf("ML-19"));
    expect(ml19Card).not.toContain("Inspect lead");
  });

  it("explains an empty tab instead of showing a blank panel", () => {
    const html = renderToStaticMarkup(
      <InsightsPage
        data={live}
        tab="questions"
        onInspect={() => {}}
        onOpenSource={() => {}}
      />,
    );
    expect(html).toContain("No questions for this case yet.");
  });
});
