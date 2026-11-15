import { describe, expect, it } from "vitest";
import type { EvidenceFile, EvidenceView, SourceRecord } from "../api/types";
import { casePath, parseRoute } from "../routing";
import {
  columnWidths,
  describeTarget,
  evidenceLink,
  fileFolder,
  groupFiles,
  matchesFile,
  parseEvidenceTarget,
  rangeAt,
  visibleSlice,
} from "./evidence-view";

const source = (id: string, evidenceId: string, locator: string) =>
  ({
    id,
    path: "",
    kind: "event",
    timestamp: "",
    hash: "",
    excerpt: "",
    metadata: { evidence_id: evidenceId, locator },
  }) satisfies SourceRecord;

const file = (evidenceId: string, path: string): EvidenceFile => ({
  evidenceId,
  fileId: 1,
  path,
  filename: path.split("/").at(-1)!,
  sha256: "a".repeat(64),
  bytes: 10,
  format: "csv",
  evidenceType: "records",
  parseStatus: "parsed",
  recordCount: 1,
  manifestMatch: true,
  origin: "zip_member",
});

describe("citation targets", () => {
  it("uses the board source metadata for evidence ID and locator", () => {
    const sources = [
      source(
        "EV-103:message_id=<a@b.example>",
        "EV-103",
        "message_id=<a@b.example>",
      ),
    ];
    expect(
      parseEvidenceTarget("EV-103:message_id=<a@b.example>", sources),
    ).toEqual({
      evidenceId: "EV-103",
      locator: "message_id=<a@b.example>",
      sourceId: "EV-103:message_id=<a@b.example>",
    });
  });

  it("splits unknown citations at the first colon and treats a bare ID as a file", () => {
    expect(parseEvidenceTarget("EV-070:row=616")).toEqual({
      evidenceId: "EV-070",
      locator: "row=616",
    });
    expect(parseEvidenceTarget("EV-070")).toEqual({ evidenceId: "EV-070" });
    expect(parseEvidenceTarget("EV-076:uid=KESTREL:1")).toMatchObject({
      evidenceId: "EV-076",
      locator: "uid=KESTREL:1",
    });
  });

  it("round-trips citation links through the evidence route", () => {
    const segment = evidenceLink("EV-063", "id=PV-00021");
    const route = parseRoute(casePath("k-1", "evidence", segment));
    expect(route).toEqual({
      kind: "case",
      caseId: "k-1",
      view: "evidence",
      sourceId: "EV-063:id=PV-00021",
    });
  });
});

describe("file browser", () => {
  it("groups files by submitted folder in path order, nested files under their container", () => {
    const groups = groupFiles([
      file("EV-070", "case/evidence/06_logs/badge.csv"),
      file("EV-003", "case/evidence/00_intake/custody.csv"),
      file("FILE-9", "case/evidence/06_logs/backup.zip::inner/a.csv"),
    ]);
    expect(groups.map((g) => g.folder)).toEqual(["00_intake", "06_logs"]);
    expect(groups[1].files.map((f) => f.evidenceId)).toEqual([
      "FILE-9",
      "EV-070",
    ]);
    expect(fileFolder("top.csv")).toBe("Archive root");
  });

  it("searches name, ID and type", () => {
    const f = file("EV-070", "case/evidence/06_logs/badge_bldg_e.csv");
    expect(matchesFile(f, "ev-070")).toBe(true);
    expect(matchesFile(f, "BADGE")).toBe(true);
    expect(matchesFile(f, "records")).toBe(true);
    expect(matchesFile(f, "email")).toBe(false);
  });
});

describe("viewer geometry", () => {
  it("finds the range covering an item", () => {
    const ranges = [{ start: 4, end: 6 }];
    expect(rangeAt(ranges, 5)).toEqual(ranges[0]);
    expect(rangeAt(ranges, 7)).toBeUndefined();
  });

  it("describes resolved positions in the file's own numbering", () => {
    const base = {
      target: { ranges: [{ start: 614, end: 614 }], page: null, whole: false },
    };
    expect(
      describeTarget({
        ...base,
        table: { items: [] },
      } as unknown as EvidenceView),
    ).toBe("row 616");
    expect(
      describeTarget({
        target: {
          ranges: [{ start: 843, end: 862 }],
          page: null,
          whole: false,
        },
        lines: { unit: "line" },
      } as unknown as EvidenceView),
    ).toBe("lines 844–863");
    expect(
      describeTarget({
        target: { ranges: [], page: null, whole: true },
      } as unknown as EvidenceView),
    ).toBe("the whole file");
  });

  it("windows a fixed-height list", () => {
    expect(visibleSlice(3000, 600, 30, 2000, 5)).toEqual({
      start: 95,
      end: 125,
    });
    expect(visibleSlice(0, 600, 30, 10)).toEqual({ start: 0, end: 10 });
  });

  it("sizes columns from content within bounds", () => {
    const widths = columnWidths(
      ["id", "body"],
      [{ cells: ["1", "x".repeat(200)] }],
    );
    expect(widths).toEqual([7, 46]);
  });
});
