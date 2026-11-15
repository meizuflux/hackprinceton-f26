import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { CaseData, NormalizedEvidenceRecord } from "../api/types";
import { EvidenceBrowser } from "./EvidenceBrowser";

const emptyCase: CaseData = {
  id: "test",
  title: "Test",
  subtitle: "",
  timeRange: { start: "", end: "" },
  nodes: [],
  edges: [],
  gaps: [],
  insights: [],
  suggestions: [],
  sources: [],
  audit: [],
};

function renderRecords(records: NormalizedEvidenceRecord[]) {
  return renderToStaticMarkup(
    <EvidenceBrowser
      data={emptyCase}
      mode="generalized"
      generalizedRecords={records}
      onInspect={() => {}}
    />,
  );
}

describe("normalized evidence provenance", () => {
  it("keeps supplied fields next to the original evidence ID and locator", () => {
    const html = renderRecords([
      {
        id: "record-1",
        recordType: "message",
        fields: { content: "Provided by ingestion" },
        citations: [{ evidenceId: "EV-001", locator: "row=4" }],
      },
    ]);
    expect(html).toContain("Provided by ingestion");
    expect(html).toContain("EV-001");
    expect(html).toContain("row=4");
    expect(html).not.toContain("Original file unavailable");
  });

  it("withholds uncited fields and locators that are missing", () => {
    const html = renderRecords([
      {
        id: "missing-citation",
        recordType: "message",
        fields: { content: "Uncited assertion" },
        citations: [],
      },
      {
        id: "missing-locator",
        recordType: "message",
        fields: { content: "Unlocated assertion" },
        citations: [{ evidenceId: "EV-001", locator: "" }],
      },
    ]);
    expect(html).not.toContain("Uncited assertion");
    expect(html).not.toContain("Unlocated assertion");
  });

  it("reports an unknown source link instead of substituting a different source", () => {
    const html = renderToStaticMarkup(
      <EvidenceBrowser
        data={emptyCase}
        mode="raw"
        selectedSourceId="missing"
        onInspect={() => {}}
      />,
    );
    expect(html).toContain("Source missing is not available in this case.");
    expect(html).not.toContain("FICTIONAL EXCERPT");
  });
});
