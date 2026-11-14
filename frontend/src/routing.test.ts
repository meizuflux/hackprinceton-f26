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

  it("supports project manager and new-project deep links", () => {
    for (const path of ["/projects", "/projects/"]) {
      expect(parseRoute(path)).toEqual({ kind: "projects" });
    }
    for (const path of ["/projects/new", "/projects/new/"]) {
      expect(parseRoute(path)).toEqual({ kind: "new-project" });
    }
    expect(parseRoute("/projects/unknown")).toEqual({ kind: "not-found" });
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

  it("round-trips each workspace section and evidence citation deep link", () => {
    for (const view of ["evidence", "files", "insights", "chat"] as const) {
      expect(parseRoute(casePath("case one", view))).toEqual({
        kind: "case",
        caseId: "case one",
        view,
      });
    }
    expect(parseRoute(casePath("case one", "evidence", "source 2"))).toEqual({
      kind: "case",
      caseId: "case one",
      view: "evidence",
      sourceId: "source 2",
    });
    for (const path of [
      "/cases/a/unknown",
      "/cases/a/chat/source",
      "/cases/a/evidence/%2F",
      "/cases/a/evidence/%ZZ",
      "/cases/a/evidence/..",
      "/cases/a/files/x/y",
    ]) {
      expect(parseRoute(path), path).toEqual({ kind: "not-found" });
    }
    expect(() => casePath("a", "chat", "source")).toThrow();
    expect(() => casePath("a", "evidence", "../source")).toThrow();
  });
});
