---
name: MapleTrace
description: A calm, evidence-first workspace for inspecting case material.
colors:
  primary: "#78cbff"
  primary-light: "#9cdcff"
  primary-strong: "#58b2ff"
  primary-deep: "#3d92e3"
  primary-text: "#9cd6ff"
  primary-selected: "#58b2ff1f"
  primary-ink: "#04203a"
  focus: "#8ed5ff"
  workspace: "#10151c"
  panel: "#18202a"
  raised: "#202a36"
  field: "#141b23"
  line: "#2c3946"
  chrome-border: "#33414f"
  question: "#d4ad6a"
  paper: "#e8e4d5"
  paper-canvas: "#eee8de"
  paper-card: "#faf8f1"
  text: "#e6ecf2"
  text-muted: "#a3b2c2"
  contradiction: "#b3262f"
  ink-person: "#7b3f8f"
  ink-device: "#2b5c99"
  ink-event: "#17706a"
  ink-location: "#55721c"
  ink-statement: "#4d5157"
  ink-other: "#6b5d4f"
typography:
  display:
    fontFamily: "Newsreader, Georgia, serif"
    fontSize: "clamp(44px, 5.2vw, 68px)"
    fontWeight: 400
    lineHeight: 1.06
    letterSpacing: "-0.03em"
  headline:
    fontFamily: "Newsreader, Georgia, serif"
    fontSize: "42px"
    fontWeight: 400
    lineHeight: 1.1
  excerpt:
    fontFamily: "Newsreader, Georgia, serif"
    fontSize: "17px"
    fontWeight: 400
    lineHeight: 1.55
  title:
    fontFamily: "DM Sans, sans-serif"
    fontSize: "20px"
    fontWeight: 550
  section:
    fontFamily: "DM Sans, sans-serif"
    fontSize: "16px"
    fontWeight: 550
  case-title:
    fontFamily: "DM Sans, sans-serif"
    fontSize: "15px"
    fontWeight: 550
  body:
    fontFamily: "DM Sans, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
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
    lineHeight: 1.18
  evidence-summary:
    fontFamily: "Excalifont, DM Sans, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.4
  evidence-thread:
    fontFamily: "Excalifont, DM Sans, sans-serif"
    fontSize: "14.5px"
    fontWeight: 400
    lineHeight: 1.25
  label:
    fontFamily: "IBM Plex Mono, monospace"
    fontSize: "11px"
    fontWeight: 400
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
    rounded: "{rounded.panel}"
    padding: "11px 18px"
    height: "44px"
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.text}"
    rounded: "{rounded.panel}"
    padding: "11px 18px"
    height: "44px"
  input-search:
    backgroundColor: "{colors.field}"
    textColor: "{colors.text}"
    rounded: "{rounded.panel}"
    padding: "0 10px"
    height: "36px"
  nav-toolbar:
    backgroundColor: "{colors.workspace}"
    textColor: "{colors.text-muted}"
    rounded: "{rounded.panel}"
    width: "48px"
  nav-toolbar-item-active:
    backgroundColor: "{colors.primary-selected}"
    textColor: "{colors.primary-text}"
    rounded: "{rounded.subtle}"
    height: "34px"
  evidence-pin:
    backgroundColor: "{colors.paper-card}"
    padding: "14px 17px 4px"
    width: "248px"
    height: "224px"
---

# Design System: MapleTrace

## Overview

**Creative North Star: “The Evidence Pinboard”**

MapleTrace pairs a cool ink workspace with a faint warm paper canvas and paper evidence cards. Glassy blue, taken from the logo, marks the main action, selection and focus; amber marks open questions. The visual language keeps the board distinctive while making the review path easy to scan during a short demo.

Controls, search, and the primary demo action should remain easy to find. The inspector puts original sources first, and graph and list views provide two ways to inspect the same evidence. Backend scores are computed ranks shown as labels, never percentages; mock scores are labelled illustrative.

**Key Characteristics:**
- Cool ink workspace chrome with glassy blue accents and a faint warm paper evidence surface.
- Paper-toned pinned cards coloured by record type and certainty.
- Sources and uncertainty are visible parts of the review flow.

## Brand

The mark is two overlapping chevrons: an off-white chevron (`#f4f2ec`) pointing right, behind a glassy blue chevron pointing left. The upper arm's gradient runs from light sky at the tip (`#a4e0ff`) to `#3b96ee`; the lower arm starts at `#9cdcff`, dips to `#3d92e3` mid-arm and lightens again to `#7acbff`, which gives the glassy fold. `public/mapletrace-mark.svg` is the canonical artwork; `src/components/BrandMark.tsx` renders the same geometry inline (`<BrandMark size={20} />`, where size is the height in px and width follows the 80:56 viewBox; decorative unless `title` is set). Shipped sizes are 20px in the landing and projects nav, 18px in the case navigation and 16px in the landing footer. Favicons are `public/favicon.svg` (the mark on a dark rounded tile, so it reads on light browser chrome), `favicon-32.png`, `favicon.ico` and `apple-touch-icon.png`, rendered from the SVG.

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
- **`--focus-ring` #8ed5ff:** every keyboard focus outline on dark chrome. The global rule is a 2px solid outline with a 3px offset on buttons, links, inputs, text areas and summaries; fields with `:focus-within` use a 1px offset. Paper-surface controls (thread labels, card actions) use dark ink outlines instead so focus stays visible on paper.

### Glass
- **`--glass-fill`** is a faint top-lit white gradient layered over a chrome surface (`background: var(--glass-fill), var(--surface)`); **`--glass-edge`** is a 1px inner top highlight. Use glass on chrome (top bar, landing nav, modals, focus buttons) only, never on reading surfaces, source excerpts, evidence cards or the paper canvas. Backdrop blur is reserved for the landing nav and the modal backdrop.

### Secondary
- **Question Amber `--amber` #d4ad6a:** open gaps and question-related emphasis.

### Neutral
- **Ink Workspace `--surface` #10151c:** the main dark application surface; `--panel` #18202a, `--raised` #202a36 (hover), `--field` #141b23 (inputs).
- **Lines:** `--line` #2c3946 for dividers; `--chrome-border` #33414f for floating chrome edges.
- **Evidence Paper `--paper` #e8e4d5:** the backing of source excerpts in the inspector. The board canvas is `#eee8de` over the paper texture, and cards fill with `#faf8f1` washed by their type tint.
- **Text `--text` #e6ecf2** and **Muted `--muted` #a3b2c2** (8.5:1 on the workspace).

`--green` remains a legacy alias of `--brand` (still read by about 30 rules) so unmigrated rules stay on-brand; new code uses the `--brand-*` tokens, and focus outlines always use `--focus-ring`, never `--green`.

**The Evidence-State Rule.** Use blue for interaction, selection and focus, and amber for questions; keep observed records legible on paper-toned cards. Semantic status colors (recorded or leading green, asserted or disproven red) stay distinct from the brand blue.

## Board colours

Colour on the board comes only from the API's type and certainty, through the inks in `src/components/board-colors.ts` (CSS in `board-coding.css`). Every ink keeps at least 4.5:1 against the paper card (`#faf8f1`) and canvas (`#eee8de`); `board-colors.test.ts` enforces it. Colour always travels with an icon, a label or a line pattern.

| Card type | Ink | Thread family sharing the hue |
| --- | --- | --- |
| Person | `#7b3f8f` purple | Identity |
| Device or account | `#2b5c99` blue | Communication |
| Event | `#17706a` teal | Time |
| Location | `#55721c` olive | Place |
| Statement | `#4d5157` grey | Claim |
| Other | `#6b5d4f` brown | Other link |

- **Contradiction** threads are red (`#b3262f`); red means nothing else.
- **Certainty:** observed threads are solid, inferences dashed `8 7`, claims dashed `3 6`. Inferred cards have a dashed outline and an "Inferred" chip.
- **Pushpins** take the card's type ink (9px, with a soft drop and inner shade); `#ad604a` rust is only the fallback when no type ink is set.
- **Open questions:** an amber outline and a question flag on the card.
- **Key:** a 32px pill at the bottom left opening a popover (Cards, Threads) that lists only the types present in the case. The minimap mirrors the colours.
- **Story view:** compact story cards (196×96) frame a 300×140 hero card; group cards show an exact count and fan out their members; the opening fit aims for about 90% zoom beside the open dock.

### Origin marks

Provenance (traditional ML, agent, LLM) is encoded without hue: a graphite `#33373d` stamp chip with icon and word, a faint dotted (ML), hatched (agent) or ruled (LLM) strip along the card bottom, the icon on thread labels, a minimap tab and an Origin legend row. Rules and record items stay unmarked.

## Typography

**Display / Document Font:** Newsreader (with Georgia, serif fallback)
**Body Font:** DM Sans (with sans-serif fallback)
**Evidence Hand:** Excalifont (with DM Sans fallback)
**Label/Mono Font:** IBM Plex Mono (with monospace fallback)

DM Sans carries the whole case workspace: headings, controls, metadata and body. Newsreader appears in only two places: the landing (`/`) and projects (`/projects`) pages, where it sets hero and page headings, and source excerpts (inspector blockquotes and chat citations), where it gives quoted material a document-like character. Evidence-card titles, summaries, question links and thread annotations use locally bundled Excalifont for legible handwriting; card metadata stays in upright DM Sans. IBM Plex Mono distinguishes compact metadata, IDs, locators, timestamps and numbers. DM Sans, Newsreader and IBM Plex Mono are requested from Google Fonts; if unavailable, the declared fallback stacks apply.

Excalifont is distributed with its upstream SIL Open Font License in `public/fonts/` and preloaded from `index.html`. The Latin subset is bundled; unsupported characters fall back to DM Sans. Annotation words wrap only at spaces. Keep text upright and high contrast; imperfections belong to the outline, never the letter alignment.

### Hierarchy
- **Display** (Newsreader 400, clamp(44px, 5.2vw, 68px), 1.06, -0.03em): landing hero only.
- **Headline** (Newsreader 400, 42px, 1.1): the projects page heading; its empty-state and case-card headings use Newsreader 26px.
- **Excerpt** (Newsreader 400, 17px, 1.55): original source excerpts on paper in the inspector; chat citations use 13.5px.
- **Title** (DM Sans 550, 20px): the inspector's item heading.
- **Section** (DM Sans 550, 16px): case section headings (Raw evidence, Generalized files, Insights sections, Ask about this case); the evidence browser heading uses 17px and the Insights intro 22px.
- **Case title** (DM Sans 550, 15px): the single case `h1` in the top bar, with a 12px muted subtitle line.
- **Body** (DM Sans 400, 14px, 1.5): default interface reading size.
- **Detail / Compact / Micro** (DM Sans 400, 12px / 11px / 10px): secondary descriptions, chips, counts and timestamps.
- **Label** (IBM Plex Mono 400, 11px; 10–12px in use): IDs, locators, hashes and numeric metadata.

**The One Title Rule.** Each case page has exactly one `h1`, the case (or session project) title in the top bar. Section names are sans `h2`s beneath it, never a second `h1` and never serif.

**The Serif Is For Documents Rule.** Newsreader marks marketing headings on `/` and `/projects` and quoted source text. It never sets workspace headings, controls or metadata.

## Layout

The board is the primary canvas and never resizes when navigation or review panels open. The faint paper background (`#eee8de` at 50% over `paper.webp`) fills it. A flat 52px top bar holds the case title, search, the List/Board switch, the audit trail and, on the board, the Case analysis entries; section pages keep only the audit trail as their case-level action. A compact toolbar floats at the upper left, 16px from the edge and below the top bar, using the same dark surface, border, 6px radius and shadow as the board controls. It is 48px wide collapsed and 192px expanded, with 34px rows and 16px icons. Expansion overlays the canvas, revealing section labels and project actions; omit a large wordmark, project heading, or full-height sidebar. Collapsed icons retain accessible names and tooltips. Escape collapses the toolbar while focus is inside it, and choosing a section on small screens collapses it.

Analysis, source inspection, and audit share a review dock: 400px wide, 16px from the right and bottom, with 8px corners. While the dock is open above 900px, the canvas sets `--dock-offset: 416px` (dock plus gap), and the minimap and zoom controls move left of the dock with a 0.2s ease-out on `right`; the Ask widget moves to the matching 432px. At widths up to 900px, the dock stacks below the board and the offset stays 0. At widths up to 540px, search spans the board toolbar. Returning from an inspector restores review context.

Bottom-right chrome stacks in a fixed order: the 240px minimap sits at the 16px board inset, the zoom controls sit 10px to its left, and the Ask widget sits above the minimap. `CanvasMinimap` publishes its rendered height as `--minimap-height`, and the widget's bottom is that height plus 28px (inset 16 + gap 12), so it expands upward without covering the minimap, the zoom controls or the bottom-left Key.

The board offers graph and list views, visible search, pan and zoom controls, fit view, and a minimap. The minimap frames the pins alone, so its scale never changes while panning. A clipped viewport rectangle shows the visible area. Pressing the rectangle grabs it; pressing elsewhere centres the view there; arrow keys pan. Minimap navigation clamps the view to the pins; panning the canvas itself may still leave the board. The zoom readout sits in the zoom controls and resets to 100%. A two-finger trackpad swipe pans the canvas; pinch, the zoom controls, and holding the zoom key while scrolling change scale. The shared spacing rhythm uses compact 8–24px steps.

## Elevation & Depth

Depth combines tonal surface changes with restrained shadows. The paper background stays nearly flat; paper cards lift slightly from it. Floating chrome (toolbar, zoom controls, dock, minimap, Key) shares one shadow, and dialogs sit above a blurred backdrop. Focus on the board is amber: reviewed targets get an amber outline and a warm glow while everything else dims.

### Shadow Vocabulary
- **Chrome** (`--shadow`, `0 8px 28px #03070c66`): floating toolbar, zoom controls, review dock and other overlays on the canvas.
- **Primary lift** (`inset 0 1px 0 #ffffff59, 0 4px 14px #1d6fc433`): the primary button's glass highlight and soft blue lift.
- **Paper card** (`drop-shadow(0 3px 4px #4e443b26)` on the silhouette): resting evidence cards.
- **Review focus** (3px `--amber` outline, 3px offset, `drop-shadow(0 8px 24px #d4ad6a73)`): cards in the reviewed cluster; their threads thicken to 4.5px with `drop-shadow(0 2px 5px #c48c3499)`. Non-target cards dim to 16% and threads to 14% opacity.

**The Amber Focus Rule.** Amber outlines and glows mean "this is what you are reviewing" or "this is an open question"; blue means interaction and selection in the chrome. Never swap them.

## Shapes

Controls and workspace chrome use gently rounded corners: 6px (`--radius`) for buttons, search, the toolbar and zoom controls; 3–4px for rows, chips and small toggles; 8px for the review dock. Evidence cards use a single gently uneven paper silhouette, and source excerpts on paper keep near-square 2px corners to stay document-like. Pushpins, status dots and count badges are circular or pill-shaped.

## Components

### Buttons
- **Character:** compact, direct controls with clear primary emphasis.
- **Shape:** softly rounded (6px, `--radius`).
- **Primary:** `--brand-gradient` fill with a `#b4e4ff66` border and the primary lift, `--brand-ink` text at weight 600, 11px by 18px padding, and a 44px minimum height. Disabled primary buttons use a flat slate fill (`#233142`, text `#a9bacb`) rather than reduced opacity.
- **Hover / Focus / Active:** `--brand-gradient-hover` on hover; 2px `--focus-ring` outline with 3px offset; pressing darkens to 94% brightness. Colour transitions run 160ms.
- **Secondary:** transparent fill with a `#44566a` border and light text; hover adds `--brand-hover` and `--brand-border`.
- **Text and icon buttons:** transparent, muted, 36px minimum; hover lifts text to `--text` over a faint white wash.

### Inputs / Fields
- **Style:** dark inset `--field` search field, 36px tall, with a thin `--line` border, 6px corners and a 14px search icon.
- **Focus:** 2px `--focus-ring` outline at 1px offset via `:focus-within`; search remains visible in the board toolbar at every width.

### Navigation
- **Case toolbar:** `--surface` fill, `--chrome-border` edge, 6px corners, `--shadow`. Rows are 34px, 12px DM Sans in `--muted`; hover lifts to `--text` over a faint white wash. The current section uses `--brand-text` on `--brand-selected` with a 2px inset `--brand-400` left edge.

### Section Header
- One case `h1` (15px/550) and a muted subtitle sit in the top bar on every case route. Section pages and the review dock title their content with a sans `h2` (16px/550; dock header 15px/550), optionally followed by a 12px muted note and a count. The board's list view titles itself “Evidence & connections” the same way.

### Cards / Containers
- **Corner Style:** evidence cards use gently varying paper silhouettes; dark panels use 6–8px.
- **Background:** ivory paper with a faint wash of the card type's hue (see Board colours); the type icon and label always accompany the colour.
- **Shadow Strategy:** subtle lift at rest; a 3px amber outline at 3px offset for the active card.
- **Internal Padding:** evidence cards use 14px at the top and 17px at the sides.

### Signature Component: Evidence Pin

Paper cards sit on the faint paper canvas with a centered pushpin in the card's type ink set just inside the paper's top edge (9px pin at 5px), record type, title, brief summary, time where available, citation count, and an inspect action. Sizes are role-tailored in `board-layout.ts` (default 248 × 224px), with a single gently uneven paper silhouette. Each silhouette varies slightly by card without tilting the text. Omit the inset frame and footer divider; use an arrow-only source-inspection button with a full accessible name. The whole card shows a pointer cursor and remains draggable. Titles and summaries show at most two lines; inspection preserves the full text and citations. A separate Open question button opens the card's cited gap directly. A gap signals a question requiring verification; it does not establish proof.

Initial placement and completed card drops preserve at least 40px between cards. Layout is presentation geometry only and does not create case relationships. Threads use the facing card edges, choosing horizontal or vertical attachment from their positions rather than routing every connection through a top pin. Smooth 3px curves connect the cards, coloured by thread family (see Board colours). Small arrowheads appear only when the API adapter explicitly sets `directed: true`; an omitted direction is rendered without an arrowhead. Preserve the supplied source and target order; never reverse a relationship from screen position or guessed meaning. The list and inspector use matching directional or undirected notation. Claims and inferences use dashed threads with compact explicit labels; hover, focus, or selection reveals their relationship wording. Observed relationship labels use a quiet flat backing without a border. Every relationship label is a keyboard-accessible source-inspection button. The minimap reuses the same paper silhouettes, inset top pushpins, facing-edge Bezier connections, thread colours, explicit direction, and live selection state. Question cards receive an amber outline and flag rather than a different fill.

### Signature Component: Source Inspector

The inspector docks within the workspace and presents original sources first. Source excerpts expand inline with their metadata and render in Newsreader on a `--paper` backing with dark ink; with the mock adapter, hashes are visibly marked as placeholders. Selecting a record, relationship, gap, insight, suggestion, or audit item should retain a path to its cited material.

## Do's and Don'ts

### Do:
- **Do** keep the main demo action visually prominent and controls readable.
- **Do** pair graph inspection with a searchable list view.
- **Do** label illustrative scores and keep questions distinct from observed evidence.
- **Do** keep source inspection near the item being reviewed.
- **Do** move bottom-right board chrome with `--dock-offset` and stack the Ask widget on `--minimap-height`, so nothing slides under the review dock or the minimap.
- **Do** use `--focus-ring` for every focus outline on dark chrome.

### Don't:
- **Don't** use amber question styling as proof that a claim is true.
- **Don't** imply that illustrative scores or placeholder hashes are computed results.
- **Don't** rely on the remote font request without the declared system fallbacks.
- **Don't** set workspace headings in Newsreader or add a second `h1` to a case page.
- **Don't** put glass fills or backdrop blur on reading surfaces, source excerpts, evidence cards or the paper canvas.

## Assets

- **Board texture:** `src/assets/paper.webp`, a generated material asset with its exact prompt in the adjacent JSON sidecar. Show it beneath a flat 50% `#eee8de` overlay: visible paper fibers without competing with the evidence. Preserve the surrounding dark interface.
- **`design/workspace-concept.webp`:** an exploratory, generated full-screen board concept from an earlier pass. It is not shipped, and its faces, names, claims and text are not evidence or product truth; only its canvas-and-overlay composition informed the layout.
- **Evidence-card font:** licence and provenance in `public/fonts/README.md`.
