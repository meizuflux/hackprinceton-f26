# Photos and video on the board (contract)

Shared by the backend and the frontend. Field names on the wire are camelCase. Extends `backend/TRACE.md`.

## Media cards (deterministic)

Every ingested photo and video (a row in `case.db` `media`) becomes a board node:

- `type`: `event` (a capture is a moment in time); `certainty`: `observed`; `origin`: `record`; `stage`: `ingest`;
  `evidenceIds`: `[<its evidence ID>]`; `citations`: the media record's citation (e.g. `EV-022:<locator>`).
- `label`: a short human title (e.g. "CCTV clip · P2 garage (CAM-E-P2-02)" or "Photo · csu_001.jpg");
  `time`: capture time (UTC ISO) when known.
- `media`: `{evidenceId, kind: "photo"|"video", mediaType, capturedUtc, captureSource, timeFlags: [...],
  durationS, width, height, deviceMake, deviceModel, gps: {lat, lon} | null}`, straight from the `media` table.

- `displayLabel` (rules, see `LABELS.md`): the camera's directory name and the clip's local time span ("Garage P2
  camera · 21:35–21:38") or the photo's `MANIFEST.csv` title ("EBC cabinet SC-EBC-01, empty ES-0007 slot").

Edges join a media card to other cards only through cited records, with `origin: "rules"`, `stage: "media_links"`,
`directed: false`, a `rule` and a `basis` that starts with the rule name. `vms_export`, `capture_device` and
`custodian` are `observed`; the rest are `inferred`:

- `vms_export`: a video's clip file named in `vms_export_index.csv` (or any record whose attributes name the
  clip file) joins the clip to the camera card for that `camera_id` (the camera's device entity, `ent-<id>`; created
  with `stage: "media_links"` when the board has none), citing the export row.
- `capture_device`: a photo's EXIF device joins the card of the same entity, or of an entity explicitly linked to it
  (via `entity_links`). When no such card exists, photos that record the same EXIF device entity share one new
  device card (exact entity match, never fuzzy). Kestrel has no device links, so it uses the shared card.
- `place`: a photo's GPS that falls within 150 m of the centre of a place cluster already on the board (an ML
  `place_cluster` card, `sig-...`; the other location cards carry no coordinates) joins the photo to that location, citing both records; `certainty: "inferred"` (a GPS radius is an
  inference), `basis` gives the distance.

- `custodian`: the file's `MANIFEST.csv` custodian is, by exact name, a person card on the board ("collected from").
  Cites the media record and the person card's first citation. Kestrel: the four camera-roll photos join Richard
  Halvorsen.
- `camera_place`: the clip's camera (from `vms_export`) is placed in a room by the facility directory (a reference
  list with `id`, `kind`, name, floor and room per row, Kestrel's `doors_readers.csv`); the clip joins location cards
  named after that room or naming a directory entry in it ("filmed in"). Cites the media record, the directory row
  and the location card. Kestrel: the lobby clip joins "Lobby", both P2 clips join "Garage P2".
- `title_place`: the `MANIFEST.csv` title names a directory ID or room as a whole word ("Scene photo: EBC cabinet
  SC-EBC-01, ...", "... P2 elevator lobby door ..."); the media card joins the location cards for it ("pictured at").
  A room inside a longer matched room is not counted twice. Cites the media record, the directory row and the
  location card.
- `same_place_time` ("same place, nearby time"): an event card (a key event or unusual event, from its own records)
  has a record on the camera's floor, per the directory, within 60 s of the clip's span. Label "same floor, during
  clip" or "same room, during clip". Cites the media record, the event record, and the directory rows for the camera
  and the event's place. Kestrel: the 21:35 P2 clip joins the held P2 elevator lobby door (BDG-000615, 21:36:49) and
  the key event that includes it.

Edge `type` is `temporal` for `vms_export`, `capture_device`, `custodian` and `same_place_time`, and `spatial` for
`place`, `camera_place` and `title_place`. A pair of cards gets at most one edge of each type (the first rule wins).
None of the rules use vision descriptions. Media cards sit in their own backend layout column. Each edge must cite
records on both ends. Media with no rule-backed link still appears as a card, unconnected (Kestrel: the visitor kiosk
photo). Media edges never pull cards into the opening story (`board.story`), so media stays one click away.
`stage_finished` with `stage: "media_links"` is written to the trace after the rules stages.

## Image description (LLM, optional, isolated)

With `--llm`, stage `media_vision` sends each photo and a few frames per video (fixed times: 10%, 50%, 90% of the
duration) to the model and asks for a neutral, literal description: visible objects, text, people (no
identification of real people, no protected attributes, no guesses about identity or intent).

- Output per media file: `media.vision = {text, observations: [{text, frameS | null}], model, origin: "llm",
  certainty: "inferred"}`, attached to the media card. It cites the media record (with `frameS` for video frames).
- Isolation: like ML signals, vision output is never fed to claims, contradictions, explanations, gaps, insights or
  the investigator agent, so the existing recorded investigator and chat caches stay valid. A test checks this.
- One request per image (a photo, or a frame at 10/50/90% of the duration); `media.vision.text` joins the frame texts
  and `citations` holds the media record's citation. Misses skip that image with a flag in `analysis.json`
  `llm.vision`; the run never fails. `make backend-vision-record` records only this cache.
- Cache: a separate file `backend/llm_cache/vision-<archive sha256>.jsonl` keyed explicitly on (evidence sha256,
  frame time, prompt text, model), not on decoded image bytes, so a replay never needs to decode video. Recording
  needs an `ffmpeg` binary for video frames; replay needs neither. Do not install PyAV (`av`) in the backend venv: it changes deepagents' `read_file` tool description and so the investigator cache key.
- Trace: one `llm_call` per request with `purpose: "media_vision"` (TRACE.md fields), and `stage_finished` for
  `media_vision`.

## Frontend

- Cards with `media` show a thumbnail: photos via `evidenceFileUrl(..., {inline: true})` in an `<img loading="lazy">`,
  videos via `<video preload="metadata" muted>` at a poster time. Clicking opens the source panel, whose top shows
  the photo or a playable clip, then metadata, then the vision description (labelled as an LLM description, inferred,
  with its citation) when present.
- The replay reveals a media card when its file is parsed, as for other record cards.
