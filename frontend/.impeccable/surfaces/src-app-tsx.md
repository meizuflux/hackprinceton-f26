---
version: 1
slug: "src-app-tsx"
primary_target: "src/App.tsx"
related_targets: ["src/styles.css", "src/styles/", "src/components/Inspector.tsx", "src/components/EvidenceNode.tsx", "src/components/WorkspaceNavigation.tsx", "src/onboarding/"]
---

# Canvas workspace cleanup

Mode: Operate; landing: Persuade. Code-first implementation. Product truth: root `SPEC.md`, read only. The user confirmed the landing primary action goes to projects.

## Confirmed frontend scope

Impeccable init is limited to the frontend. Root `SPEC.md` remains the canonical product record; do not create `PRODUCT.md` or require backend documentation changes to begin frontend work. Read `SPEC.md`, `frontend/DESIGN.md`, and this brief directly when the context loader does not discover them.

The user confirmed the next goal: remove visual clutter and inconsistency and present a cohesive, clear design. Apply that goal across the landing page, project manager, upload flow, case sections, board controls, and review dock. Preserve the established evidence-pinboard identity and working interactions. This init records scope only; it does not establish a new visual world or claim that the interface has passed a fresh visual review.

## Direction contract

THESIS: The case is a full-screen evidence board. Navigation and review controls float above it; marketing chrome never consumes working space.

OWN-WORLD: Preserve dark moss controls, faint warm paper, ivory evidence cards, sage actions, amber questions and rust relationships. Sans interface controls; serif source excerpts. Reviewers use laptops during a short presentation, so keep controls readable and surfaces distinct.

CARD DIRECTION: User confirmed a clean modern interface around a traditional detective pinboard, with clarity above all else. Cards use legible Excalidraw-style handwritten titles, clean sans-serif summaries, and subtle outline imperfections; text stays upright, summaries stay brief, and full details remain in source inspection. Red threads must be thick enough to read against faint paper and run smoothly between facing sides, without looping beneath the source or unnecessarily attaching to the target's top. Cards keep clear spacing. Claims, inferences, and open questions retain explicit distinctions and citations.

STORY: Open projects. Create a named project with a ZIP preview, or open the fictional case from the manager. Inspect records and relationships, then gaps, original sources, suggested evidence and audit. Once opened, the fictional case is a project, not a repeated prompt.

FIRST VIEWPORT: Faint paper fills the canvas. A compact menu toggle sits upper left beside the floating title, search, list, audit and review toolbar. Zoom/fit, legend and minimap float below. A review panel opens on the right without resizing or resetting the graph; below 900px it stacks beneath it.

FORM: seed: none (pinned). User: “the pin board is the full background and everything is a layer element / button on top”; navigation “should be expandable and collapsable.” Code-first; generated concept is exploratory, not an approved measured comp. Existing product context stays in SPEC.md per repository instructions.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance.

REFINEMENT: The user found the first treatment too busy, then found the softened paper too faint. Keep one ivory card color, visible paper grain beneath a flat 50% warm overlay, compact 248 × 224px cards, and quiet unboxed relationship labels. Keep Claim and Inference labels visible; reveal their wording on hover, focus, or selection.
