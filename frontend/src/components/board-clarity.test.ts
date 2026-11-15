import { describe, expect, it } from "vitest";
import type { EvidenceNode, SourceRecord } from "../api/types";
import { getPinDimensions, PIN_GAP } from "./board-layout";
import { layoutCaseGraph } from "./graph-layout";
import {
  cardSummary,
  cardTitle,
  formatLocator,
  rawLabelNote,
  shortMethod,
  sourceHeading,
  tidyLabel,
} from "./readable";
import { placeThreadLabels, threadPoint } from "./thread-geometry";
import { createReuse, searchText } from "./board-render";

describe("readable card wording", () => {
  it("prefers the backend's display label and keeps the raw label as metadata", () => {
    const node = { label: "SC-EBC-01", displayLabel: "Secure cabinet, EBC" };
    expect(cardTitle(node)).toBe("Secure cabinet, EBC");
    expect(rawLabelNote(node)).toBe("SC-EBC-01");
    expect(
      cardSummary({ label: "x", summary: "raw", displaySummary: "nice" }),
    ).toBe("nice");
  });
  it("tidies key=value labels without inventing or completing values", () => {
    expect(
      tidyLabel("scan_id=RF-00111; reader_id=RF-SC-EBC-01; tag_id=ES-0007; cu"),
    ).toBe("Scan RF-00111 · reader RF-SC-EBC-01 · tag ES-0007");
    // A last pair cut at the backend's label length is dropped, never guessed.
    expect(
      tidyLabel("scan_id=GT-0061; checkpoint_id=E-L1-CP1; officer_note=All se"),
    ).toBe("Scan GT-0061 · checkpoint E-L1-CP1");
    expect(tidyLabel("DOOR_HELD_OPEN @ P2 garage elevator lobby door")).toBe(
      "Door held open at P2 garage elevator lobby door",
    );
    // Ordinary labels are untouched and need no raw-label note.
    expect(tidyLabel("Richard Halvorsen")).toBe("Richard Halvorsen");
    expect(rawLabelNote({ label: "+14085550147" })).toBeUndefined();
  });
  it("heads excerpts with a file name and position, keeping the citation", () => {
    const source = {
      id: "EV-075:row=72",
      path: "kestrel_case/evidence/06_logs/ws_exec0001.csv",
      metadata: { locator: "row=72" },
    } as unknown as SourceRecord;
    expect(sourceHeading(source)).toEqual({
      heading: "ws_exec0001.csv · row 72",
      citation: "EV-075:row=72",
    });
    expect(
      sourceHeading({ ...source, fileLabel: "Workstation log" }).heading,
    ).toBe("Workstation log · row 72");
    expect(formatLocator("event_id=BDG-000615")).toBe("event BDG-000615");
  });
  it("shortens ML method names for the card face", () => {
    expect(shortMethod("DBSCAN (haversine)")).toBe("DBSCAN");
    expect(shortMethod("IsolationForest on daily movement profiles")).toBe(
      "IsolationForest",
    );
    expect(shortMethod(undefined)).toBeUndefined();
  });
  it("searches readable and raw wording", () => {
    const text = searchText({
      label: "SC-EBC-01",
      title: "Secure cabinet",
      summary: "",
    });
    expect(text).toContain("sc-ebc-01");
    expect(text).toContain("secure cabinet");
  });
});

describe("full-graph layout", () => {
  const node = (id: string, type = "event", extra = {}) =>
    ({ id, type, ...extra }) as unknown as EvidenceNode;
  const nodes = [
    node("hub", "person"),
    ...Array.from({ length: 8 }, (_, i) => node(`phone${i}`, "device")),
    node("cam", "device"),
    node("photo", "event", { media: { kind: "photo" } }),
    node("lonely", "location"),
    node("a"),
    node("b"),
  ];
  const edges = [
    ...Array.from({ length: 8 }, (_, i) => ({
      source: "hub",
      target: `phone${i}`,
    })),
    { source: "photo", target: "cam" },
    { source: "cam", target: "hub" },
    { source: "a", target: "b" },
  ];
  const layout = layoutCaseGraph(nodes, edges);

  it("places every card with the 40px clearance", () => {
    expect(layout.size).toBe(nodes.length);
    const boxes = nodes.map((n) => ({
      ...layout.get(n.id)!,
      ...getPinDimensions(n),
    }));
    for (let i = 0; i < boxes.length; i++)
      for (let j = i + 1; j < boxes.length; j++) {
        const a = boxes[i];
        const b = boxes[j];
        const apart =
          a.x + a.width + PIN_GAP <= b.x + 0.5 ||
          b.x + b.width + PIN_GAP <= a.x + 0.5 ||
          a.y + a.height + PIN_GAP <= b.y + 0.5 ||
          b.y + b.height + PIN_GAP <= a.y + 0.5;
        expect(apart).toBe(true);
      }
  });
  it("is deterministic", () => {
    expect(layoutCaseGraph(nodes, edges)).toEqual(layout);
  });
  it("clusters by connection: a photo sits nearer its camera than unlinked cards", () => {
    const d = (a: string, b: string) =>
      Math.hypot(
        layout.get(a)!.x - layout.get(b)!.x,
        layout.get(a)!.y - layout.get(b)!.y,
      );
    expect(d("photo", "cam")).toBeLessThan(d("photo", "a"));
    // The unlinked card goes to the periphery below everything else.
    const lonelyY = layout.get("lonely")!.y;
    for (const n of nodes)
      if (n.id !== "lonely") expect(layout.get(n.id)!.y).toBeLessThan(lonelyY);
  });
});

describe("thread label placement", () => {
  it("moves a label off a card that covers the middle of its thread", () => {
    const source = { x: 0, y: 0, width: 100, height: 100 };
    const target = { x: 900, y: 0, width: 100, height: 100 };
    const blocker = { x: 380, y: 0, width: 240, height: 100 };
    const spots = placeThreadLabels(
      [
        {
          id: "e",
          source,
          target,
          sourceSide: "right",
          targetSide: "left",
          width: 90,
          height: 26,
        },
      ],
      [source, target, blocker],
    );
    const t = spots.get("e")!;
    expect(t).not.toBe(0.5);
    const at = threadPoint(
      { x: 100, y: 50, side: "right" },
      { x: 900, y: 50, side: "left" },
      t,
    );
    expect(at.x + 45 <= 380 || at.x - 45 >= 620).toBe(true);
  });
  it("keeps the middle when it is clear", () => {
    const source = { x: 0, y: 0, width: 100, height: 100 };
    const target = { x: 900, y: 0, width: 100, height: 100 };
    const spots = placeThreadLabels(
      [
        {
          id: "e",
          source,
          target,
          sourceSide: "right",
          targetSide: "left",
          width: 90,
          height: 26,
        },
      ],
      [source, target],
    );
    expect(spots.get("e")).toBe(0.5);
  });
});

describe("render reuse", () => {
  it("returns the same object while inputs are unchanged", () => {
    const reuse = createReuse<{ n: number }>();
    const first = reuse("a", [1, "x"], () => ({ n: 1 }));
    expect(reuse("a", [1, "x"], () => ({ n: 2 }))).toBe(first);
    expect(reuse("a", [2, "x"], () => ({ n: 3 }))).toEqual({ n: 3 });
  });
});
