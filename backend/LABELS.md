# Readable card titles (contract)

Shared by the backend and the frontend. Field names on the wire are camelCase. Additive only: `label`, `summary` and
every other existing field are unchanged, so search, the LLM tools and the recorded caches see exactly what they saw
before.

## Fields

Board nodes (`board.json` and `GET /cases/{caseId}`) may carry:

- `displayLabel: string`: a short human title, at most 44 characters. Absent when no readable title can be derived;
  the frontend then falls back to `label`.
- `displaySummary: string`: a plain-English version of `summary` (at most 400 characters), mainly for record cards
  whose `summary` is raw `key=value` text. Absent when `summary` already reads well.
- `labelOrigin: "rules" | "llm"`: present whenever either field is. `rules` is deterministic; `llm` is inferred,
  display-only text from the optional label cache below and must be shown as such.

Sources (`sources[]`) carry `fileLabel: string`: a human name for the evidence file, the file's `MANIFEST.csv`
`title` (for example "Building E badge access events"), else its type and file name. The frontend can show
"Building E badge access events · event_id=BDG-000615" instead of "EV-070:event_id=BDG-000615".

## Rules (`mapletrace_reason/labels.py`, deterministic)

Labels restate what the case's own records say; they never add a place, person or fact.

- **Facility directory:** a reference-list file whose rows each have an `id`, a `kind` and a name (Kestrel's
  `doors_readers.csv`, EV-077) maps IDs to names, floors and rooms. Only exact ID or exact (case-insensitive) name
  matches resolve. `SC-EBC-01` becomes "Secure demo cabinet · EBC 4-12"; long names are cut at their first qualifier
  ("Garage P2 camera covering elevator lobby door, ..." becomes "Garage P2 camera").
- **Record cards** (unusual events, `rec-` cards): the event code in words plus the directory place: "Auth attempt ·
  Secure demo cabinet", "Tag ES-0007 in cabinet · EBC 4-12", "Checkpoint scan: All secure · Lobby". `displaySummary`
  is one sentence with the remaining fields in words, followed by the existing "Flagged because ..." text.
- **Key events:** "Sat 17 Oct 22:51 at Secure demo cabinet" (case time zone); the summary names directory IDs.
- **Phones:** formatted (+1 408-555-0147). When every message the number sent carries one saved contact name
  (`party_name` in a message extraction), "Phone · Vince (Supply)", with a summary that says where the name is saved.
  A saved contact name is not an identity: it never merges entities or changes findings.
- **People:** all-caps forms are put in reading order ("CHEN, ANDREW" -> "Andrew Chen"). A surname joined to one
  fuller name by an explicit `entity_links` row (for example `unique_surname`) reads "Halvorsen (likely Richard
  Halvorsen)", and the summary names the link and its confidence. The two cards stay separate.
- **Accounts:** "SMS sender · PROMO" when the sender's messages name one service.
- **Cameras and media:** camera cards use the directory name; a clip reads "Garage P2 camera · 21:35–21:38"; a photo
  uses its `MANIFEST.csv` title ("EBC cabinet SC-EBC-01, empty ES-0007 slot", "Restaurant table · Halvorsen iPhone").
  Media labels never use vision descriptions.

## Optional LLM labels (`mapletrace_reason/label_llm.py`, inferred)

For cards still hard to read after the rules (no rules `displayLabel` or `displaySummary`, and a `label` over 44
characters, with `key=value` text or an event code; in Kestrel today mostly ML signal, agent insight and statement
cards), a cheap model (default `claude-haiku-5-5`, `label_model` in the LLM config) writes a title and
one sentence from the card's own `type`, `subtitle`, `label`, `summary` and up to three cited excerpts. Media cards are
never sent.

- Output sets only `displayLabel`, `displaySummary` and `labelOrigin: "llm"` on that card. Rules labels are never
  overwritten. Replies are rejected when the title is over 44 characters or a number in them is not in the card data.
- Isolation: labels are applied after the board is built and are never read by claims, contradictions, explanations,
  gaps, insights, the investigator, chat or vision; none of their inputs or prompts change. `tests/test_label_llm.py`
  checks this.
- Cache: `backend/llm_cache/labels-<archive sha256>.jsonl`, keyed on (card input, prompt, model). The stage replays
  only, needs no key, and is skipped silently when the file is absent (as for Kestrel today). Recording is explicit:
  `make backend-label-record` (billed; needs `ANTHROPIC_API_KEY`) replays the analysis cache, records only the labels
  and rebuilds the demo snapshot.
- Trace: one `llm_call` per card with `purpose: "display_labels"` and `stage_finished` for `display_labels`, only when
  the cache exists. The trace cost uses the Sonnet price table in `llm_cache.py`, so it overstates a Haiku run.
