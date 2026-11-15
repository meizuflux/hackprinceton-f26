---
name: MapleTrace
description: A calm, evidence-first workspace for inspecting case material.
colors:
  primary: "#78cbff"
  primary-deep: "#3d92e3"
  primary-text: "#9cd6ff"
  primary-ink: "#04203a"
  focus: "#8ed5ff"
  workspace: "#10151c"
  panel: "#18202a"
  raised: "#202a36"
  chrome-border: "#33414f"
  question: "#d4ad6a"
  paper: "#e8e4d5"
  paper-card: "#faf8f1"
  text: "#e6ecf2"
  text-muted: "#a3b2c2"
  thread: "#a1372f"
  pushpin: "#ad604a"
typography:
  display:
    fontFamily: "Newsreader, Georgia, serif"
    fontSize: "clamp(41px, 4.5vw, 68px)"
    fontWeight: 400
  headline:
    fontFamily: "DM Sans, sans-serif"
    fontSize: "26px"
    fontWeight: 500
  title:
    fontFamily: "DM Sans, sans-serif"
    fontSize: "20px"
    fontWeight: 500
  section:
    fontFamily: "DM Sans, sans-serif"
    fontSize: "16px"
    fontWeight: 550
  body:
    fontFamily: "DM Sans, sans-serif"
    fontSize: "14px"
    fontWeight: 400
  detail:
    fontFamily: "DM Sans, sans-serif"
    fontSize: "12px"
    fontWeight: 400
  compact:
    fontFamily: "DM Sans, sans-serif"
    fontSize: "11px"
    fontWeight: 400
  micro:
    fontFamily: "DM Sans, sans-serif"
    fontSize: "10px"
    fontWeight: 400
  evidence:
    fontFamily: "Excalifont, DM Sans, sans-serif"
    fontSize: "21px"
    fontWeight: 400
  evidence-summary:
    fontFamily: "Excalifont, DM Sans, sans-serif"
    fontSize: "15px"
    fontWeight: 400
  evidence-thread:
    fontFamily: "Excalifont, DM Sans, sans-serif"
    fontSize: "14.5px"
    fontWeight: 400
  label:
    fontFamily: "IBM Plex Mono, monospace"
    fontSize: "9px"
    fontWeight: 400
    letterSpacing: "1.4px"
rounded:
  pin: "2px"
  subtle: "3px"
  control: "4px"
  button: "5px"
  panel: "6px"
  surface: "7px"
  card: "8px"
spacing:
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.primary-ink}"
    rounded: "{rounded.button}"
    padding: "12px 18px"
    height: "44px"
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.text}"
    rounded: "{rounded.button}"
    padding: "12px 18px"
    height: "44px"
---

# Design System: MapleTrace

## Overview

**Creative North Star: “The Evidence Pinboard”**

MapleTrace pairs a cool ink workspace with a faint warm paper canvas and paper evidence cards. Glassy blue, taken from the logo, marks the main action, selection and focus; amber marks open questions. The visual language keeps the board distinctive while making the review path easy to scan during a short demo.

Typography controls, search, and the primary demo action should remain easy to find. The inspector puts original sources first, and graph and list views provide two ways to inspect the same evidence. Scores are labeled illustrative wherever shown.

**Key Characteristics:**
- Cool ink workspace chrome with glassy blue accents and a faint warm paper evidence surface.
- Paper-toned pinned cards with restrained accent colors.
- Sources and uncertainty are visible parts of the review flow.

## Brand

The mark is two overlapping chevrons: an off-white chevron (`#f4f2ec`) pointing right, behind a glassy blue chevron pointing left. The blue gradients run from light sky at the tip (`#9cdcff`) to `#3b96ee` on the upper arm and dip to `#3d92e3` on the lower arm. `public/mapletrace-mark.svg` is the canonical artwork; `src/components/BrandMark.tsx` renders the same geometry inline (`<BrandMark size={20} />`, where size is the height in px; decorative unless `title` is set). Favicons are `public/favicon.svg` (the mark on a dark rounded tile, so it reads on light browser chrome), `favicon-32.png`, `favicon.ico` and `apple-touch-icon.png`, rendered from the SVG.

- Place the mark beside the “MapleTrace” wordmark on dark surfaces only; the off-white chevron disappears on paper or white. Never recolor, outline or rotate it.
- Do not use lucide or other stock icons as a stand-in logo.

## Colors

The palette moves between cool ink neutrals, glassy blue accents, warm evidence paper, and amber for questions. All tokens live in `:root` in `src/styles/base.css`.

### Brand blue
- **Sky scale:** `--brand-100` #b4e4ff, `--brand-200` #9cdcff, `--brand-300` #78cbff (= `--brand`), `--brand-400` #58b2ff, `--brand-500` #3d92e3.
- **`--brand-text` #9cd6ff:** accent text, links and icons on dark (10:1 on the workspace).
- **`--brand-ink` #04203a:** text on brand fills (7.2:1 on #58b2ff).
- **`--brand-gradient` / `--brand-gradient-hover`:** 135° sky gradient for primary buttons and the review toggle only.
- **`--brand-selected` #58b2ff1f, `--brand-hover` #58b2ff14, `--brand-border` #58b2ff80:** selected rows, active tabs and toolbar items, hover washes, selected borders. Active toolbar items add a 2px inset `--brand-400` edge.
- **`--focus-ring` #8ed5ff:** every keyboard focus outline.

### Glass
- **`--glass-fill`** is a faint top-lit white gradient layered over a chrome surface (`background: var(--glass-fill), var(--surface)`); **`--glass-edge`** is a 1px inner top highlight. Use glass on chrome (top bar, landing nav, modals, focus buttons) only, never on reading surfaces, source excerpts, evidence cards or the paper canvas. Backdrop blur is reserved for the landing nav and the modal backdrop.

### Secondary
- **Question Amber `--amber` #d4ad6a:** open gaps and question-related emphasis.

### Neutral
- **Ink Workspace `--surface` #10151c:** the main dark application surface; `--panel` #18202a, `--raised` #202a36 (hover), `--field` #141b23 (inputs).
- **Lines:** `--line` #2c3946 for dividers; `--chrome-border` #33414f for floating chrome edges.
- **Evidence Paper:** pinned records and source-like cards on the board (unchanged warm paper).
- **Text `--text` #e6ecf2** and **Muted `--muted` #a3b2c2** (8.5:1 on the workspace).

`--green` remains a legacy alias of `--brand` so unmigrated rules stay on-brand; new code uses the `--brand-*` tokens.

**The Evidence-State Rule.** Use blue for interaction, selection and focus, and amber for questions; keep observed records legible on paper-toned cards. Semantic status colors (recorded or leading green, asserted or disproven red) stay distinct from the brand blue.

## Typography

**Display Font:** Newsreader (with Georgia, serif fallback)
**Body Font:** DM Sans (with sans-serif fallback)
**Label/Mono Font:** IBM Plex Mono (with monospace fallback)

The serif face gives source excerpts a document-like character. Evidence-card titles, summaries, question links, and thread annotations use locally bundled Excalifont for legible handwriting. Workspace controls and card metadata retain DM Sans. IBM Plex Mono distinguishes compact metadata and numbers. The other fonts are requested from Google Fonts; if unavailable, the declared fallback stacks apply.

Excalifont is distributed with its upstream SIL Open Font License in `public/fonts/`. The Latin subset is bundled; unsupported characters fall back to DM Sans. Card titles use 21px/1.18, summaries use 15px/1.4, and thread annotations use 14.5px/1.25. Annotation words wrap only at spaces. Keep text upright and high contrast; imperfections belong to the outline, never the letter alignment.

### Hierarchy
- **Display** (400, responsive 41–68px): welcome-page lead.
- **Headline** (500, 26px): case and section headings.
- **Body** (400, 14px): default interface reading size.
- **Label** (400, 9px, 1.4px tracking): compact metadata and eyebrow labels.

## Layout

The faint paper background fills the case canvas. A compact toolbar floats at the upper left, using the same dark surface, border, and radius as the board controls. It is 48px wide collapsed and 192px expanded, with 34px rows and 16px icons. Expansion reveals section labels and project actions; omit a large wordmark, project heading, or full-height sidebar. The graph retains its dimensions and viewport while desktop controls and page content clear the expanded toolbar. Collapsed icons retain accessible names and tooltips. Escape collapses the toolbar while focus is inside it, and choosing a section on small screens collapses it. Search, list, audit, and review controls float above the canvas. Analysis, source inspection, and audit share a review dock over the right side of the canvas. At widths up to 900px, the dock stacks below the board. At widths up to 540px, search spans the board toolbar. Returning from an inspector restores review context. The board offers graph and list views, visible search, pan and zoom controls, fit view, and a minimap. The minimap is a fixed overview of the pins. A viewport rectangle shows the visible area and moves and resizes with pan and zoom. Dragging that rectangle keeps the pins in view; panning the canvas itself may still leave the board. A two-finger trackpad swipe pans the canvas; pinch, the zoom controls, and holding the zoom key while scrolling change scale. The shared spacing rhythm uses compact 8–24px steps.

## Elevation & Depth

Depth combines tonal surface changes with restrained shadows. The paper background stays nearly flat; paper cards lift slightly from it, and an active card receives a clear amber outline. Dialogs and floating controls use stronger shadows than the resting workspace.

## Shapes

Controls and workspace panels use gently rounded corners, while evidence cards and gap markers stay nearly square to retain a paper-and-pin character. Focus is shown with a visible `--focus-ring` blue outline and offset. Badges and status indicators use pill or circular shapes where appropriate.

## Components

### Buttons
- **Character:** compact, direct controls with clear primary emphasis.
- **Shape:** softly rounded (5px).
- **Primary:** `--brand-gradient` fill with an inner top highlight, `--brand-ink` text, 12px by 18px padding, and a 44px minimum height. Disabled primary buttons use a flat slate fill rather than reduced opacity.
- **Hover / Focus:** `--brand-gradient-hover` on hover; 2px `--focus-ring` outline with 3px offset.
- **Secondary:** transparent fill with a slate border and light text; hover adds `--brand-hover` and `--brand-border`.

### Inputs / Fields
- **Style:** dark inset `--field` search field with a thin `--line` border and 4px corners.
- **Focus:** shared `--focus-ring` outline; search remains visible in the board toolbar.

### Cards / Containers
- **Corner Style:** evidence cards use gently varying paper silhouettes; the enclosing workspace uses 7px.
- **Background:** one ivory paper surface keeps attention on content; icons and text identify record types.
- **Shadow Strategy:** subtle lift at rest, stronger amber outline for the selected card.
- **Internal Padding:** evidence cards use 14px at the top and 17px at the sides.

### Signature Component: Evidence Pin

Paper cards sit on the faint paper canvas with a centered pushpin inset 6px inside the paper's top edge, record type, title, brief summary, time where available, citation count, and an inspect action. They measure 248 × 224px, with a single gently uneven paper silhouette and one quiet ivory surface. Each silhouette varies slightly by card without tilting the text. Omit the inset frame and footer divider; use an arrow-only source-inspection button with a full accessible name. The whole card shows a pointer cursor and remains draggable. Titles and summaries show at most two lines; inspection preserves the full text and citations. A separate Open question button opens the card's cited gap directly. A gap signals a question requiring verification; it does not establish proof.

Initial placement and completed card drops preserve at least 40px between cards. Layout is presentation geometry only and does not create case relationships. Threads use the facing card edges, choosing horizontal or vertical attachment from their positions rather than routing every connection through a top pin. Smooth 3px red curves connect the cards. Small arrowheads appear only when the API adapter explicitly sets `directed: true`; an omitted direction is rendered without an arrowhead. Badge association and time overlap are undirected in the disposable mock. Preserve the supplied source and target order; never reverse a relationship from screen position or guessed meaning. The list and inspector use matching directional or undirected notation. Claims and inferences use dashed red threads with compact explicit labels; hover, focus, or selection reveals their relationship wording. Observed relationship labels use a quiet flat backing without a border. Every relationship label is a keyboard-accessible source-inspection button. The minimap reuses the same paper silhouettes, inset top pushpins, facing-edge Bezier connections, explicit direction, and live selection state. Question cards receive an amber outline rather than a different fill. A lightly shaded sage viewport indicator keeps the preview legible while tracking pan and zoom.

### Signature Component: Source Inspector

The inspector docks within the workspace and presents original sources first. Source excerpts expand inline, with metadata and placeholder hashes visibly identified. Selecting a record, relationship, gap, insight, suggestion, or audit item should retain a path to its cited material.

## Do's and Don'ts

### Do:
- **Do** keep the main demo action visually prominent and controls readable.
- **Do** pair graph inspection with a searchable list view.
- **Do** label illustrative scores and keep questions distinct from observed evidence.
- **Do** keep source inspection near the item being reviewed.

### Don't:
- **Don't** use amber question styling as proof that a claim is true.
- **Don't** imply that illustrative scores or placeholder hashes are computed results.
- **Don't** rely on the remote font request without the declared system fallbacks.

The board texture is `src/assets/paper.webp`, a generated material asset with its exact prompt in the adjacent JSON sidecar. Show it beneath a flat 50% `#eee8de` overlay: visible paper fibers without competing with the evidence. Preserve the surrounding dark interface.
