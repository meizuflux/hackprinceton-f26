# MapleTrace frontend

React + Vite evidence board for source-linked case review. The UI loads case data through an API adapter. In development it talks to the FastAPI backend in `backend/`, which ingests the ZIP and produces every case fact. A disposable mock adapter with fictional fixtures remains available; it does not read ZIP contents or perform analysis.

## Run locally

Requires Bun 1.4.4. Run the app from the repository root:

```sh
make frontend-install
make backend-install    # once; Python 3.11+
make dev                # API on :8000 and Vite on :5173
make backend-seed-kestrel   # in another terminal: upload and analyse the fictional Kestrel case
```

Open [localhost:5173](http://localhost:5173), choose **Open projects**, then open Kestrel or upload a ZIP with **New project**. Vite proxies `/api` to the backend (`MAPLETRACE_API_URL`, default `http://127.0.0.1:8000`). Cases persist in `backend/data/`.

To use the mock adapter instead, start Vite with `VITE_API_BASE_URL=mock`; see `.env.example`. Production builds use the mock unless `VITE_API_BASE_URL` is set at build time.

The welcome page is at `/`, and an opened case uses `/cases/:caseId`. Browser back and forward and direct case links are supported. The production nginx configuration falls back to the app for these routes.

Each case has Mind map, Raw evidence, Generalized files, Insights, and Chat sections in a collapsible left toolbar. The icon rail expands to show labels and project actions; Escape collapses it while focused inside the toolbar. The latter four sections use `/evidence`, `/files`, `/insights`, and `/chat` under the case URL. Source links from the map and insights open `/evidence/:sourceId`; switching sections and expanding the toolbar preserve the map viewport and review context. Raw evidence lists cited source records with their excerpts and links to download the read-only original file. Generalized files means normalized ingestion records, paged from the backend and filterable by evidence file. With the mock adapter, excerpts are fictional, originals are unavailable and no normalized records exist.

Without Make, run `bun install --frozen-lockfile` and `bun run --bun dev` from `frontend/`.

## Run with Docker

Requires Docker with Compose and a running Docker daemon. The container serves the production build, which uses the mock adapter; the backend is not containerised. Stop any local Vite server using port 5173 first. From the repository root, build and start the production demo container:

```sh
docker compose up --build -d
```

Open [localhost:5173](http://localhost:5173). If using Docker to serve updated source changes, rebuild and restart with `docker compose up --build -d`. Docker is optional and is not needed for routine frontend development. Stop the container with:

```sh
docker compose down
```

Commit `bun.lock` when changing dependencies. Use `bun add <package>` or `bun add -d <package>` inside `frontend/`. The Docker build uses the same pinned Bun version and frozen lockfile.

## Useful commands

Run these from the repository root:

```sh
make frontend-test       # Run contract tests
make frontend-build      # Type-check and build into dist/
make frontend-preview    # Serve dist/ locally (run frontend-build first)
make frontend-format     # Format source files
```

## Backend integration

- `src/api/types.ts`: presentation contract. The backend is authoritative; when they disagree, change these types. See `backend/README.md` for the API.
- `src/api/http.ts`: live adapter for `backend/mapletrace_api` (upload, status, cases, files, records, audit chain, original file URLs). Backend errors arrive as `{"error": {"code", "message"}}` and surface as `ApiError`.
- `src/api/client.ts`: selects the live or mock adapter from `VITE_API_BASE_URL`, and holds the mock.
- `src/api/fixtures.ts`: disposable fictional case for the mock adapter only.
- `src/api/files.ts`: source index built from citations already in `CaseData`.
- `src/api/chat.ts`: optional chat adapter; [CHAT.md](CHAT.md) documents the handoff. The backend has no chat endpoint yet, so chat shows its unavailable state.

The UI polls job status through TanStack Query. Citations use source IDs (`EV-071:seq=40162`); original paths, excerpts, timestamps and file SHA-256 hashes live in source records. [INTEGRATION.md](INTEGRATION.md) records what the integration covers and what remains.
