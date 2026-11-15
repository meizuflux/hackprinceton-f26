import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { ChatStatus } from "../api/chat";
import { ChatSuggestions } from "./ChatSuggestions";

const status: ChatStatus = {
  available: true,
  live: false,
  suggestions: [
    { question: "Who was there?", recorded: true },
    { question: "Where was he?", recorded: true },
    { question: "Who uses the phone?", recorded: false },
  ],
};

describe("ChatSuggestions", () => {
  it("lists every suggestion before the first question", () => {
    const html = renderToStaticMarkup(
      <ChatSuggestions
        status={status}
        live={false}
        disabled={false}
        onAsk={() => {}}
      />,
    );
    expect(html).toContain("Suggested questions");
    expect(html).toContain("Who was there?");
    expect(html).toContain("Who uses the phone?");
  });

  it("shows only questions not yet asked once a conversation exists", () => {
    const html = renderToStaticMarkup(
      <ChatSuggestions
        status={status}
        live={false}
        disabled={false}
        onAsk={() => {}}
        compact
        asked={["Who was there?"]}
      />,
    );
    expect(html).toContain("Ask next");
    expect(html).not.toContain("Who was there?");
    expect(html).toContain("Where was he?");
  });

  it("holds suggestions while an answer is still playing", () => {
    const html = renderToStaticMarkup(
      <ChatSuggestions
        status={status}
        live={false}
        disabled
        onAsk={() => {}}
        compact
        asked={[]}
      />,
    );
    expect(html.match(/disabled=""/g)?.length).toBe(3);
  });

  it("renders nothing when every suggestion has been asked", () => {
    const html = renderToStaticMarkup(
      <ChatSuggestions
        status={status}
        live={false}
        disabled={false}
        onAsk={() => {}}
        compact
        asked={status.suggestions!.map((s) => s.question)}
      />,
    );
    expect(html).toBe("");
  });
});
