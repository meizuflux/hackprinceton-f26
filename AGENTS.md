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

- API seam: `CaseApi` in `src/api/types.ts`; `src/api/client.ts` owns mock jobs. UI loads the case through TanStack Query and never imports fixtures directly.
- Mock uploads never read ZIP contents. Keep this limitation visible beside upload controls. Fixture hashes and confidence scores are illustrative, not computed.
- Luna subagents are requested for delegated work. Fetch remote refs frequently and make one signed commit per feature.
- Board uses React Flow custom pinned cards on a cork surface inside a dark workspace. Relationships and ranked analysis open the shared source inspector.
- Validate API fixture links and mock upload state transitions with `npm test`; use `npm run build` for TypeScript and the production bundle.
- Browser-verified demo path: synthetic ZIP selection → staged mock progress → board; gap and insight inspection; original source expansion; edge inspection; audit trail. Upload modal traps keyboard focus and supports Escape when idle/ready; inspector supports Escape.
- Run `npm run format` after changes. No real source files or computed hashes are bundled; source excerpts live only in disposable fixtures.
