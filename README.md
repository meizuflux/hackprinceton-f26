# MapleTrace

MapleTrace is a hackathon prototype of an inspectable evidence board. A case ZIP goes through a Python backend that ingests every file into a traceable database, analyses it, and serves a board of cited evidence, relationships, ranked gaps, suggested next evidence, insights, a case chat and an audit trail. All case data is fictional.

- **`frontend/`:** React + Vite board. It talks to the backend through a live adapter, with a disposable mock adapter as a fallback.
- **`backend/`:** ingestion (`mapletrace_ingest`), reasoning with traditional ML, rules and an optional LLM investigator (`mapletrace_reason`), and the FastAPI service (`mapletrace_api`). The backend is authoritative for every case fact.
- **`generator/`:** deterministically builds the synthetic Kestrel case in `cases/kestrel/`.

## Quickstart

Requires Bun 1.4.4, [uv](https://docs.astral.sh/uv/) and Python 3.12. From the repository root:

```sh
make frontend-install
make backend-install     # uv sync: backend/.venv from backend/uv.lock
make dev                 # API on 127.0.0.1:8000 and Vite on 127.0.0.1:5173
```

Open [localhost:5173](http://localhost:5173) and press the demo button. It opens the prepared Kestrel case instantly from a committed snapshot (`POST /demo`), including its recorded LLM results, with no API key. **New project** uploads a ZIP for real analysis; uploading `cases/kestrel/kestrel_case_upload.zip` replays the recorded LLM responses. `make backend-seed-kestrel` uploads Kestrel from the command line. Set `ANTHROPIC_API_KEY` only for new LLM analyses and free-typed chat questions.

`make help` lists every target. The main checks:

```sh
make frontend-test       # Vitest suite
make frontend-build      # type-check and build into frontend/dist/
make backend-test        # includes a full Kestrel ingestion
make data-verify         # rebuild the case and check every file hash
```

## Docker

Optional, and not needed for development. Requires Docker with Compose and a running daemon. Stop anything else on port 5173 first.

```sh
export ANTHROPIC_API_KEY=...   # optional
make docker-up                 # docker compose up --build -d
make docker-logs               # follow logs
make docker-down               # stop; case data is kept
```

Open [localhost:5173](http://localhost:5173). `compose.yaml` runs two services:

- **`backend`:** FastAPI on port 8000 inside the Compose network only, built from the repository root with `backend/Dockerfile` and run as a non-root user. The root `.dockerignore` is an allowlist (backend code, `backend/demo/`, `backend/llm_cache/` and the Kestrel upload ZIP).
- **`frontend`:** the production build with `VITE_API_BASE_URL=/api`, served by nginx on `127.0.0.1:5173`. nginx proxies `/api/` to the backend, stripping the prefix as Vite does, accepts 100 MB uploads and allows 600-second timeouts. It starts once the backend is healthy.

The demo button and the Kestrel upload work without a key. Case data lives in the `mapletrace-data` volume at `/data`; it survives `make docker-down` and is removed by `docker compose down -v`.

Compose reads `ANTHROPIC_API_KEY` (optional) and `MAPLETRACE_LLM_MODEL` (default `claude-sonnet-5-5`) from your shell or a git-ignored root `.env`; never commit keys. `MAPLETRACE_DATA`, `MAPLETRACE_MAX_UPLOAD_MB=100` and `MAPLETRACE_CORS` are set in `compose.yaml`. If you raise the upload limit, also raise `client_max_body_size` in `frontend/nginx.conf`.

For a mock-only frontend without a backend: `docker build --build-arg VITE_API_BASE_URL=mock -t mapletrace-mock frontend`, then `docker run --rm -p 127.0.0.1:5173:80 mapletrace-mock`.

## Docs

| File | Purpose |
| --- | --- |
| [AGENTS.md](AGENTS.md) | Rules and durable decisions for contributors and agents |
| [SPEC.md](SPEC.md) | Product specification (changes need user and team approval) |
| [frontend/README.md](frontend/README.md) | Frontend development, adapters, routes and structure |
| [frontend/DESIGN.md](frontend/DESIGN.md) | Design system: brand, tokens, board colours and components |
| [frontend/CHAT.md](frontend/CHAT.md) | Case chat HTTP contract |
| [backend/README.md](backend/README.md) | Ingestion, reasoning pipeline, LLM layer and cache, HTTP API |
| [backend/LLM_COSTS.md](backend/LLM_COSTS.md) | Measured cost of an LLM analysis and estimated chat cost |
| [generator/README.md](generator/README.md) | Case generator and the rules for changing it |
| [generator/EVALUATION.md](generator/EVALUATION.md) | Known consistency issues in the generated case |
| [cases/kestrel/README.md](cases/kestrel/README.md) | The Kestrel case contents (generated) |
