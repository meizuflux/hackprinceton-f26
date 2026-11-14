# Compstat frontend

- This is a hackathon prototype. Prioritize a clear, reliable three-minute demo.
- Build with Vite, React, and TypeScript. Use React Flow for the inspectable pin-up board.
- Keep backend contracts and temporary synthetic fixtures separate from presentation. All current case data is fictional and disposable.
- Every graph relationship, gap, and insight must expose original source citations. Distinguish observed evidence from inference; a gap is not proof.
- Support ZIP upload, ingestion progress, the evidence board, ranked gaps, suggested evidence, source inspection, and an audit trail.
- Keep the board usable on laptop screens with pan, zoom, fit view, and a minimap.
- Record durable implementation decisions here as work proceeds.
- Commit incremental changes with `git commit -S -m "message"`.
- Do not imply that mock ingestion parses ZIP files or performs real analysis. Swap the API adapter when the Python backend is available.

## Implementation decisions

- The single canonical product spec and Impeccable product context live in root `SPEC.md`; do not create a second `PRODUCT.md`; app-specific settings live in `frontend/.impeccable/`. Future landing pages use the confirmed code-first workflow. Keep the root skill installation and `AGENTS.md` at the repository root.
- API seam: `CaseApi` in `frontend/src/api/types.ts`; `frontend/src/api/client.ts` owns mock jobs. UI loads the case through TanStack Query and never imports fixtures directly.
- Mock uploads never read ZIP contents. Keep this limitation visible beside upload controls. Fixture hashes and confidence scores are illustrative, not computed.
- Luna subagents are requested for delegated work. Fetch remote refs at task start and before coordinating or integrating shared work; do not run `git fetch` continuously or poll on a timer. Make one signed commit per feature.
- Board uses React Flow custom pinned cards on a cork surface inside a dark workspace. Relationships and ranked analysis open the shared source inspector.
- Frontend design preserves the dark/cork identity. The source inspector occupies the review dock, with source excerpts first; below 900px it stacks under the board. Keep search available at every width. The list view exposes evidence and relationships through standard buttons, and illustrative scores are labeled beside their values. Design tokens live in `frontend/DESIGN.md`; baseline findings live in `frontend/EVALUATION.md`.
- The case board is the primary canvas. Analysis, source inspection, and audit share a collapsible review dock; opening it must preserve the graph viewport and the analysis context. The welcome page uses `/` and case workspaces use `/cases/:caseId`; validate case IDs against the API result, and keep browser history and direct-load fallback working.
- Validate API fixture links and mock upload state transitions from `frontend/` with `bun run --bun test`; use `bun run --bun build` for TypeScript and the production bundle.
- Browser-verified demo path: synthetic ZIP selection → staged mock progress → board; gap and insight inspection; original source expansion; edge inspection; audit trail. Upload modal traps keyboard focus and supports Escape when idle/ready; inspector supports Escape.
- Run `bun run --bun format` from `frontend/` after changes. No real source files or computed hashes are bundled; source excerpts live only in disposable fixtures.

- Onboarding lives in `frontend/src/onboarding/` with isolated styles: `/` is a standalone landing page, `/projects` is the session project manager, and `/projects/new` opens project naming plus ZIP selection or direct fictional demo entry. The mock adapter exposes one case; the manager keeps one entry for it in React session state. Carry a session project name into the matching case workspace title; direct case routes fall back to the API title. Contact sales prepares a copyable enquiry and does not send messages.
- Keep prototype labeling focused on upload behavior and explicit fictional case entry points; avoid repeating “demo” in the case workspace chrome. Clearly disclose that ZIP contents are not read and results use fictional data.

## Repository layout

- Keep `AGENTS.md` at the repository root. All frontend application files, dependencies, build outputs, and frontend documentation live in `frontend/`.
- Run Bun commands from `frontend/`. Root-level orchestration may reference that directory.
- The root `Makefile` provides `frontend-install`, `frontend-dev`, `frontend-build`, `frontend-test`, `frontend-preview`, and `frontend-format`. Run Make from the repository root; recipes enter `frontend/` automatically. Do not add a nested frontend Makefile. Docker and the root `compose.yaml` are optional for server deployment; do not start Docker, run Compose, or rebuild container images for routine frontend work unless the user explicitly requests it.
- Use Bun 1.4.4 for frontend dependencies and script execution. Commit `frontend/bun.lock`; install with `bun install --frozen-lockfile`. Use `bun run --bun test` to run the Vitest suite (not the separate `bun test` runner). Docker uses the same pinned Bun build image.

## Specification change approval

- Before any future modification to root `SPEC.md`, always present the proposed changes and ask both the user and team members for approval. Wait for their explicit approval before editing; silence is not approval.
- If team members cannot be reached through an explicitly authorized channel, ask the user to obtain their approval. Do not contact anyone without authorization or assume team consent.
- This rule governs changes to `SPEC.md`; routine implementation work and other documentation can proceed within the user's authorized scope.
