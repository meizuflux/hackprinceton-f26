# Mapletrace frontend

React + Vite evidence board for source-linked case review. The UI loads case data through a replaceable API adapter. The current adapter is a mock: it does not read ZIP contents or perform analysis.

## Run locally

Requires Bun 1.4.4. Run the app from the repository root:

```sh
make frontend-install
make frontend-dev
```

Open [localhost:5173](http://localhost:5173), choose **Open projects**, then open the fictional case or select a ZIP to preview the workspace. ZIP selection does not read the archive.

The welcome page is at `/`, and an opened case uses `/cases/:caseId`. Browser back and forward and direct case links are supported. The production nginx configuration falls back to the app for these routes.

Each case has Mind map, Raw evidence, Generalized files, Insights, and Chat sections in a collapsible left toolbar. The icon rail expands to show labels and project actions; Escape collapses it while focused inside the toolbar. The latter four sections use `/evidence`, `/files`, `/insights`, and `/chat` under the case URL. Source links from the map and insights open `/evidence/:sourceId`; switching sections and expanding the toolbar preserve the map viewport and review context. Raw evidence currently shows fictional excerpts, with original files explicitly unavailable. Generalized files means normalized ingestion records; this view stays empty until authoritative backend records are supplied.

Without Make, run `bun install --frozen-lockfile` and `bun run --bun dev` from `frontend/`.

## Run with Docker

Requires Docker with Compose and a running Docker daemon. Stop any local Vite server using port 5173 first. From the repository root, build and start the production demo container:

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

- `src/api/types.ts`: shared API contracts.
- `src/api/client.ts`: API adapter (`createUpload`, `getStatus`, `getCase`).
- `src/api/fixtures.ts`: example case data for the frontend workspace.
- `src/api/files.ts`: source index and normalized record presentation contract; never derives normalized facts from fixtures. Supply optional `CaseData.normalizedRecords` through the future ingestion adapter. Each record needs an evidence ID and original locator; optional `sourceId` links only to an existing `CaseData.sources` entry. Records without citations are withheld from the viewer.
- `src/api/chat.ts`: optional chat adapter; [CHAT.md](CHAT.md) documents the Deep Agents backend handoff. This pass implements the chat UI and HTTP contract, without a backend or model calls.

The UI polls job status through TanStack Query. Connect the adapter to the Python backend as its endpoints become available. Citations use source IDs; original paths, excerpts, timestamps, and placeholder hashes live in source records.
