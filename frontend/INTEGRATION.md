# Frontend ↔ backend integration

Working plan for the `integration` branch. The backend (`backend/`) is authoritative for case facts; the frontend adapts to it. Both sides may change where needed to make the integration work.

Baseline checked against a real run: `mapletrace_ingest` + `mapletrace_reason analyze` (no LLM) on `cases/kestrel` produced 58 nodes, 56 edges, 7 gaps, 10 insights, 13 suggestions, 455 sources, 299 timeline entries, 2 contradictions, 1 explanation set, 15 missing periods, 30 uncertain times, 2 source groups, 20 ML signals and 15 audit entries.

## Backend output the frontend does not use

API calls the frontend never makes:
- `POST /upload` (with `case_name`, `timezone`, `llm`), `GET /status/{jobId}` (`failed`, `stage`, `caseId`), `GET /cases`, `GET /cases/{caseId}`, `GET /health`.
- `GET /cases/{caseId}/evidence/{evidenceId}` (original file download).
- `POST /cases/{caseId}/evidence` (add evidence, new version, `changes`).
- `GET`/`POST /cases/{caseId}/overrides` (dismiss, confirm, set status/label, note, reject link; target `key`).

Fields on items already shown:
- Nodes/edges: `certainty` (`observed` | `inferred`), edge `basis`. The frontend currently infers observed/inferred from edge `type`, so inferred `identity` and co-location edges display as observed links.
- Gaps: `gapType`, `status`, `previousStatus`, `missing`, `direction`, `answer`, `key`.
- Insights: `observations[]` (each cited), `inference`, `unknowns`, `counterevidence`, `assumptions`, `limitations`, `confidence`, `status`, `explanations`, `key`.
- Suggestions: `gapIds[]`, `artifact`, `score`, `key`.
- Sources: `metadata.reliability`, `time_precision`, `time_flags`, `who`, `evidence_id`, `locator` (rendered only as generic key/value pairs).

Sections with no UI: `contradictions`, `explanations`, `timeline`, `missingPeriods`, `uncertainTimes`, `sourceGroups`, `signals`, `changes`, `overrides`, `timeRange`.

## Frontend needs the backend did not supply

| Need | Status |
|---|---|
| Citations on every node (45 of 58 entity/place nodes had none) | Backend fix |
| Explicit `directed` on edges | Backend fix |
| Gap ↔ node links (no node received a `gapId` on Kestrel; `affectedClaims` are display strings) | Backend fix: `gaps[].nodeIds` and `nodes[].gapId` |
| Evidence file inventory for `/files` (sources are cited records, not files) | Backend: `GET /cases/{caseId}/files` |
| Normalized records (`normalizedRecords`) | Backend: `GET /cases/{caseId}/records` |
| Ingestion audit chain and verification | Backend: `GET /cases/{caseId}/audit-chain` |
| Case time zone for local time display | Backend: top-level `timezone` |
| Readable layout for real node counts (backend columns are 130px apart, cards ~224px) | Frontend layout (presentation only) |
| Chat endpoint matching `frontend/CHAT.md` | Not built; chat stays unavailable |

## Mismatches

- Scores are computed ranks, not illustrative; insights carry a `confidence` label that must not be shown as a percentage.
- Errors are `{"error": {"code", "message"}}`; the chat client reads `detail`.
- Backend rejects uploads over 100 MB and non-ZIP content; mock copy says there is no size cap and contents are not read.
- Mock disclaimers must only appear when the mock adapter is active.
- Times are ISO UTC strings shown raw.
- Labels are capped at 60 characters, summaries at 400.

## Backend contract additions (this branch)

- `nodes[].citations`: non-empty for every node (entity and place nodes cite the records that place them on the board).
- `edges[].directed`: `true` only where the relation has a real direction (person → statement "stated", statement → event "conflicts with", event → place "occurred at", person → event "recorded at"); `false` for communication, co-location and identity.
- `gaps[].nodeIds`: board node IDs the gap concerns; `nodes[].gapId` set from the highest-scoring gap that concerns the node.
- Top-level `timezone`: IANA case time zone (`case_info`), or `"UTC"`.
- `GET /cases/{caseId}/files`: one entry per evidence file — `evidenceId`, `fileId`, `path`, `filename`, `sha256`, `bytes`, `format`, `evidenceType`, `parseStatus`, `recordCount`, `manifestMatch`, `origin`.
- `GET /cases/{caseId}/records?evidenceId=&limit=&offset=`: `{total, items: [{id, recordType, fields, citations: [{evidenceId, locator, sourceId?}]}]}`.
- `GET /cases/{caseId}/audit-chain`: ingestion + analysis audit entries with hashes, and `{verified, head}`.

## Order of work

1. Connect: real `CaseApi` adapter selected by `VITE_API_BASE_URL` (mock remains the fallback), Vite proxy for dev, case by ID, `failed` status and `caseId`, project name sent as `case_name`, backend error format, adapter-aware disclaimers, project list from `GET /cases`.
2. Correct what is shown: certainty from the API, scores relabelled, layout for real node counts, local time display, directed edges, node citations.
3. Richer data: structured insights, gap type/status, contradictions, competing explanations, original file download, evidence file list.
4. Optional views: timeline with missing periods and uncertain times, ML signals, overrides, add evidence, chat.
5. Adapter tests, a root `make` target to run both servers, and `AGENTS.md` updates.
