# Run trace, provenance and chat steps (contract)

The contract shared by the backend and the frontend for the live import view, board provenance and the chat
step display. Field names on the wire are camelCase. Every value comes from the run itself; the frontend only paces
and displays it.

## Run trace

Each ingestion version writes `ingest/vN/trace.jsonl`, one JSON event per line, appended and flushed as the run
happens (ingestion and analysis both write to it), so it can be read while the job is still processing. It is
included in the demo snapshot.

`GET /cases/{caseId}/trace?after=<seq>` returns

```json
{"status": "processing|ready|failed", "timing": "recorded|estimated|live", "events": [TraceEvent, ...], "next": 57}
```

`after` is exclusive (default `0` returns everything). `next` is the seq to pass on the next poll. The endpoint
works while the job runs (the case directory exists from the upload onwards) and returns a 404 `not_found` error
when the case has no trace.

### TraceEvent

Common fields: `seq` (1-based, increasing), `tMs` (milliseconds since the run started on the *replay clock*,
see below), `phase`, `type`.

`phase` is one of `ingest`, `rules`, `ml`, `llm`, `agent`, `output`.

| type | phase | extra fields |
|---|---|---|
| `run_started` | ingest | `mode`: `live` or `replay`; `llm`: bool; `model`: string or null; `archive`: {`filename`, `sha256`, `bytes`} |
| `phase_started` | any | `label` (human text, e.g. "Hashing and parsing evidence") |
| `phase_finished` | any | `label`, `durationMs` |
| `file_hashed` | ingest | `evidenceId`, `filename`, `sha256`, `bytes`, `manifestMatch` (bool or null) |
| `file_parsed` | ingest | `evidenceId`, `filename`, `format`, `parseStatus`, `records` (int), `recordTypes` ({type: count}) |
| `entities_linked` | ingest | `entities` (int), `links` (int) |
| `stage_finished` | rules, ml, llm, agent | `stage` (pipeline stage name, e.g. `connections`, `findings`, `ml_signals`, `claims`, `contradictions`, `gaps`, `insights`, `agent_insights`), `label`, `counts` ({name: int}), `durationMs` |
| `ml_signal` | ml | `id` (`ML-xx`), `signalType`, `title`, `method` (model name) |
| `llm_call` | llm, agent | `purpose` (`claim_extraction`, `investigator`, `verifier`), `model`, `inputTokens`, `outputTokens`, `cacheReadTokens`, `cacheWriteTokens`, `costUsd`, `durationMs`, `durationSource` (`recorded`, `estimated`, `live`), `replayed` (bool), `startMs` (replay-clock start; `tMs` is the end) |
| `agent_tool` | agent | `tool` (tool name), `args` (short object; strings truncated to 120 chars), `resultChars` (int) |
| `insight_recorded` | agent | `id` (always `null`: display IDs are assigned when the run ends, match the board insight by `key`), `key`, `title` |
| `run_finished` | output | `status` (`ready` or `failed`), `durationMs`, `totals` ({`records`, `nodes`, `edges`, `gaps`, `insights`, `signals`, `llmCalls`, `toolCalls`, `costUsd`}) |

### Replay clock

`tMs` is the wall clock of the run, except that a replayed LLM call (served from the committed cache) advances the
clock by its *recorded* duration instead of the near-zero replay time. Cache entries keep `latency_ms` from the
recording run when they have it (`durationSource: "recorded"`). Older entries have no latency, so the duration is
estimated from the recorded token counts (`durationSource: "estimated"`, formula in `mapletrace_reason/llm_cache.py`: 600 ms + output tokens / 200 per second, calibrated to the roughly five minutes the Kestrel recording took). Replayed calls are placed one after another: the cache does not record start times, so overlap in the original run cannot be reconstructed.
A live billed run reports real durations (`"live"`). The response's top-level `timing` is `recorded` only when every
replayed call had a recorded latency, `estimated` if any did not, and `live` for a live run. The UI must label
estimated timing as estimated.

Cost uses the per-token prices in `backend/LLM_COSTS.md` and the usage the API reported for that call.

## Board provenance

Every board node and edge carries

- `origin`: `record` (directly from ingested records), `rules` (deterministic analysis), `ml` (traditional ML,
  `mapletrace_reason/ml.py`), `llm` (LLM claim extraction) or `agent` (deepagents investigator insight);
- `stage`: the pipeline stage that produced it (matches `stage_finished.stage`; `ingest` for record items);
- `evidenceIds`: the evidence IDs of its citations, so the UI can reveal a record node once its file has parsed.

`origin` is independent of `certainty`: an `ml` item is always inferred, but a `rules` item may be observed or
inferred. ML signals and agent insights appear on the board as inferred nodes joined to the nodes whose citations
they share (edge `basis` says so). These nodes have `id` `sig-<key>` or `ins-<key>`, `itemId` (`ML-xx`/`I-xx`) and `key`; their edges have type `inference` and are undirected. The trace endpoint returns an empty `events` list with status `processing` while a new case has not written its first event yet. Insights and signals in the side lists carry the same `origin`.

## Upload mode

`POST /upload` accepts form field `analysis_mode`: `replay` (default: deterministic stages plus the committed LLM
cache for this archive if one exists; free) or `live` (real model calls, billed; never reads or writes the
committed cache). `live` without a server API key returns 400 `needs_api_key`. `GET /health` reports
`{"llmLive": bool}` so the UI can offer the live option. The confirm dialog
shows the cost figures from `LLM_COSTS.md` as an estimate.

## Chat steps

`POST /cases/{caseId}/chat` replies additionally carry `steps`: the answer's tool loop in order,

```json
[{"type": "model_call", "inputTokens": 1200, "outputTokens": 300, "costUsd": 0.005, "durationMs": 4100,
  "durationSource": "recorded|estimated|live"},
 {"type": "tool_call", "tool": "search_records", "args": {"query": "badge"}, "resultChars": 2311}]
```

and `replayed` (already present). The frontend animates these steps at their durations (sped up) before the answer
appears, and labels replayed answers as replayed.
