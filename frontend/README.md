# MapleTrace frontend

React + Vite evidence board for source-linked case review. Case data comes from the FastAPI backend in `../backend`, which ingests the ZIP and produces every case fact. A disposable mock adapter with fictional fixtures remains available; it does not read ZIP contents or perform analysis.

Setup, the demo path and Docker are in the [root README](../README.md); rules and design decisions are in [AGENTS.md](../AGENTS.md).

## Development

From the repository root, `make dev` runs the API and Vite together; `make frontend-dev` runs Vite alone. Without Make, from `frontend/`:

```sh
bun install --frozen-lockfile
bun run --bun dev        # Vite on :5173
bun run --bun test       # Vitest suite
bun run --bun build      # type-check and build into dist/
bun run --bun preview    # serve dist/ (proxies /api like dev)
bun run --bun format     # Prettier over src, index.html and config
```

Add dependencies with `bun add <package>` or `bun add -d <package>` and commit `bun.lock`.

## Adapters

`VITE_API_BASE_URL` selects the adapter (see `.env.example`):

- **Unset in development, or a base URL such as `/api`:** the live adapter. In development Vite proxies `/api` to `MAPLETRACE_API_URL` (default `http://127.0.0.1:8000`) and strips the prefix. Cases persist in `backend/data/`.
- **`mock`:** the fixture adapter. Production builds also use the mock unless `VITE_API_BASE_URL` is set at build time.

Chat calls same-origin `/api`, or `VITE_CHAT_API_BASE_URL` when set.

## Routes

| Path | View |
| --- | --- |
| `/` | Landing page |
| `/projects`, `/projects/new` | Project manager; naming plus ZIP selection |
| `/cases/:caseId` | Mind map |
| `/cases/:caseId/insights/{questions,evidence,inferences}` | Insights (bare `/insights` shows Questions) |
| `/cases/:caseId/evidence`, `/evidence/:sourceId` | Raw evidence; a citation (`EV-071:seq=40162`) or bare evidence ID opens that file at the cited position |
| `/cases/:caseId/files` | Generalized files (normalized ingestion records) |
| `/cases/:caseId/chat` | Case chat |

Browser history and direct links work; nginx falls back to the app for these routes. With the mock adapter, excerpts are fictional, originals are unavailable and no normalized records exist.

## Structure

- `src/api/types.ts`: the `CaseApi` presentation contract. The backend is authoritative; when they disagree, change these types. The API is documented in [backend/README.md](../backend/README.md#api-mapletrace_api).
- `src/api/http.ts`: live adapter (upload, status, cases, demo, files, records, evidence viewer, audit chain). Backend errors `{"error": {"code", "message"}}` surface as `ApiError`.
- `src/api/client.ts`: adapter selection and the mock jobs. `src/api/fixtures.ts`: the mock's fictional case.
- `src/api/chat.ts` and `src/components/useCaseChat.ts`: chat adapter and hook; contract in [CHAT.md](CHAT.md).
- `src/api/files.ts`: source index built from citations already in `CaseData`.
- `src/routing.ts`: route parsing, `casePath()` and `insightsPath()`.
- `src/App.tsx`: the board, top bar and review dock. `src/components/CaseWorkspace.tsx`: sections and the left toolbar.
- `src/components/board-layout.ts`, `board-colors.ts`, `board-focus.ts`, `CanvasMinimap.tsx`, `BoardLegend.tsx`: presentation-only layout, colour coding, focus and overview.
- `src/components/insights-sections.ts`: groups API data into the Insights tabs.
- `src/onboarding/`: landing page and project manager, with their own styles.
- `src/styles/`: tokens (`base.css`), workspace, evidence cards, review dock and upload styles.

TanStack Query loads cases and polls job status. UI components never import fixtures.

## Not done yet

- A timeline view of `timeline`; the board's `changes` and `overrides` are not shown.
- Investigator overrides and adding evidence to a case (`POST /cases/{caseId}/overrides`, `POST /cases/{caseId}/evidence`) have no UI.
