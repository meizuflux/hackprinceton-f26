# Case chat UI contract

The chat panel is an optional frontend integration. It has no local model, fixture answers, or fallback responses. The existing fictional preview case is not sent to a backend unless an endpoint is configured, and a backend must confirm that it serves the requested case before the panel enables its composer.

Set `VITE_CHAT_API_BASE_URL` to the backend origin (for example, `http://localhost:8000`). When unset, the adapter tries the same-origin `/api` endpoints. Vite exposes this value in the browser, so it must contain only a public base URL; model credentials belong in the backend environment.

## Endpoints

### `GET /api/chat/status?case_id={caseId}`

Returns `{ "available": true, "authoritative": true, "case_id": "..." }` when the optional chat service is configured for this exact ingested case. Otherwise return `{ "available": false, "case_id": "...", "reason": "..." }`. The frontend requires both an exact case ID match and `authoritative: true`; this keeps the fictional preview from being mistaken for backend data.

### `POST /api/cases/{caseId}/chat`

Request body:

```json
{
  "thread_id": "optional existing conversation id",
  "message": "What evidence places the vehicle near the station?"
}
```

Response body:

```json
{
  "thread_id": "server-owned conversation id",
  "message": {
    "role": "assistant",
    "content": "The retrieved evidence records ...",
    "evidence_status": "supported",
    "citations": [
      {
        "evidence_id": "EV-071",
        "locator": { "seq": 40162 },
        "excerpt": "Relevant source text",
        "source_id": "optional CaseData.sources id"
      }
    ]
  }
}
```

`evidence_status` is `supported`, `partial`, or `insufficient`. Citation `evidence_id`, locator, and excerpt must come from authoritative backend records. `source_id` is optional and should only be included when it resolves to a source in the frontend's current `CaseData`; the panel otherwise displays the citation without trying to open a mock source. The backend should distinguish observed evidence from inference, state when evidence is insufficient, and never represent a gap as proof. Keep protected attributes out of retrieval results and model inputs through server-side field allowlists.

The panel keeps the returned `thread_id` for follow-up turns while it is mounted. Requests use `AbortController`; retries resubmit the last user turn. The JSON response is intentionally simple; a streaming endpoint can be added later without changing citation semantics.

## Deep Agents handoff

For a Python backend, LangChain's self-hosted Deep Agents SDK can provide the tool-calling loop and thread checkpointer. Give the agent only narrow read-only evidence retrieval tools; do not expose host filesystem or shell access. Tool results should contain allowlisted evidence fields and citations assembled from database rows. Configure `COMPSTAT_CASE_ID`, `COMPSTAT_CASE_RUN`, `COMPSTAT_CHAT_MODEL`, and the selected provider's API key on the server. See [Deep Agents overview](https://docs.langchain.com/oss/python/deepagents/overview), [customization](https://docs.langchain.com/oss/python/deepagents/customization), and [tools](https://docs.langchain.com/oss/python/langchain/tools).
