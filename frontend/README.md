# Compstat frontend

React + Vite evidence board. All case data and ingestion responses are temporary mocks; no backend is required. Uploaded ZIP contents are not read or sent anywhere.

## Run locally

Requires Bun 1.4.4. Run the app from the repository root:

```sh
make frontend-install
make frontend-dev
```

Open [localhost:5173](http://localhost:5173) and click **Explore demo case**. You can also choose a ZIP to try the simulated ingestion flow.

Without Make, run `bun install --frozen-lockfile` and `bun run --bun dev` from `frontend/`.

## Run with Docker

Requires Docker with Compose and a running Docker daemon. Stop any local Vite server using port 5173 first. From the repository root, build and start the production demo container:

```sh
docker compose up --build -d
```

Open [localhost:5173](http://localhost:5173). After source changes, rebuild and restart with `docker compose up --build -d`. Stop the container with:

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

## Connect a backend later

- `src/api/types.ts`: shared API contracts.
- `src/api/client.ts`: replaceable mock adapter (`createUpload`, `getStatus`, `getCase`).
- `src/api/fixtures.ts`: disposable fictional case data.

The UI polls job status through TanStack Query. Replace the adapter with HTTP calls when the Python backend is ready. Citations use source IDs; original paths, excerpts, timestamps, and placeholder hashes live in source records. Nothing is persisted between sessions.
