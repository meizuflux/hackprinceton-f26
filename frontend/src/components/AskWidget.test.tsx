import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { AskWidget, submitToChat } from "./AskWidget";
import { takeQueuedQuestion } from "./chat-handoff";

describe("AskWidget", () => {
  it("queues the question and opens the chat tab instead of answering on the map", () => {
    const onAsk = vi.fn();
    expect(submitToChat("c1", "  What happened? ", true, onAsk)).toBe(true);
    expect(onAsk).toHaveBeenCalledOnce();
    expect(takeQueuedQuestion("c1")).toBe("What happened?");
    expect(takeQueuedQuestion("c1")).toBeUndefined();
  });
  it("ignores empty questions and unavailable chat", () => {
    const onAsk = vi.fn();
    expect(submitToChat("c2", "   ", true, onAsk)).toBe(false);
    expect(submitToChat("c2", "Hi", false, onAsk)).toBe(false);
    expect(onAsk).not.toHaveBeenCalled();
    expect(takeQueuedQuestion("c2")).toBeUndefined();
  });
  it("renders only a small input, never answers", () => {
    const html = renderToStaticMarkup(
      <AskWidget caseId="c3" onAsk={() => {}} />,
    );
    expect(html).toContain("ask-box");
    expect(html).not.toContain("chat-message");
  });
});
