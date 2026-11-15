# MapleTrace agent instructions

Rules and durable decisions for agents working in this repository. How-to material lives in the READMEs listed in [README.md](README.md#docs); do not repeat it here.

## Ground rules

- This is a hackathon prototype. Prioritize a clear, reliable three-minute demo.
- Build the frontend with Vite, React, TypeScript and TanStack Query, and the board with React Flow. Keep backend contracts and disposable fixtures separate from presentation. All case data is fictional.
- Every graph relationship, gap and insight must expose original source citations. Distinguish observed evidence from inference; a gap is not proof.
- Support ZIP upload, ingestion progress, the evidence board, ranked gaps, suggested evidence, source inspection and an audit trail. Keep the board usable on laptop screens with pan, zoom, fit view and a minimap.
- Commit incremental changes with `git commit -S -m "message"`, one signed commit per feature.
- Luna subagents are requested for delegated work. Fetch remote refs at task start and before coordinating or integrating shared work; do not run `git fetch` continuously or poll on a timer.
- Record durable implementation decisions here as work proceeds, replacing lines they make stale.
- Never imply that the mock adapter parses ZIP files or performs real analysis. Keep prototype labelling to upload behaviour and the explicit fictional-case entry points; avoid repeating "demo" in the case workspace chrome. The frontend bundles no real source files or computed hashes.

## Repository layout and tooling

- Keep `AGENTS.md` and the skill installation at the repository root. Frontend files, dependencies, build output and docs live in `frontend/`; backend code, dependencies and docs live in `backend/`; the case generator lives in `generator/`.
- Run Make from the repository root (`make help` lists every target). Do not add nested Makefiles.
- Frontend: Bun 1.4.4, run from `frontend/`. Commit `frontend/bun.lock`; install with `bun install --frozen-lockfile`. Test with `bun run --bun test` (Vitest, not `bun test`), build with `bun run --bun build`, and run `bun run --bun format` after changes. Docker uses the same pinned Bun image.
- Backend: Python 3.11+ with `backend/requirements.txt`; `make backend-install` creates `backend/.venv` with uv and Python 3.12. Run `make backend-test` after backend changes.
- Docker and `compose.yaml` are optional. Do not start Docker, run Compose or rebuild images for routine work unless the user asks.

## Backend authority and evidence

- **The backend is authoritative.** Case facts (records, times, entities, citations, hashes) come only from the backend. `case.db` (written by `backend/mapletrace_ingest`), its `ingest_report.json`, and the analysis outputs are the source of truth. `frontend/src/api/types.ts` is a presentation contract: when it and the backend disagree, change the frontend types or adapter, never the backend data. The frontend must not compute, infer or hard-code case facts.
- Ingestion never alters evidence. Working copies are read-only, every file is SHA-256 hashed before parsing, `MANIFEST.csv` hashes are checked, and every step is written to the hash-chained `audit_log`. `python -m mapletrace_ingest verify <run>` must pass. `backend/tests/test_formats.py` re-ingests the Kestrel ZIP and requires every file to parse and every manifest hash to match.
- Every record carries `locator_json` (row, line, `doc_line`, page, JSON path, ...); its file carries `external_id` (the manifest evidence ID). Citations are `{evidence_id, locator}`, written as `EV-071 seq=40162` or source ID `EV-071:seq=40162`. Uncited facts must not reach the frontend. Every citation ID must identify exactly one record: `unique_labels` in `backend/mapletrace_reason/store.py` falls back to the record's position when an ID-like attribute is shared within a file.
- Timestamps are stored in UTC with an uncertainty window and a flag for every assumption. Each file's `time_basis` in `MANIFEST.csv` decides UTC versus local wall time. Human-reported times are `reliability = 'asserted'`, never machine records.
- Identity merges happen only on explicit evidence (contacts, email display names, unambiguous name forms) and are recorded in `entity_links` with a rule and confidence. Fuzzy linkage belongs in the ML stage.
- Media (`mapletrace_reason/media.py`, `vision.py`, contract `backend/MEDIA.md`): every photo and video is an observed board card; links come only from cited rules. Image descriptions (`--llm`) are inferred, live in the separate `llm_cache/vision-<sha>.jsonl`, are attached to media cards only and never reach claims, gaps, insights or the investigator (`backend/tests/test_vision.py`).
- Reasoning (`backend/mapletrace_reason`) never writes to `case.db`. Each run writes `analysis/vN/` with `board.json`, `analysis.json`, `graph.json` and `analysis.db`, whose audit chain continues from the ingestion head. Deterministic stages (traditional ML and rules) must work without an API key.
- Traditional ML (`mapletrace_reason/ml.py`) writes cited `signal` items (`ML-xx`) only. Signals go to the board and the agent's `list_ml_signals` tool and are never fed to later stages, so they cannot change findings, explanations or gaps (`backend/tests/test_ml.py` checks this). Models use fixed seeds, learn only from the case's own evidence, and never use protected attributes or the answer key.
- The run trace (`ingest/vN/trace.jsonl`, `mapletrace_ingest/trace.py`, contract in `backend/TRACE.md`) is presentation telemetry: appended while the job runs, never part of the audit chain or the evidence. Its `tMs` is a replay clock: a model response replayed from the cache advances it by its recorded `latency_ms`, or by the estimate in `llm_cache.py` (flagged `estimated`) for older entries. `analysis_mode=live` uploads never read or write the committed cache (case-local `llm_cache/` only). Every board node and edge carries `origin`, `stage` and `evidenceIds`.
- Contradictions list several possible reasons and never conclude that someone lied. Explanations return "insufficient evidence" rather than forcing a verdict. Gaps are typed missing, failed_extraction, conflicting or uncertain. Corroboration counts independent origins, not records.
- Investigator overrides go to `overrides.jsonl` and are applied on every run. Never delete them or the machine result they annotate. Items match across versions by their stable `key`.
- API errors are always `{"error": {"code", "message"}}`.
- Backend run outputs (`backend/runs/`, `backend/data/`) and generated sample ZIPs are not committed.

## LLM layer and cache

- The LLM layer (`--llm`, deepagents + Anthropic) only adds claims and agent insights, and both must cite resolvable record IDs. The default model is `claude-sonnet-5-5`.
- Never put upload-form values (such as the case name) into model prompts: replay keys must match across uploads of the same archive.
- Recorded responses are committed on purpose: `backend/llm_cache/<archive sha256>.jsonl` (analysis), `backend/llm_cache/chat-<archive sha256>.jsonl` (chat), and `backend/demo/kestrel.tar.gz` (the finished Kestrel case served by `POST /demo`). After changing anything the model sees, rebuild with `make backend-llm-record` (billed), `make backend-demo-snapshot` (free) and `make backend-chat-record` (billed).
- Tool names, docstrings (whitespace included) and outputs in `llm.read_tools` are part of the cache keys of both the investigator and chat caches. Editing them invalidates both.

## Case data and generator

- Generated data under `cases/` is the authoritative data for backend work. Never hand-edit it: change `generator/`, run `make data-generate`, and confirm with `make data-verify` (byte-for-byte check against `BUILD_INFO.json`). The generator needs Python 3.12+ and uv; its pins are the PEP 723 block in `generator/generate.py`.
- Frontend fixtures (`frontend/src/api/fixtures.ts`) are disposable mocks. Never use them as a backend data source or reconcile backend data to them.
- `cases/kestrel/evidence/` and `kestrel_case_upload.zip` are the pipeline inputs. The repository holds no answer key. `make data-truth` writes one to the git-ignored `.truth/kestrel/` for scoring only. Never commit it, and never give it or anything under `generator/` (which encodes the solution) to the model.
- All people, companies, numbers (555-01xx), plates and domains (`.example`) are fictional. Do not add real people or organizations to case data.
- Protected attributes (for example `id_issuing_country`, nationality) must never be model features or be returned by the API. The case includes a deliberate bias trap (RH-03).

## Frontend decisions

### Adapters and data

- API seam: `CaseApi` in `frontend/src/api/types.ts`. `http.ts` is the live adapter for `backend/mapletrace_api`; `client.ts` selects it from `VITE_API_BASE_URL` (development defaults to `/api`; `mock`, or an unset value outside development, selects the mock) and owns the mock jobs. UI loads cases by ID through TanStack Query and never imports fixtures directly.
- Mock-only disclosures (ZIP not read, fictional excerpts, illustrative scores and hashes) render only when `api.mode === "mock"`, and the ZIP limitation stays visible beside upload controls. The mock upload validates a `.zip` extension and a nonempty file only, enforces no size cap, and never reads contents.
- Observed versus inferred comes from the API's `certainty` on nodes and edges; claims stay claims. Never infer certainty from edge type names. Arrowheads require API `directed: true`; never reverse an edge from card positions.
- Backend node positions are column placeholders. Live cases use the presentation-only layout `layoutCaseGraph` in `frontend/src/components/board-layout.ts`; fixture positions are hand-placed. Layout code never creates case facts.
- Gap focus uses the backend's `gaps[].nodeIds`; shared citations are only a fixture fallback.
- Backend scores are computed ranks. Show insight `confidence` as a label and ML scores as "Model score 0.xx", never as percentages. Times render in the case `timezone` via `formatCaseTime`.
- Competing explanations show the backend verdict, which may be undecided; never present a hypothesis as a finding.

### Run replay (frontend/src/replay)

- The import and the demo open the empty map and play the run from `GET /cases/{id}/trace` (`useReplay`, default 10x, 1x/10x/50x, pause, skip). `reveal.ts` only decides when an existing board item appears (record nodes at their first parsed `evidenceIds` file, others at their `stage_finished` or `insight_recorded` key, edges when both ends show, everything at `run_finished`); items without provenance and the mock (no trace) show at once. Layout always comes from the full case, so revealed cards never move.
- The start-replay flag is module state (`replay/intent.ts`), not a URL parameter: reloads and later visits show the finished case with a "Replay run" button. A case opened while processing shows the HUD on an empty map, polls the trace every 700 ms and swaps in the board when `GET /cases/{id}` stops returning `not_ready`.
- Replay pacing is honest slow-down only: ingest, rules and ML each get a minimum on-screen time (4 s, 2 s, 2.5 s; `phaseMinWallMs` in `trace.ts`), longer phases use the chosen speed, and the HUD states the effective speed while a phase is slowed. The shown replay clock is always the real `tMs`. The HUD counter is "Agent insights" (`insight_recorded` only); the top bar counts all insights. Bursts of events at one instant (the agent's batched tool calls) are spread across up to 80% of the gap before the next event (`displayTimes`), and the feed folds consecutive calls of one tool into a counted row; feed times stay the real `tMs`. A replay frames the finished layout once at the start instead of refitting as cards appear.
- The HUD labels replay versus live and shows the backend `timing` ("estimated" is never presented as recorded); it collapses to a "Run summary" chip when a watched run ends. Uploads (live adapter) ask for replay or, when `/health` reports `llmLive`, billed live analysis in `UploadConfirm` before sending `analysis_mode`.

### Routes and workspace

- `/` is the landing page, `/projects` the project manager and `/projects/new` project naming plus ZIP selection (onboarding lives in `frontend/src/onboarding/`). Demo buttons call `openDemo()` (`POST /demo` with the live adapter). Carry a session project name into the matching case title; direct case routes fall back to the API title. The fictional-case entry stays on `/projects` until that case is in the session; do not repeat it in the upload modal. Contact sales is not part of the prototype: no enquiry form or fake destination.
- A case is `/cases/:caseId` (the mind map), with `/evidence`, `/evidence/:sourceId`, `/files`, `/insights/{questions,evidence,inferences}` and `/chat`. Bare `/insights` shows Questions; build links with `insightsPath()`. Validate case IDs against the API and keep browser history and direct loads working. Keep the board mounted across sections to preserve its viewport and review context.
- Left toolbar order: Mind map, Insights, Raw evidence, Generalized files, Chat. It floats below the top bar (measured clearance `--topbar-clearance-y`), is 48px collapsed and 192px expanded with 34px rows and 16px icons, overlays the canvas when expanded, keeps accessible names and tooltips on collapsed icons, collapses on Escape while focused, and collapses after a selection on small screens.
- The top bar is a flat full-width header. On the mind map it holds Search, List/Board, Audit trail, and a "Case analysis" group with one entry per kind with its count (Gaps, Insights, Next evidence). Each entry opens the review dock, titled "Analysis", on its own tab. There is no single "Review gaps" button. Section pages (Insights, Raw evidence, Generalized files, Chat) show only the case title, the subtitle and Audit trail (which returns to the mind map with the audit panel open); the left toolbar handles navigation. Section headings are sans h2s under the single case-title h1. Keep search available on the mind map at every width.
- Analysis, source inspection and audit share a collapsible review dock that preserves the graph viewport; source excerpts come first, and below 900px the dock stacks under the board. Opening analysis items pans and zooms the map to the relevant cluster (accounting for the dock), highlighting targets in amber and dimming the rest. On desktop the open dock runs to the bottom inset; the minimap, zoom controls and Ask widget move to its left (`--dock-offset`), and the legend collapses until the dock closes. At 900px and below the stacked dock clears the floating toolbar.
- Keyboard on the board goes through each card's inspect button and each thread's label button; React Flow node and edge focus is off. Focus outlines use `--focus-ring`.
- The frontend may format backend text for display (`formatCaseSubtitle`, audit payload fields) but never changes values.
- The list view exposes evidence and relationships through standard buttons. The upload modal traps focus and supports Escape when idle or ready; the inspector supports Escape.

### Board

- Evidence cards: Excalifont titles, summaries, question links and thread annotations, with upright sans-serif metadata, a gently uneven paper silhouette, and a centered pushpin 6px inside the top edge. Sizes are role-tailored in `board-layout.ts` (default 248 × 224px) with 40px clearance after placement and drops. Inspection is an arrow-only button with an accessible name; the card shows a pointer cursor; omit inset frames and footer dividers.
- Card colour comes only from API type and certainty, via the inks in `board-colors.ts`: person purple, device blue, event teal, location olive, statement grey. Each thread family shares the hue of its card type. Red means contradiction only.
- Media cards (nodes with `media`, see `backend/MEDIA.md`) keep the event ink and pushpin and put a 4:3 photo or 16:9 clip frame (`<img>`/`<video preload="metadata" muted>` at a mid-duration `#t=` poster, never autoplay, never draggable) under the type row, with a Photo/CCTV chip and a duration badge; sizes live in `board-layout.ts`. The source panel shows the photo or playable clip first, then metadata, then `media.vision` apart as "Description (LLM, inferred)" with the LLM stamp; the replay withholds `media.vision` until `media_vision` finishes (`withheldVision`). The legend lists "Photo / CCTV" when present.
- Inferred cards are dashed with an "Inferred" chip; cards with an open question get an amber outline and flag. Observed threads are solid, inferences dashed `8 7`, claims dashed `3 6`. Every thread label is a source-inspection button.
- Origin (`origin` on nodes, edges and insights) never changes hue. `ml`, `agent` and `llm` items get a graphite (`ORIGIN_INK`, neutral, 4.5:1 tested) stamp chip with icon plus word (ML scatter, Agent bot, LLM sparkles), a faint textured strip on the card (dotted, hatched, ruled), the same icon on thread labels, a minimap tab, an "Origin" legend section listing only origins present, and a "Produced by" line in the inspector. `record` and `rules` stay unmarked; items without `origin` render as before. Inferences tab tags each item by origin.
- Colour always travels with an icon, label or pattern, and every ink keeps 4.5:1 contrast against the paper (`board-colors.test.ts` enforces it).
- A collapsible legend at the bottom left lists only the types present; the minimap mirrors the board colours, direction and selection.
- Minimap: frames the pins only, so it never rescales while panning, with a clipped viewport rectangle. Pressing grabs the rectangle or centres the view there; minimap navigation clamps the view to the pins; arrow keys pan. The zoom readout sits in the zoom controls.
- The "Ask a question" widget is only a small input with suggestion chips, and typing is always allowed: it sits 12px above the minimap (which publishes `--minimap-height`), moves left of an open review dock, and must not cover the minimap, zoom controls or legend. Submitting navigates to the chat tab, which asks the question; the map never shows answers.

### Insights

- Questions: gaps plus the suggestions tied to them. Evidence: contradictions, cited observations, source groups, missing periods and uncertain times. Inferences: insight inferences, competing explanations with the backend verdict, and ML signals as leads; dashed borders.
- Cited observations always stay separate from the inference. One search covers all tabs. `insights-sections.ts` only groups API data; it never creates or scores facts.

### Raw evidence and generalized files

- Raw evidence lists files from `GET /cases/{id}/files` and opens them with `GET /cases/{id}/evidence/{evidenceId}/view`. `/evidence/:sourceId` accepts a citation (`EV-xxx:locator`) or a bare evidence ID.
- Positions come only from each record's `locator_json` on the backend. The cited row, line or sentence is highlighted; records sharing a label are marked more lightly.
- Originals are served inline only for images, video, audio and PDF; everything else is a `nosniff` attachment, sandboxed by CSP.
- "Generalized files" means normalized ingestion records: a table whose citations link to the raw file at that row, filtered by type with `GET /records?recordType=`. Never synthesize normalized records from fixture metadata.
- The mock adapter keeps its cited-source list and "unavailable" states.

### Chat

- Implemented. Contract: [`frontend/CHAT.md`](frontend/CHAT.md); code: `backend/mapletrace_api/chat.py` and `backend/mapletrace_reason/chat.py`. Keys stay server-side and the frontend never simulates replies.
- Chat replies carry `steps` (the tool loop); the chat tab replays them as a paced "thinking", tool-call and typing animation, labelled as replayed or live, collapsed afterwards, and instant for reduced motion or history. Step capture must never change what the model sees (cache keys).
- Suggested questions are deterministic and always answered without thread history, so they replay. Free typing is live and billed and needs a server key; without one the server only replays, and a miss returns `needs_api_key`.

### Brand and visual design

- Tokens and the full design system live in [`frontend/DESIGN.md`](frontend/DESIGN.md); `SPEC.md` is the single product spec and Impeccable product context (do not create a `PRODUCT.md`). App-specific Impeccable settings live in `frontend/.impeccable/`. Impeccable work is frontend-only; if its loader misses `SPEC.md` or the frontend artifacts, read them directly instead of reopening init. Future landing pages use the confirmed code-first workflow.
- The product name is `MapleTrace` in all UI, titles and tokens; snake_case package names (`mapletrace_ingest`, ...) stay as they are.
- The mark is `frontend/public/mapletrace-mark.svg`, rendered inline by `BrandMark.tsx`. Use it on dark surfaces only, never recolour it, and never use stock icons as a stand-in logo.
- Blue (`--brand-*` in `src/styles/base.css`) means interaction, selection and focus; amber means open questions; status greens and reds stay separate. `--green` is a legacy alias of the brand blue; migrate away from it.
- Glass (`--glass-fill`, `--glass-edge`, blur) is for chrome only, never for reading surfaces, cards or the paper canvas.
- Dark workspace chrome surrounds a faint paper canvas. Non-board sections render in framed floating panels with 16px clearance. Corner radius is for structural floating containers (toolbar, panels, dock, cards), not icons, chips or internal boundaries.

## Docker

- The backend image is built from the repo root and mirrors the repo layout under `/app`. The root `.dockerignore` is an allowlist: add any new runtime file to it.
- Data lives in the `mapletrace-data` volume at `/data`; the image runs as a non-root user.
- The frontend image is built with `VITE_API_BASE_URL=/api` (`mock` is a build arg). nginx strips `/api` the way Vite does, and its `client_max_body_size 100m` must follow `MAPLETRACE_MAX_UPLOAD_MB`.
- Only the frontend is published, on `127.0.0.1:5173`. `ANTHROPIC_API_KEY` is optional.

## Specification change approval

- Before any modification to root `SPEC.md`, present the proposed changes and ask both the user and team members for approval. Wait for explicit approval; silence is not approval.
- If team members cannot be reached through an explicitly authorized channel, ask the user to obtain their approval. Do not contact anyone without authorization or assume team consent.
- This rule governs `SPEC.md` only; routine implementation and other documentation proceed within the user's authorized scope.
