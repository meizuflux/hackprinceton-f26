# MapleTrace frontend

React + Vite evidence board for source-linked case review. The UI loads case data through an API adapter. In development it talks to the FastAPI backend in `backend/`, which ingests the ZIP and produces every case fact. A disposable mock adapter with fictional fixtures remains available; it does not read ZIP contents or perform analysis.

## Run locally

Requires Bun 1.4.4. Run the app from the repository root:

```sh
make frontend-install
make backend-install    # once; uv creates backend/.venv (Python 3.12)
make dev                # API on :8000 and Vite on :5173
```

Open [localhost:5173](http://localhost:5173). The demo buttons open the prepared Kestrel case instantly from a committed snapshot, including its cached LLM results. **New project** uploads a ZIP for real analysis; uploading `cases/kestrel/kestrel_case_upload.zip` replays the recorded LLM responses instead of calling the API. Vite proxies `/api` to the backend (`MAPLETRACE_API_URL`, default `http://127.0.0.1:8000`). Cases persist in `backend/data/`.

To use the mock adapter instead, start Vite with `VITE_API_BASE_URL=mock`; see `.env.example`. Production builds use the mock unless `VITE_API_BASE_URL` is set at build time.

The welcome page is at `/`, and an opened case uses `/cases/:caseId`. Browser back and forward and direct case links are supported. The production nginx configuration falls back to the app for these routes.

Each case has Mind map, Raw evidence, Generalized files, Insights, and Chat sections in a collapsible left toolbar. The icon rail expands to show labels and project actions; Escape collapses it while focused inside the toolbar. The latter four sections use `/evidence`, `/files`, `/insights`, and `/chat` under the case URL. Source links from the map and insights open `/evidence/:sourceId`; switching sections and expanding the toolbar preserve the map viewport and review context. Raw evidence lists cited source records with their excerpts and links to download the read-only original file. Generalized files means normalized ingestion records, paged from the backend and filterable by evidence file. With the mock adapter, excerpts are fictional, originals are unavailable and no normalized records exist.

Without Make, run `bun install --frozen-lockfile` and `bun run --bun dev` from `frontend/`.

## Run with Docker

Docker is optional and is not needed for routine development. It requires Docker with Compose and a running daemon. The root `compose.yaml` runs two services:

- `backend`: the FastAPI API (`backend/Dockerfile`, Python 3.12, dependencies installed with uv), run as a non-root user on port 8000 inside the Compose network only. Its build context is the repository root; the root `.dockerignore` admits only the backend code, `backend/demo/`, `backend/llm_cache/` and `cases/kestrel/kestrel_case_upload.zip`.
- `frontend`: the production build with `VITE_API_BASE_URL=/api`, served by nginx at `127.0.0.1:5173`. nginx proxies `/api/` to the backend and strips the prefix as Vite's dev proxy does, accepts 100 MB uploads, and allows 600-second timeouts for analysis and chat. It starts after the backend reports healthy.

Stop any local Vite server or `make dev` on port 5173 first. From the repository root:

```sh
export ANTHROPIC_API_KEY=...   # optional; see below
make docker-up                 # docker compose up --build -d
make docker-logs               # follow logs; Ctrl-C to stop following
make docker-down               # stop; case data is kept
```

Open [localhost:5173](http://localhost:5173). Rebuild after source changes with `make docker-up`.

**Demo in Docker.** The demo buttons call `POST /demo`, which installs the committed Kestrel snapshot (`backend/demo/kestrel.tar.gz`) and restores its upload ZIP from the image after checking its hash. This needs no API key. Uploading `cases/kestrel/kestrel_case_upload.zip` through **New project** replays the recorded LLM responses in `backend/llm_cache/`, also without a key. Only LLM analysis of other archives needs `ANTHROPIC_API_KEY`.

**Case data** lives in the named volume `mapletrace-data`, mounted at `/data` (`MAPLETRACE_DATA`). It survives `make docker-down` and rebuilds. Remove it with `docker compose down -v`.

**Environment** (read by Compose from your shell or a git-ignored root `.env`; never commit keys):

| Variable | Default | Purpose |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | empty | Optional. Needed only for new, unrecorded LLM analyses. |
| `MAPLETRACE_LLM_MODEL` | `claude-sonnet-5-5` | Model for the LLM layer. |

`MAPLETRACE_DATA=/data`, `MAPLETRACE_MAX_UPLOAD_MB=100` and `MAPLETRACE_CORS` are set in `compose.yaml`. If you raise the upload limit, also raise `client_max_body_size` in `nginx.conf`.

**Mock-only image.** To serve the fixture adapter without a backend, build the frontend alone: `docker build --build-arg VITE_API_BASE_URL=mock -t mapletrace-mock frontend`, then `docker run --rm -p 127.0.0.1:5173:80 mapletrace-mock`.

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
