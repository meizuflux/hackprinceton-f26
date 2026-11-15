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

Edges join a media card to other cards only through cited records, with `certainty: "observed"`, `origin: "rules"`,
`stage: "media_links"` and a `basis` that names the rule:

- `vms_export`: a video's clip file named in `vms_export_index.csv` (or any record whose attributes name the
  clip file) joins the clip to the camera/location card for that `camera_id`, citing the export row.
- `capture_device`: a photo's EXIF device that matches an explicitly linked device/person entity (via
  `entity_links`) joins the photo to that card. No fuzzy matching.
- `place`: a photo's GPS that falls inside a location the analysis already clusters (an existing location card with
  coordinates) joins the photo to that location, citing both records; `certainty: "inferred"` (a GPS radius is an
  inference), `basis` gives the distance.

Each edge must cite records on both ends. Media with no rule-backed link still appears as a card, unconnected.
`stage_finished` with `stage: "media_links"` is written to the trace after the rules stages.

## Image description (LLM, optional, isolated)

With `--llm`, stage `media_vision` sends each photo and a few frames per video (fixed times: 10%, 50%, 90% of the
duration) to the model and asks for a neutral, literal description: visible objects, text, people (no
identification of real people, no protected attributes, no guesses about identity or intent).

- Output per media file: `media.vision = {text, observations: [{text, frameS | null}], model, origin: "llm",
  certainty: "inferred"}`, attached to the media card. It cites the media record (with `frameS` for video frames).
- Isolation: like ML signals, vision output is never fed to claims, contradictions, explanations, gaps, insights or
  the investigator agent, so the existing recorded investigator and chat caches stay valid. A test checks this.
- Cache: a separate file `backend/llm_cache/vision-<archive sha256>.jsonl` keyed explicitly on (evidence sha256,
  frame time, prompt text, model), not on decoded image bytes, so a replay never needs to decode video. Recording
  needs frame extraction (`av`/PyAV or an `ffmpeg` binary); replay needs neither.
- Trace: one `llm_call` per request with `purpose: "media_vision"` (TRACE.md fields), and `stage_finished` for
  `media_vision`.

## Frontend

- Cards with `media` show a thumbnail: photos via `evidenceFileUrl(..., {inline: true})` in an `<img loading="lazy">`,
  videos via `<video preload="metadata" muted>` at a poster time. Clicking opens the source panel, whose top shows
  the photo or a playable clip, then metadata, then the vision description (labelled as an LLM description, inferred,
  with its citation) when present.
- The replay reveals a media card when its file is parsed, as for other record cards.
