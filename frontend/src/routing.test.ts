import { describe, expect, it } from "vitest";
import { casePath, parseRoute } from "./routing";

describe("application routes", () => {
  it("recognizes the welcome page and a case path", () => {
    expect(parseRoute("/")).toEqual({ kind: "welcome" });
    expect(parseRoute("/cases/synthetic-demo")).toEqual({
      kind: "case",
      caseId: "synthetic-demo",
    });
  });

  it("decodes URL-safe case IDs and accepts a trailing slash", () => {
    expect(parseRoute("/cases/case%20one/")).toEqual({
      kind: "case",
      caseId: "case one",
    });
    expect(casePath("case one")).toBe("/cases/case%20one");
  });

  it("rejects malformed paths and unsafe encoded segments", () => {
    for (const path of [
      "/unknown",
      "/cases",
      "/cases/a/b",
      "/cases/%2F",
      "/cases/%5C",
      "/cases/%ZZ",
    ]) {
      expect(parseRoute(path), path).toEqual({ kind: "not-found" });
    }
  });

  it("does not permit unsafe IDs when constructing links", () => {
    expect(() => casePath("")).toThrow();
    expect(() => casePath("a/b")).toThrow();
    expect(() => casePath(".")).toThrow();
    expect(() => casePath("..")).toThrow();
  });
});
