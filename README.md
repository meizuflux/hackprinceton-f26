# Compstat

An inspectable evidence pin board for a hackathon investigation demo. Built with Vite, React, TypeScript, React Flow, and TanStack Query.

## Run

```sh
npm install
npm run dev
```

Open the URL Vite prints (normally http://localhost:5173). Choose **Explore demo case**, or select a ZIP to see simulated ingestion. Open a ranked gap, inspect its original sources and suggested query, switch to Insights, and open Audit trail.

```sh
npm run build
npm test
npm run preview
```

## Temporary data and backend handoff

All case records, scores, hashes, source excerpts, insights, and audit entries are fictional fixtures in `src/api/fixtures.ts`. The ZIP adapter validates filename and size only; it never reads or uploads archive contents. No analysis or ML runs. Case changes and pin positions last only for the current mounted workspace.

`src/api/types.ts` is the current shared contract. `src/api/client.ts` implements `CaseApi`; replace that adapter with HTTP calls when the Python backend is ready. UI components do not import fixtures. TanStack Query polls `getStatus(jobId)` until ready and then loads the case through `getCase()`.

Suggested mapping:

| Adapter method | Backend |
| --- | --- |
| `createUpload(file)` | `POST /upload` with multipart file → `{ jobId }` |
| `getStatus(jobId)` | `GET /status/:id` → `{ status, progress, message }` |
| `getCase()` | Aggregate `/graph`, `/gaps`, `/insights`, `/audit` plus source records into `CaseData` |

Confirm the contract with the backend before connecting it: job-scoped case retrieval, timestamp formats, citation granularity, source metadata, graph positions or layout, score semantics, failure states, and access to original artifacts. The current mock supports a single case and processing/ready states only.

Every entity and relationship has source IDs. Gaps refer to suggested evidence IDs; suggestions link back to gaps. Citation inspection exposes the original source path, timestamp, excerpt, and a clearly fictional hash. The board supports dragging, pan/zoom, fit view, minimap, and local pin search. No authentication, durable storage, real uploads, or production case handling is implemented.
