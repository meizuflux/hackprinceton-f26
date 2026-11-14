# Compstat

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Compstat serves people reviewing evidence across domains, including insurance fraud investigators, crime scene investigators, detectives, and lawyers. It is not tied to one profession or case type.

The immediate audience is hackathon judges watching a three-minute demonstration. The prototype must work reliably and look appealing.

## Product Purpose

Help reviewers explore case evidence, inspect relationships, identify gaps, and decide what evidence to seek next while keeping the original sources accessible.

Demo success means a clear, reliable path from selecting a synthetic ZIP through staged ingestion progress to an inspectable evidence board, ranked gaps, suggested evidence, source inspection, and an audit trail.

## Operating Context

- This is a hackathon prototype using fictional, disposable case data.
- The main workspace is an interactive evidence board intended to remain usable on laptop screens, with pan, zoom, fit view, and a minimap.
- Reviewers can inspect entities, relationships, gaps, insights, suggestions, and source excerpts within the same workspace.
- The current session is temporary; case changes are not persisted between sessions.

## Capabilities and Constraints

- Use Vite, React, TypeScript, and React Flow. Use Bun 1.4.4 for dependencies and scripts.
- Keep API contracts and synthetic fixtures separate from presentation. `src/api/types.ts` defines `CaseApi`; `src/api/client.ts` owns the replaceable mock adapter. UI data loads through TanStack Query.
- Support ZIP selection and simulated ingestion progress. The current adapter does not read or upload ZIP contents, parse files, or perform real analysis. Make that limitation visible beside upload controls.
- Every graph relationship, gap, and insight must expose original source citations. Preserve source inspection for suggested evidence and audit records as well.
- Distinguish observed evidence from inference. A gap is not proof.
- Fixture hashes and confidence scores are illustrative, not computed. Bundled source excerpts are fictional; no real source files are included.
- Replace the mock API adapter when the Python backend becomes available.
- Professional production workflows, real ingestion behavior, persistence, and deployment beyond the prototype remain undecided.

## Brand Commitments

The product name is Compstat. Keep language useful across evidence-review domains rather than assuming every user works in law enforcement. The demo must combine working interactions with an appealing presentation.

## Evidence on Hand

- `src/api/fixtures.ts`: disposable fictional case, sources, excerpts, relationships, ranked gaps, insights, suggestions, and audit records.
- `src/api/contract.test.ts`: fixture citation integrity and mock upload state-transition checks.
- `README.md`: local and container demo instructions and the backend integration seam.
- No real case data, validated analytical results, computed confidence scores, testimonials, customer proof, or professional efficacy claims are provided.

## Product Principles

1. Make the three-minute demonstration clear and reliable.
2. Keep every interpretation traceable to its cited sources.
3. Treat missing evidence as uncertainty, never proof.
4. Be explicit about simulation and fictional data.
5. Preserve a useful evidence-review workflow across professional domains.

## Accessibility & Inclusion

Preserve keyboard access to the upload flow and source inspector. The upload modal traps focus and supports Escape when idle or ready; the inspector supports Escape. Keep the evidence board navigable on laptop screens.
