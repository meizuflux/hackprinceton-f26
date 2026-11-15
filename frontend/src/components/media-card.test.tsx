import { renderToStaticMarkup } from "react-dom/server";
import { ReactFlowProvider } from "@xyflow/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../api/client", () => ({
  isMock: false,
  api: {
    mode: "live",
    evidenceFileUrl: (c: string, e: string) => `/api/${c}/${e}?inline=1`,
  },
}));
import type { EvidenceNode, MediaInfo, TraceEvent } from "../api/types";
import { getPinDimensions } from "./board-layout";
import { EvidenceNode as Card, type PinData } from "./EvidenceNode";
import {
  formatDuration,
  mediaAlt,
  mediaDevice,
  posterTime,
  videoSrc,
} from "./media-card";
import { MediaInspector, mediaNodeFor } from "./MediaInspector";
import { summarize, emptyProgress } from "../replay/trace";
import { itemRevealed, revealCase, withheldVision } from "../replay/reveal";

const vision = {
  text: "A sedan in a garage.",
  observations: [{ text: "Partial plate", frameS: 12 }],
  origin: "llm" as const,
  certainty: "inferred" as const,
};
const video: MediaInfo = {
  evidenceId: "EV-022",
  kind: "video",
  durationS: 61,
  vision,
};
const node = (media?: MediaInfo): EvidenceNode =>
  ({
    id: "n1",
    type: "event",
    label: "CCTV clip",
    citations: ["EV-022:row=1"],
    origin: "record",
    evidenceIds: ["EV-022"],
    media,
  }) as unknown as EvidenceNode;

describe("media card helpers", () => {
  it("picks a poster time halfway through", () => {
    expect(posterTime(60)).toBe(30);
    expect(posterTime(null)).toBe(0.1);
    expect(videoSrc("/f?inline=1", 20)).toBe("/f?inline=1#t=10");
  });
  it("builds alt text and metadata", () => {
    expect(mediaAlt("Photo · a.jpg", "photo")).toBe("Photo: Photo · a.jpg");
    expect(mediaAlt("Garage", "video")).toBe("CCTV: Garage");
    expect(formatDuration(61)).toBe("1:01");
    expect(
      mediaDevice({ ...video, deviceMake: "Acme", deviceModel: "X1" }),
    ).toBe("Acme X1");
  });
  it("sizes media cards by kind and leaves others alone", () => {
    expect(
      getPinDimensions({ type: "event", media: { kind: "photo" } }).height,
    ).toBeGreaterThan(getPinDimensions({ type: "event" }).height);
    expect(getPinDimensions({ type: "event" })).toEqual({
      width: 252,
      height: 228,
    });
  });
});

const data = (n: EvidenceNode): PinData =>
  ({
    label: n.label,
    type: n.type,
    summary: "summary text",
    subtitle: "sub",
    citations: n.citations,
    media: n.media,
    caseId: "c1",
    onInspect: () => {},
  }) as PinData;
const props = (d: PinData) =>
  ({ id: "n1", data: d }) as unknown as Parameters<typeof Card>[0];
const card = (d: PinData) =>
  renderToStaticMarkup(
    <ReactFlowProvider>
      <Card {...props(d)} />
    </ReactFlowProvider>,
  );

describe("media card rendering", () => {
  it("renders a non-draggable photo with alt text", () => {
    const html = card(data(node({ evidenceId: "EV-1", kind: "photo" })));
    expect(html).toContain("<img");
    expect(html).toContain('draggable="false"');
    expect(html).toContain('loading="lazy"');
    expect(html).toContain("Photo: CCTV clip");
  });
  it("renders a muted metadata-only video with a duration badge", () => {
    const html = card(data(node(video)));
    expect(html).toContain("<video");
    expect(html).not.toContain("autoplay");
    expect(html).toContain("1:01");
    expect(html).toContain("CCTV");
  });
  it("renders nodes without media as before", () => {
    const html = card(data(node()));
    expect(html).not.toContain("pin-media");
    expect(html).not.toContain("<img");
    expect(html).toContain("summary text");
  });
  it("shows the description as inferred in the source panel", () => {
    const html = renderToStaticMarkup(
      <MediaInspector node={node(video) as never} caseId="c1" />,
    );
    expect(html).toContain("Description (LLM");
    expect(html).toContain("inferred");
    expect(html).toContain("Seek video to 0:12");
  });
  it("finds the media node for a citation selection", () => {
    const nodes = [node(video)];
    expect(
      mediaNodeFor(nodes, { kind: "source", id: "EV-022:row=1" })?.id,
    ).toBe("n1");
    expect(mediaNodeFor(nodes, { kind: "source", id: "EV-999:row=1" })).toBe(
      undefined,
    );
  });
});

describe("replay of media cards", () => {
  let seq = 0;
  const ev = (type: TraceEvent["type"], extra = {}): TraceEvent =>
    ({ seq: ++seq, tMs: seq, type, phase: "ingest", ...extra }) as TraceEvent;
  it("reveals when its file is parsed", () => {
    const n = node(video);
    expect(itemRevealed(n, emptyProgress())).toBe(false);
    const p = summarize([ev("file_parsed", { evidenceId: "EV-022" })]);
    expect(itemRevealed(n, p)).toBe(true);
  });
  it("withholds the description until media_vision finishes", () => {
    const n = node(video);
    const parsed = summarize([ev("file_parsed", { evidenceId: "EV-022" })]);
    expect(withheldVision(n, parsed).media?.vision).toBeNull();
    const done = summarize([
      ev("file_parsed", { evidenceId: "EV-022" }),
      ev("stage_finished", { stage: "media_vision" }),
    ]);
    expect(withheldVision(n, done).media?.vision).toBe(vision);
    const partial = revealCase(
      {
        nodes: [n],
        edges: [],
        gaps: [],
        suggestions: [],
        insights: [],
      } as never,
      parsed,
    );
    expect(partial.nodes[0].media?.vision).toBeNull();
  });
});
