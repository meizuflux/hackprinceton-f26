# Case chat contract

The backend (`backend/mapletrace_api/chat.py`, `backend/mapletrace_reason/chat.py`) answers questions about the latest analysis of an ingested case with `claude-sonnet-5-5` and read-only tools. The frontend never supplies answers, fixtures or fallbacks. Two views share one adapter (`src/api/chat.ts`) and one hook (`src/components/useCaseChat.ts`):

- **`/cases/:caseId/chat`:** the chat page (`ChatPanel`), with cited excerpts under each answer.
- **The mind map:** the floating "Ask a question" widget (`AskWidget`), mounted in `Board` in `src/App.tsx`. It sits above the minimap and zoom controls, expands upward, moves left of the review dock when the dock is open, and closes with Escape (focus returns to its button).

The adapter calls same-origin `/api` (the Vite proxy strips it), or `VITE_CHAT_API_BASE_URL` when set. Model credentials live only on the server.

## `GET /chat/status?case_id={caseId}`

```json
{
  "available": true,
  "authoritative": true,
  "case_id": "kestrel-demo",
  "live": false,
  "mode": "replay",
  "model": "claude-sonnet-5-5",
  "suggestions": [{ "question": "Where was … during …?", "recorded": true }],
  "reason": "Live questions need an Anthropic API key on the server. …"
}
```

- The frontend requires an exact `case_id` match and `authoritative: true`. An unknown or unfinished case returns `{"available": false, "case_id", "reason"}`.
- `live` is true when the server has `ANTHROPIC_API_KEY`. Without it only recorded answers replay, and the composer is disabled.
- `suggestions` (3 to 5) are derived deterministically from the analysis: the undecided key event, the strongest contradiction, and the highest-ranked open gaps. `recorded` means the answer replays from the cache without a model call; the server checks this by replaying it.

## `POST /cases/{caseId}/chat`

Request: `{"message": "…", "thread_id": "optional"}` (1 to 1000 characters).

```json
{
  "thread_id": "server-owned id",
  "suggested": true,
  "replayed": true,
  "model_calls": 4,
  "message": {
    "role": "assistant",
    "content": "Plain-text rendering of the whole answer",
    "evidence_status": "partial",
    "summary": "One or two neutral sentences.",
    "observations": [{ "text": "…", "citations": [0] }],
    "inference": "What may follow; not established by the records.",
    "unknowns": ["What the records do not show."],
    "citations": [
      {
        "evidence_id": "EV-071",
        "locator": "seq=40162",
        "excerpt": "Record text",
        "source_id": "EV-071:seq=40162"
      }
    ]
  }
}
```

- **Cite or drop:** each observation cites record IDs a tool returned in that conversation; others are dropped by the server. `observations[].citations` index into `citations`, and the adapter drops observations whose indices do not resolve. `source_id` is present only when the citation is on the board (`CaseData.sources`); only those chips open the source inspector.
- **`evidence_status`:** `supported`, `partial` (some citations were dropped or support is incomplete) or `insufficient` (nothing cited survives, or the records do not answer).
- **Observed versus inferred:** observations, inference and unknowns render as separate sections; the inference is labelled and dashed, like inferred threads on the board.
- **`suggested`:** the question matched a suggested question. Those are always answered without thread history, so a recorded answer replays in any thread. `replayed` is true when no model call was made.
- **Threads:** memory is per `thread_id` in server memory (200 threads, last 4 turns) and is lost on restart; an unknown `thread_id` starts a new thread and returns its new ID.
- **Errors** are `{"error": {"code", "message"}}`: `needs_api_key` (503) when the answer is not recorded and the server has no key (nothing is sent to the model); `model_error` (502); `empty_message` and `message_too_long` (400). The UI shows `needs_api_key` as a notice, not an error page.

## Cost

Suggested answers are recorded once (`make backend-chat-record`, billed) into `backend/llm_cache/chat-<archive sha256>.jsonl` and replay for free. Every free-typed question is a live, billed model call, and the UI says so. See `backend/LLM_COSTS.md`.
