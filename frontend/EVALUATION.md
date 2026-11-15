# Frontend evaluation

Baseline reviewed November 14, 2026, before the readability and demo-flow refinement.

Method: independent design and technical assessments by `design_assessment` and `technical_assessment`, plus a parent inspection of the rendered welcome screen. Both agents reviewed source; the technical assessment ran the Impeccable detector. Shared native browser control was unreliable, so the initial board assessment is source-based. No browser overlay was injected.

## Baseline design health

| Heuristic | Score / 4 | Main observation |
| --- | --- | --- |
| System status | 3 | Mock progress exists; search needs result feedback. |
| Match to the real world | 3 | Evidence metaphor fits; avoid language tied to one profession. |
| User control | 3 | Pan, zoom, fit, and close work in the implementation; inspection can obscure context. |
| Consistency | 3 | Coherent paper pins and analysis patterns; rail actions rely on icons. |
| Error prevention | 2 | ZIP metadata validation exists; simulation must be explicit before starting. |
| Recognition over recall | 3 | Legend and citations help; source access needs stronger prominence. |
| Efficiency | 2 | Search disappears below 1150px; graph inspection needs a keyboard alternative. |
| Minimalist design | 3 | Strong identity; undersized text and multiple panels compete for attention. |
| Error recovery | 2 | Retry exists; upload and status recovery need interaction verification. |
| Help and documentation | 2 | Uncertainty notes exist; the first demo step needs clearer emphasis. |
| **Total** | **26 / 40** | **Baseline assessment; not a post-change score.** |

## What works

- Cork, paper pins, and linked relationships give MapleTrace a recognizable evidence-review identity.
- Citations and uncertainty are part of the workflow rather than an unrelated help page.
- One source inspector covers evidence, relationships, gaps, inferences, and suggested next steps.

## Priorities

1. **P1 — Readability and workspace continuity.** Much operational text is 7–10px before graph zoom. Search disappears at laptop widths; narrow screens retain a side-by-side panel. Source details overlay the workspace. Increase type and control sizes, retain search, stack panels on small screens, and use a docked inspector with original sources near the top.
2. **P1 — A clear, honest demo path.** The welcome screen emphasizes upload despite the prototype's synthetic behavior. Scores can look computed, search lacks empty feedback, and icon-only actions and incomplete tab semantics add friction. Prioritize the fixture demo, explain ZIP simulation before processing, label illustrative scores locally, add search feedback and standard keyboard tabs, and expose records and relationships through a list alternative.

## Cognitive load and users

The board and review panel provide useful grouping. Tiny labels and competing metadata increase the effort of finding a first action. A first-time judge needs an obvious demo entry; a professional evidence reviewer needs readable provenance and a clear distinction between a source record and an inference. Keyboard users need a direct path to both record and relationship inspection.

The welcome preview's source card obscures part of its question card in the baseline capture. Preserve the physical pin-board treatment while separating the readable content.

## Detector and limits

`impeccable detect --json frontend/src` returned zero findings. This does not establish accessibility, contrast, visual quality, or interaction correctness. The source review separately identified missing tab keyboard behavior and responsive search/board problems. React Flow provides focusable graph wrappers, but native graph selection does not itself call the application's source-inspection handler; an explicit Inspect button and list alternative are appropriate.

User confirmed: “preserve identity, improve readability and demo flow.” Implementation and verification are recorded in the signed feature commit; this file preserves the baseline rather than inventing an improved score.
