# Mapletrace

<!-- impeccable:product-schema 1 -->

> **Change control:** Before any future modification to this file, ask the user and team, summarize the proposed changes, and wait for explicit approval. Silence, partial responses, or one person's assumed consent do not count as approval. Agents without team messaging access must ask the user to obtain team approval; agents must never contact people without explicit authorization to message them. This rule applies to `SPEC.md` only; routine implementation and other documentation work follows the project's normal instructions.

## Platform

Web.

## Users

Mapletrace serves people reviewing evidence across domains, including insurance fraud investigators, crime scene investigators, detectives, and lawyers. It is not tied to one profession or case type. The immediate audience is hackathon judges watching a three-minute demonstration. The prototype must work reliably and look appealing.

## Product Purpose

Help reviewers explore case evidence, inspect relationships, identify gaps, and decide what evidence to seek next while keeping the original sources accessible.

Demo success means a clear, reliable path from the landing page's single demo action through the replayed analysis run of the fictional Kestrel case to an inspectable evidence board, ranked gaps, suggested evidence, source inspection, and an audit trail. ZIP uploads are switched off for the HackPrinceton demo: upload entries stay visible but disabled, with the reason beside them.

## Operating Context

- This is a hackathon prototype using fictional, disposable case data.
- The main workspace is an interactive evidence board intended to remain usable on laptop screens, with pan, zoom, fit view, and a minimap.
- Reviewers can inspect entities, relationships, gaps, insights, suggestions, and source excerpts within the same workspace.
- The current session is temporary; case changes are not persisted between sessions.

## Capabilities and Constraints

- Use Vite, React, TypeScript, React Flow, TanStack Query, and Bun 1.4.4 for dependencies and scripts.
- Keep API contracts and synthetic fixtures separate from presentation. `frontend/src/api/types.ts` defines `CaseApi`; `frontend/src/api/client.ts` owns the replaceable mock adapter. UI data loads through TanStack Query.
- Support ZIP selection and simulated ingestion progress. The current adapter does not read or upload ZIP contents, parse files, or perform real analysis. Make this limitation visible beside upload controls.
- Every graph relationship, gap, and insight must expose original source citations. Preserve source inspection for suggested evidence and audit records as well.
- Distinguish observed evidence from inference. A gap is not proof.
- Fixture hashes and confidence scores are illustrative, not computed. Bundled source excerpts are fictional; no real source files are included.
- Replace the mock API adapter when the Python backend becomes available.
- Professional production workflows, real ingestion behavior, persistence, and deployment beyond the prototype remain undecided.

## Brand Commitments

The product name is Mapletrace. Keep language useful across evidence-review domains rather than assuming every user works in law enforcement. The demo must combine working interactions with an appealing presentation.

## Product Principles

1. Make the three-minute demonstration clear and reliable.
2. Keep every interpretation traceable to its cited sources.
3. Treat missing evidence as uncertainty, never proof.
4. Be explicit about simulation and fictional data.
5. Preserve a useful evidence-review workflow across professional domains.

## Accessibility & Inclusion

Preserve keyboard access to the upload flow and source inspector. The upload modal traps focus and supports Escape when idle or ready; the inspector supports Escape. Keep the evidence board navigable on laptop screens.

## Intended Workflow and Roadmap

The longer-term product direction is to accept a synthetic or CFReDS-style evidence bundle containing examples such as messages, location CSVs, photo metadata, and short statements. A future ingestion service could clean and reduce noise, use traditional machine-learning methods for clustering, anomaly detection, and pattern discovery, then use a reasoning agent to connect evidence and raise questions. The resulting graph could be written to a filesystem and explored as a mind map.

The envisioned map includes people, locations, devices, events, and statements, with temporal, spatial, communication, and claim relationships. Selecting a gap should explain why it matters, which claims it affects, what is missing, and what evidence artifact or concrete query might help. Inferences and recommendations should be clearly distinguished from observations and cited. An audit view should link agent steps and outputs to their citations.

Potential future inputs include DNA or other biological data, timestamped video and photos, messages, location records, written statements, and interviews. Real multimedia or biological-data ingestion is not implemented, and safe handling, supported formats, and workflow requirements remain open.

## Current Prototype

The frontend implements the synthetic demo path: ZIP selection, staged mock progress, evidence board, gap and insight inspection, source expansion, relationship inspection, and audit trail. The board uses custom pinned cards on a cork surface in a dark workspace. The upload and source inspector support keyboard interaction as described above.

The current fictional case contains about eight nodes; a legible 50–150-node case is an aspiration, not a demonstrated capability. There is a simple pin search; advanced filtering and a time scrubber are not implemented. No backend exists. ZIP selection validates mock metadata only: the app does not read or send ZIP contents, parse files, persist a graph, or perform real analysis. Current progress, hashes, confidence values, and rankings are illustrative. No data is persisted between sessions.

The current frontend types cover cases, nodes, edges, sources, gaps, insights, suggestions, audit records, uploads, and ingestion progress. They are a local API seam, not a finalized backend contract. The frontend reads case data through TanStack Query and does not import fixtures directly in UI components.

## Proposed Backend and API Direction

The intended backend direction is a Python service combining traditional ML with LangChain Deep Agents ([project](https://github.com/langchain-ai/deepagents)). OpenAI versus Anthropic, hosting such as Vultr, deployment design, and model/data policies are undecided. No backend implementation or confirmed endpoint contract exists.

An initial integration proposal is `POST /upload` returning a `jobId`, `GET /status/:id` for progress polling, and `GET /graph`, `/gaps`, `/insights`, and `/audit` for results. Source retrieval, case/job scoping, persistence, authorization, and detailed error behavior require design before implementation.

Conceptual data includes nodes with identifier/type/label/citations and optional anomaly score; edges with endpoints/type/optional timestamp/citations; gaps with description, 0–1 score, affected claims, suggested evidence, and citations; and insights with text, score, and citations. These are planning notes only. The frontend currently has additional display/source fields; schema alignment, score meaning, and citation representation are undecided.

## Demo Success

- A judge can follow the path from the landing page to the replayed board in under three minutes.
- The upload flow visibly identifies itself as simulated and completes reliably.
- The board is legible and usable on a laptop with pan, zoom, fit view, and minimap.
- Reviewers can open gaps, insights, relationships, suggestions, and audit entries and reach their cited source material.
- Ranking and next steps are easy to find, and uncertainty is represented clearly.
- No demo screen implies that mock ingestion parses ZIP files or performs real analysis.

There are no validated analytical results, real case data, computed confidence scores, testimonials, customer proof, or professional efficacy claims. No numerical user or performance targets have been validated.

## Evidence on Hand

- `frontend/src/api/fixtures.ts`: disposable fictional case, sources, excerpts, relationships, ranked gaps, insights, suggestions, and audit records.
- `frontend/src/api/contract.test.ts`: fixture citation integrity and mock upload state-transition checks.
- `frontend/README.md`: local and container demo instructions and backend integration seam.
- `frontend/src/api/types.ts` and `frontend/src/api/client.ts`: frontend contracts and replaceable mock adapter.

## Open Decisions

- Which first case type and dataset should guide backend work, and what is the intended role of insurance workflows?
- Which user group and review tasks should be validated first? What are typical case sizes and evidence volumes?
- How will original source files, excerpts, timestamps, and hashes be stored and cited with reliable provenance?
- What backend schema, source endpoints, job/case scoping, persistence, and error behavior will be adopted?
- How will ML and agent outputs be scored, calibrated, reviewed, and explained?
- Which provider, hosting environment, privacy policy, and retention controls are acceptable for sensitive evidence?
- Which evidence formats and size limits are required, especially for video, audio, and biological data?
- What production workflow, security, and deployment requirements are necessary beyond the hackathon prototype?

