import { afterEach, describe, expect, it, vi } from "vitest";
import { chatApi } from "./chat";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("chat API adapter", () => {
  it("enables chat only for an authoritative matching case", async () => {
    const fetchMock = vi.fn().mockImplementation(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({
            available: true,
            authoritative: true,
            case_id: "case-123",
          }),
          { status: 200 },
        ),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(chatApi.status("case-123")).resolves.toEqual({
      available: true,
      authoritative: true,
      case_id: "case-123",
    });
    await expect(chatApi.status("other-case")).resolves.toMatchObject({
      available: false,
      reason: "Chat is connected to a different case.",
    });
  });

  it("does not enable non-authoritative or unreachable chat", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(
            JSON.stringify({ available: true, case_id: "case-123" }),
            { status: 200 },
          ),
        ),
    );
    await expect(chatApi.status("case-123")).resolves.toMatchObject({
      available: false,
      reason: "Chat is not connected to an authoritative ingested case.",
    });

    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
    await expect(chatApi.status("case-123")).resolves.toMatchObject({
      available: false,
    });
  });

  it("sends a multi-turn request with its thread ID and propagates cancellation", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          thread_id: "thread-1",
          message: { role: "assistant", content: "No sourced answer yet." },
        }),
        { status: 200 },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    const controller = new AbortController();

    await expect(
      chatApi.send("case/one", "Follow up", "thread-1", controller.signal),
    ).resolves.toMatchObject({ thread_id: "thread-1" });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/cases/case%2Fone/chat",
      expect.objectContaining({
        method: "POST",
        signal: controller.signal,
        body: JSON.stringify({ message: "Follow up", thread_id: "thread-1" }),
      }),
    );

    const cancelled = new AbortController();
    cancelled.abort();
    fetchMock.mockRejectedValueOnce(new DOMException("Aborted", "AbortError"));
    await expect(
      chatApi.send("case-123", "Question", undefined, cancelled.signal),
    ).rejects.toMatchObject({ name: "AbortError" });
  });

  it("surfaces backend errors without inventing a reply", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "Model is not configured." }), {
          status: 503,
        }),
      ),
    );
    await expect(chatApi.send("case-123", "Question")).rejects.toThrow(
      "Model is not configured.",
    );
  });

  it("rejects malformed replies before they reach the transcript", async () => {
    for (const payload of [
      null,
      {},
      { thread_id: "a", message: { role: "user", content: "spoof" } },
      {
        thread_id: "a",
        message: { role: "assistant", content: "text", citations: [null] },
      },
    ]) {
      vi.stubGlobal(
        "fetch",
        vi
          .fn()
          .mockResolvedValue(
            new Response(JSON.stringify(payload), { status: 200 }),
          ),
      );
      await expect(chatApi.send("case-123", "Question")).rejects.toThrow(
        "invalid response",
      );
    }
  });
});
