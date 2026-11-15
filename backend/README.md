# MapleTrace backend

Three packages take an uploaded case `.zip` all the way to a cited investigation board:

```
upload.zip ──► mapletrace_ingest ──► case.db ──► mapletrace_reason ──► board.json / analysis.json ──► mapletrace_api ──► frontend
              (ingest, parse,      (immutable    (timeline, links, contradictions,       (FastAPI: upload, status,
               clean, audit)        evidence)     explanations, gaps, next steps,          case, sources, overrides,
                                                  insights, verification)                 new evidence)
```

- **`mapletrace_ingest`:** turns the ZIP into `case.db`. Every row traces back to the exact file and line, row, page or JSON path it came from.
- **`mapletrace_reason`:** the logical reasoning pipeline. It uses traditional ML and rules, plus an optional LangChain deep-agent investigator.
- **`mapletrace_api`:** the HTTP service the frontend calls.

**The backend is authoritative.** `case.db`, `board.json` and `analysis.json` are the source of truth for case data. The frontend's `CaseData` types are a view of that data, not a contract the backend must match. When the two disagree, the frontend adapter changes. See "Backend" in [`AGENTS.md`](../AGENTS.md).

## Quick start

Requires [uv](https://docs.astral.sh/uv/) and Python 3.11+ (3.12 pinned in `.python-version`). The backend is a uv project: dependencies live in `pyproject.toml` (test tools in the `dev` group) and are locked in `uv.lock`. From the repository root, `make backend-install` runs `uv sync --locked` into `backend/.venv`, and `make backend-test`, `make backend-ingest-kestrel`, `make backend-analyze-kestrel` and `make backend-serve` run the steps below. `make dev` also starts the frontend.

By hand, from `backend/` (`uv run` uses the locked environment; the `python -m ...` commands below work the same with `uv run` in front, or with `.venv` activated):

```sh
uv sync                                                     # install from uv.lock (dev group included)
uv run python -m mapletrace_ingest ingest ../cases/kestrel/kestrel_case_upload.zip --out runs/kestrel
uv run python -m mapletrace_reason analyze runs/kestrel     # writes runs/kestrel/analysis/v1/{board,analysis,graph}.json
uv run uvicorn mapletrace_api.app:app --port 8000           # then POST /upload, GET /cases/{id}
uv run python -m mapletrace_ingest verify runs/kestrel      # re-check evidence hashes, DB hash, audit chain
uv run pytest -q                                            # testpaths = tests
uv add <package>                                            # add a dependency (uv add --dev for test tools); commit uv.lock
```

Options for `ingest`:
- `--tz America/Los_Angeles`: time zone for timestamps that don't specify one. Defaults to UTC, or to the time zone named in a submitted manifest.
- `--dayfirst`: read `03/04/2026` as 3 April.
- `--country-code`: country code for local phone numbers.
- `--overwrite`: replace a previous run. It refuses to delete any folder that isn't a previous run.

From Python (as `POST /upload` does):

```python
from mapletrace_ingest.pipeline import ingest_zip
report = ingest_zip("upload.zip", "data/jobs/<job_id>", timezone="America/Los_Angeles")
```

## Output

```
runs/kestrel/
  case.db               SQLite database (schema below)
  evidence/             read-only working copies of every file (nested archives and email attachments included)
  ingest_report.json    coverage report: counts, key entities, manifest check, gaps, per-file decisions
  ingest_summary.md     the same report, human-readable
  run_manifest.json     database SHA-256 + audit-chain head, for `verify`
```

## Results on the Kestrel case

All 57 files parse: about 5,600 records, 5,339 of them timestamped. All 56 `MANIFEST.csv` hashes match.

- **Time basis:** each file's `time_basis` is applied. UTC files stay UTC, and local wall-time files are read as `America/Los_Angeles`. Ortega's "around 11:30 at night" on "Saturday 10/17" resolves to 23:30 PDT.
- **Evidence IDs:** files carry their manifest evidence ID (e.g. `EV-071`), so citations can use `{evidence_id, locator}`.
- **Transcripts:** turns keep the document's own line numbers as `locator.doc_line`, and speakers resolve to full names ("REYES" → "Det. Ana Reyes").
- **Phone exports:** attributed to their custodian, with direction resolving sender and recipient.
- **Calendar and location:** the calendar yields 224 events, and the semantic location history yields 509 visits and movements, with low-confidence items flagged.

`tests/test_formats.py` re-runs Kestrel as a regression test whenever `cases/kestrel/` is present.

## Pipeline

| Stage | What happens | Code |
|---|---|---|
| Intake | Hash the archive. Extract safely: blocks path traversal, links, encrypted members, zip bombs and size limits. Hash every file and make the copies read-only. | `intake.py` |
| Manifest | If `MANIFEST.csv` or `case_manifest.json` is present: check every hash, attach evidence IDs, learn each file's time basis and owner. | `pipeline.py` |
| Classify | Identify the format from content, not the extension, and infer the evidence type. Each decision stores a score table and a plain-language reason. | `classify.py` |
| Extract | One parser per type turns each file into records with locators. Archives and email attachments are re-queued. | `extractors/` |
| Clean | Drop exact duplicate rows, empty rows and invalid coordinates, counted by reason. Flag the same message exported twice via `duplicate_of`. | `extractors/tabular.py`, `pipeline.py` |
| Time | Convert to UTC with an uncertainty window and a flag for every assumption: `tz_assumed`, `day_month_ambiguous`, `am_pm_inferred_from_sequence`, ... | `timeparse.py` |
| Entities | People, phones, emails, devices, samples and accounts. Merges happen only on explicit evidence or unambiguous name forms, and every merge is stored with its rule and confidence. | `entities.py`, `pipeline.py` |
| Report | Totals, time quality, key entities, manifest check and gaps. | `report.py` |

Every step writes to a hash-chained `audit_log`, so editing any entry breaks the chain and `verify` reports it.

## Supported evidence

| Evidence | Formats | Record types |
|---|---|---|
| Messages | CSV/JSON (sender/recipient, or party + direction); WhatsApp-style text exports | `message` |
| Calls / CDR | CSV/JSON, including cell-site lat/lon | `call` |
| Location | CSV/JSON lat/lon (incl. E7), GPX, KML, Google semantic location history | `location_fix`, `place_visit`, `movement` |
| Calendar | iCalendar `.ics` (TZID-aware) | `calendar_event` |
| Contacts | CSV/JSON | `contact` (+ identity links) |
| Photos | JPEG, PNG, TIFF, WebP, HEIC* | `media_capture` + `media` (EXIF time and offset, GPS, device, editing software) |
| Video / audio | MP4, MOV, AVI, MKV, 3GP / WAV, MP3, M4A, FLAC, OGG | `media_capture` + `media` (container time, duration) |
| Statements | TXT, DOCX, PDF | `statement_claim` per sentence, with narrative times resolved |
| Interviews | TXT, DOCX, PDF; `Name:` or `Q:`/`A:` turns; line-numbered transcripts | `interview_turn` with speaker role |
| DNA / lab | STR tables (long or wide), comparison tables, lab report text, FASTA, VCF | `dna_profile`, `dna_comparison`, `lab_finding`, ... |
| Email | EML, mbox; attachments re-ingested | `email` |
| Logs | Any CSV/JSON/JSONL with a time column (badge, LPR, RFID, VMS, cabinet, guard tours, workstation, ...) | `event` |
| Anything else | Any | Hashed and inventoried as `unsupported` |

\* HEIC falls back to the archive timestamp unless a HEIC plugin is installed.

Each record also carries a reliability label:
- `recorded`: a machine logged it.
- `asserted`: a person said it.
- `expert_finding`: a lab concluded it.

## Schema (what the next stages read)

| Table | Purpose |
|---|---|
| `case_info` | Source archive hash, case time zone, pipeline version |
| `evidence_files` | Every file: path, stored copy, SHA-256/MD5, format, inferred type + confidence + reason, parse status, **`external_id`** (manifest evidence ID), manifest row |
| `inferred_schemas` | For tables: columns, column → role mapping, type scores, rows skipped and why |
| `records` | `record_type`, `ts_utc` + `ts_start_utc`/`ts_end_utc`, raw time, precision, flags, actor, target, lat/lon, content, attributes, **`locator_json`**, `record_sha256`, reliability, `duplicate_of` |
| `media` | Capture time and source, GPS, device make/model/serial, dimensions, duration |
| `entities` / `record_entities` | Identifiers and the role each plays in each record; `canonical_id` after resolution |
| `entity_links` | Every identity merge, with its rule, confidence and source record |
| `audit_log` | Hash-chained log of every pipeline action |
| views `timeline`, `entity_cooccurrence` | Inputs for the timeline UI and the graph builder |

A citation for the reasoning layer is `{evidence_id: evidence_files.external_id, locator: records.locator_json}`.

```sql
SELECT ts_utc, record_type, reliability, actor, content, original_path, locator_json FROM timeline;

SELECT actor, content, ts_start_utc, ts_end_utc FROM records
WHERE reliability = 'asserted' AND ts_end_utc >= '2026-10-18T05:00:00Z' AND ts_start_utc <= '2026-10-18T07:00:00Z';
```

## Sample case

`python examples/make_sample_case.py` builds a small fictional case, `examples/harbor_street_case.zip`, used by the tests. Kestrel remains the main demo case.

---

# Reasoning pipeline (`mapletrace_reason`)

```sh
python -m mapletrace_reason analyze runs/kestrel                                   # deterministic, no API key needed
python -m mapletrace_reason analyze runs/kestrel --llm                             # + LLM claim extraction and deep-agent investigator
python -m mapletrace_reason analyze runs/kestrel_v2 --previous runs/kestrel/analysis   # after new evidence: what changed
python -m mapletrace_reason override runs/kestrel <stable_key> dismiss --note "reader under repair"
```

`case.db` is opened read-only. Each run writes a new version, `runs/<case>/analysis/vN/`, containing:
- **`board.json`:** the frontend `CaseData`, plus extra fields.
- **`analysis.json`:** every item with full detail.
- **`graph.json`:** nodes and edges.
- **`analysis.db`:** an items table and an audit log that continues the ingestion audit chain without a break.

## Stages

| Stage | What it does | Method | Code |
|---|---|---|---|
| ML signals (runs first) | Each subject's likely home, work and recurring evening places; days that break a subject's routine; automated/spam vs human messages; name forms that are probably the same person. Each is a cited lead (`ML-xx`) with its model and parameters. Signals are their own kind and are not fed to later stages, so they never change findings, explanations or gaps; they go to the board (`signals`) and to the agent (`list_ml_signals`) | **DBSCAN** (haversine) on location points, **IsolationForest** on daily movement profiles, **TF-IDF + logistic regression** weakly labelled from rules, record linkage with surname blocking + **character TF-IDF agglomerative clustering**. Fixed seeds; no answer key | `ml.py` |
| Connections | Credential → person (from records that list both), account handles → person ("AURION\\rhalvorsen" → Richard Halvorsen), uncertain identity links from ingestion | rules, labelled observed/inferred | `analytics.py` |
| Findings | Repeated co-location; unusual events per log; one person in two places at once; notable communication (deleted messages, saved aliases, late-night contact); unidentified heavy-contact numbers | space-time join, **IsolationForest per log** with feature explanations, strict concurrency rules, pair statistics | `analytics.py` |
| Key events | Groups the strongest findings into episodes. The key moment is where an anomaly and a presence conflict coincide, weighted by how many independent systems recorded them | clustering in time | `analytics.py` |
| Source independence | Recognises the same information repeated: double exports, the same text in several files, reports repeating statements. Corroboration counts independent origins (custodian/system), not records | difflib, shingles | `sources.py` |
| Timeline | One ordered timeline with every uncertain time explained in plain language, silences in logs that normally report often, and people with no recorded whereabouts around a key event | | `timeline.py` |
| Claims | Whereabouts, "never been there", "haven't talked to X in weeks" → structured claims with time windows (from the sentence, the incident date in the header, or the key event, always stated as an assumption) | rules (+ LLM structured output with `--llm`) | `claims.py`, `llm.py` |
| Contradictions | Statement vs records, and record vs record. Each lists conflicting and consistent records, several possible reasons (approximate memory, shared credential, clock or time-zone error, phone away from its owner, untruth as one option) and the evidence that would resolve it | | `contradictions.py` |
| Competing explanations | For each key event: present / someone else used the credential / an associate took part / system error. Each is scored from supporting and contradicting records, weighted by directness and capped by independent origins. Returns "insufficient evidence to choose" rather than forcing a verdict, and names the evidence that would tell the explanations apart | | `hypotheses.py` |
| Gaps | Directed questions the data can't answer (who was physically there, where was X, who uses this number, is this account accurate, which explanation fits, what does this unreadable file contain). Each has a type: **missing**, **failed extraction**, **conflicting** or **uncertain** | | `gaps.py` |
| Next steps | Ranks evidence to obtain by gaps closed, how well it separates explanations, urgency (retention windows), whether it adds an independent kind of source, and speed. Each comes with a concrete request (person, time, place) and the reasons for its rank | | `recommend.py` |
| Insights | Observations (cited) kept apart from inference, unknowns, counter-evidence, assumptions and limitations. Confidence is a label (low/medium/high) set by independent sources, and never stated as certainty | | `insights.py` |
| Verification | Every citation must resolve to a record in an evidence file whose SHA-256 still matches. Uncited items are dropped and logged. Accusatory wording is softened, and protected attributes are stripped | | `verify.py` |
| Overrides and versions | Investigator corrections in `overrides.jsonl` are applied on every run and never deleted (the machine result is kept alongside). With `--previous`, gaps are marked resolved, partially resolved or reopened, and every change is listed with its reason | | `history.py` |

On Kestrel (about 4 seconds, no LLM), the analysis finds:
- **Key event:** Saturday 22:51 at the briefing-room cabinet.
- **Leading explanation:** someone else used Richard Halvorsen's credential while his workstation was active (`AURION\rhalvorsen`, linked by account handle).
- **Plausible explanation:** an associate using +1-408-555-0147, a number with 116 contacts and repeated co-location but no name in the evidence.
- **Verdict:** insufficient evidence to choose between them.
- **Contradiction:** Halvorsen's "at home, a quiet night" against his phone's location history.
- **Top next steps:** CCTV of the cabinet area, DNA and fingerprints, carrier location records, a phone extraction, and analysing the four videos already in the case.

## LLM layer (`--llm`)

Set `ANTHROPIC_API_KEY` in your environment; never commit it. With `--llm`:
- **Claim extraction:** `claude-sonnet-5-5` (set `MAPLETRACE_LLM_MODEL` or `--model` to change) extracts claims from each statement and interview using structured output (`method="json_schema"`, since Sonnet 5.5 rejects forced tool use). Every claim must cite a sentence ID from that document; invented IDs are discarded.
- **Investigator:** a deepagents agent (`deepagents` 0.7.x) gets read-only tools (`list_explanations`, `list_open_questions`, `list_ml_signals`, `search_records`, `get_record`) and two guarded writers:
  - `record_insight` rejects insights without valid record IDs, and downgrades "high" to "medium" with fewer than three independent sources.
  - `answer_question` can mark a gap partially resolved, never resolved.
- **Verifier subagent:** `claude-sonnet-5-5` checks citations.
- **Audit:** every model call and tool call is written to the audit log.
- **Sandboxing:** the agent runs in deepagents' in-memory sandbox, with no file system or shell access.
- **Labelling:** agent output is marked `generated_by: agent:<model>` and `inferred`.

### Cached LLM results

One deep analysis of Kestrel costs about $1.30 with `claude-sonnet-5-5`; replays are free. [LLM_COSTS.md](LLM_COSTS.md) has the breakdown and the chat estimate.

Model calls cost money, so responses are recorded per uploaded archive in `backend/llm_cache/<archive sha256>.jsonl`, keyed by a hash of each request. These files are committed.
- **Replay:** an upload whose archive matches a cache file replays it automatically, even without the `llm` flag. It needs no API key and never calls the API: a miss raises before any request is sent, the failed call is logged, and the deterministic analysis continues.
- **Record:** `--llm` (CLI) or `llm=true` (upload) reuses cached responses and records the ones it lacks. Those calls are billed.
- **CLI:** `--llm-cache record|replay|off` (default `record`).
- **Demo snapshot:** `backend/demo/kestrel.tar.gz` holds the finished Kestrel case, including the replayed LLM results. `POST /demo` installs it as case `kestrel-demo`, which is instant and makes no model calls, and writes the snapshot's SHA-256 to `demo_snapshot.sha256` in the case folder. It reinstalls when that hash no longer matches the committed snapshot or a version lacks its `trace.jsonl` (installs from before the run trace never replayed), carrying `overrides.jsonl` over and re-applying it. The snapshot omits the uploaded ZIP; `POST /demo` restores it from `cases/kestrel/` after checking its hash.
- **Rebuilding:** `make backend-llm-record` makes one billed run that records responses for the Kestrel ZIP. `make backend-demo-snapshot` rebuilds the snapshot by replaying the cache, and refuses if any response is missing. Both go through the same code path as `POST /upload`, so their requests match later uploads of the same archive.
- **When to re-record:** changing prompts, tools, model settings or anything in the analysis that the model sees changes the request hashes, so record again and rebuild the snapshot. The names, docstrings (whitespace included) and outputs of the tools in `llm.read_tools` are part of the request, and chat uses the same tools, so editing them invalidates both caches.

### Case chat

`mapletrace_reason/chat.py` answers an investigator's questions about the latest analysis of a case; `mapletrace_api/chat.py` serves it. [`frontend/CHAT.md`](../frontend/CHAT.md) is the HTTP contract and describes citations, threads, suggested questions and errors; this section covers the implementation.
- **Model and tools:** `claude-sonnet-5-5` (`MAPLETRACE_CHAT_MODEL`, falling back to `MAPLETRACE_LLM_MODEL`; medium reasoning effort) with the investigator's read-only tools (`llm.read_tools`), plus `list_items` and `get_item` over the finished analysis. It ends with `submit_answer`; at most 10 model calls per answer.
- **Citations:** come from `case.cite()`; `source_id` is set only when the citation is in the board's `sources`.
- **Cost control:** responses are cached in `backend/llm_cache/chat-<archive sha256>.jsonl`, keyed by the full request, so the same question in the same thread state replays for free. With `ANTHROPIC_API_KEY` the cache records; without it only recorded answers are served, and a miss returns `503 needs_api_key` before anything is sent. Prompts hold no case name, time or random ID.
- **Recording:** `make backend-chat-record` installs the demo snapshot in a temporary folder and records the answers to its suggested questions (billed). `python -m mapletrace_api.chat suggestions` lists them and whether each replays, without calling the API.
- **Audit:** chat reads the finished analysis and is not written to the case's audit log.

## API (`mapletrace_api`)

```sh
uvicorn mapletrace_api.app:app --port 8000      # CORS allows localhost:5173 and 127.0.0.1:5173 (MAPLETRACE_CORS to change)
```

| Method | Path | Purpose |
|---|---|---|
| POST | `/upload` (multipart `file`, optional `case_name`, `timezone`, `llm`, `analysis_mode=replay\|live`) | New case → `{jobId, caseId}`. Ingestion and analysis run in the background (100 MB limit) |
| GET | `/status/{jobId}` | `{status: processing \| ready \| failed, progress, stage, message, caseId}` |
| GET | `/case` | Latest ready case as `CaseData` (drop-in for the frontend's `getCase()`) |
| GET | `/cases`, `/cases/{caseId}` | List cases; one case as `CaseData` |
| GET | `/cases/{caseId}/{section}` | `graph`, `gaps`, `insights`, `suggestions`, `contradictions`, `explanations`, `timeline`, `audit`, `changes`, `sources`, `uncertainTimes`, `missingPeriods`, `sourceGroups`, `signals` |
| GET | `/cases/{caseId}/source?id=EV-071:seq=40162` | One cited record in full (source inspector) |
| GET | `/cases/{caseId}/evidence/{evidenceId}` | The original evidence file (read-only copy), as an attachment. `?inline=true` renders images, video, audio and PDF in place; other formats stay attachments (`nosniff`, sandboxed) |
| GET | `/cases/{caseId}/evidence/{evidenceId}/view?locator=&offset=&limit=` | The stored copy in a viewable form, with a citation resolved to a position. `locator` is the label after `EV-xxx:` in a source ID (`event_id=BDG-000615`, `row=71`, `line=14`). Returns file metadata (`sha256`, `bytes`, `format`, `evidenceType`, `parseStatus`, `manifestMatch`, `recordCount`), `kind` (`table` \| `text` \| `json` \| `document` \| `image` \| `video` \| `audio` \| `pdf` \| `binary`), `mediaType`, `notes`, and one window: `table: {columns, total, offset, limit, items: [{row, line, cells}]}` (row numbers as ingestion counts them: header row 1) or `lines: {unit: line \| paragraph, total, offset, limit, items: [{n, text, label?, truncated?}]}`. `target: {locator, resolved, recordIds, sharedRecordIds, locators, ranges: [{start, end, colStart?, colEnd?}], sharedRanges, page, whole, note?}` gives 0-based item ranges taken from each record's `locator_json`; without `offset` the window opens around the first range. When records share a label, the board source excerpt picks the cited one and the rest are `sharedRanges`. `limit` 1–5000 (default 1000); lines are capped at 4,000 characters. JSON is pretty-printed (`pretty: true`), so its line numbers refer to the rendering |
| GET | `/cases/{caseId}/files` | Evidence inventory from the latest ingestion: `[{evidenceId, fileId, path, filename, sha256, bytes, format, sniffedFormat, evidenceType, parseStatus, recordCount, manifestMatch (bool or null when the manifest lists no hash), origin, title}]` |
| GET | `/cases/{caseId}/records?evidenceId=&recordType=&limit=&offset=` | Normalized ingestion records, read-only: `{total, limit, offset, types: {recordType: count}, items: [{id, recordType, fields, citations: [{evidenceId, locator, sourceId?}]}]}`. `fields` holds flat scalars (`ts_utc`, `ts_start_utc`/`ts_end_utc`, `ts_raw`, `ts_precision`, `ts_flags`, `actor`, `target`, `lat`, `lon`, `content`, `reliability`, `duplicate_of`, then scalar attributes; protected attributes are never returned). `sourceId` is present only when the record is cited on the board. `types` counts record types within the file filter (ignoring `recordType`). `limit` 1–500 (default 100) |
| GET | `/cases/{caseId}/audit-chain` | `{verified, head, checks: [{source, ok, message}], entries: [{seq, time, stage, action, fileId, detail, hash, prevHash, source: ingest \| analysis}]}`. `verified` re-runs `mapletrace_ingest verify` (database hash, chain, evidence hashes), checks the analysis chain continues from the ingestion head, and checks the board/analysis outputs against their logged hashes |
| POST | `/cases/{caseId}/evidence` | Add a ZIP of new evidence. Re-ingests everything as a new version and reports what changed |
| POST | `/demo` | Install the committed Kestrel snapshot and return `{caseId}` (`404 no_demo_snapshot` if it is missing). Reused until the snapshot changes; a stale install is replaced, keeping its `overrides.jsonl` (then `jobId` names the re-analysis that re-applies them) |
| GET | `/health` | Liveness check (used by Docker); `llmLive` is true when a server API key allows `analysis_mode=live` |
| GET | `/cases/{caseId}/trace?after=N` | Run trace events (ingestion and analysis) with a replay clock, readable while the job runs: `{status, timing, events, next}`. See [`TRACE.md`](TRACE.md) |
| GET | `/chat/status?case_id=` | Case chat availability, mode (`live` with a key, `replay` without) and suggested questions with a `recorded` flag. See [`frontend/CHAT.md`](../frontend/CHAT.md) |
| POST | `/cases/{caseId}/chat` (`{message, thread_id?}`) | Cited answer `{thread_id, message: {role, content, evidence_status, citations, summary, observations, inference, unknowns}, suggested, replayed, model_calls}`. `503 needs_api_key` when the answer is not recorded and no key is set. See [`frontend/CHAT.md`](../frontend/CHAT.md) |
| GET / POST | `/cases/{caseId}/overrides` | Read or record investigator corrections (`dismiss`, `confirm`, `set_status`, `set_label`, `note`, `reject_link`) |

Errors are always `{"error": {"code", "message"}}`. Uploads are capped at `MAPLETRACE_MAX_UPLOAD_MB` (default 100). The LLM model is `MAPLETRACE_LLM_MODEL` (default `claude-sonnet-5-5`). Case data lives under `$MAPLETRACE_DATA/cases/<caseId>/` (default `backend/data/`): uploads, numbered ingestion and analysis versions, and `overrides.jsonl`.

### Board fields

`board.json` is the frontend's `CaseData` plus these fields. The frontend types most of them; it does not yet use `timeline`, `changes` or `overrides`.
- **`nodes[].certainty` / `edges[].certainty`** (`observed` | `inferred`), plus `edges[].basis`.
- **`nodes[].citations`** are never empty: entity and place nodes cite the records behind their threads (or, failing that, records that name them), up to 12.
- **`edges[].directed`:** `true` for person → statement "stated", statement → event "conflicts with", event → place "occurred at" and person → event "recorded at"; `false` for communication, co-location and identity. `source` → `target` follows the direction.
- **`gaps[].nodeIds`:** board nodes the gap concerns (its affected hypotheses, findings, contradictions and missing periods resolved to episode, person, statement and record nodes, plus event/statement nodes citing the gap's records). **`nodes[].gapId`** is the highest-scoring gap that concerns the node.
- **`timezone`:** the case's IANA time zone (`case_info.assumed_timezone`), or `UTC`.
- **`gaps[]`:** `gapType`, `status`, `direction`, `missing`, `whyItMatters`, `answer`, `previousStatus`, `key`.
- **`insights[]`:** `certainty`, `confidence`, `observations[]` (each cited), `inference`, `unknowns`, `counterevidence`, `assumptions`, `limitations`, and `explanations` for verdict insights.
- **`suggestions[]`:** `gapIds`, `artifact`, `score`.
- **Top-level:** `contradictions`, `explanations`, `timeline`, `uncertainTimes`, `missingPeriods`, `sourceGroups`, `changes`, `overrides`, `signals` (ML leads: `type`, `method`, `score`, `certainty`, `citations`).
- **Provenance:** every node and edge has `origin` (`record` \| `rules` \| `ml` \| `llm` \| `agent`), `stage` and `evidenceIds`; `insights[]` and `signals[]` carry `origin`. ML signals (except identity clusters, which are threads between people) and agent insights are inferred nodes (`sig-<key>`, `ins-<key>`, with `itemId`) joined by `inference` edges to the nodes they share citations with.
- **`key`:** every item has a stable key, which is what overrides target.
- **Readable titles:** nodes may carry `displayLabel` (at most 44 characters), `displaySummary` and `labelOrigin` (`rules` \| `llm`); `sources[]` carry `fileLabel` (the MANIFEST.csv title). Presentation only; `label` and `summary` are unchanged. See [LABELS.md](LABELS.md).

## Not done yet
- **Content analysis:** OCR, speech-to-text and vision on media. Videos are flagged as "failed extraction" gaps with a "analyse video already in the case" next step.
- **Cleaning rules from the plan:** reader clock drift correction, plate edit distance, message noise classifier, RFID single misses.
- **Scorer:** an evaluation against the locally generated answer key (`make data-truth`).
- **Not parsed yet:** XLSX, phone backup SQLite databases, disk images. They're hashed and listed as `unsupported`.

## Photos and video

Every `media` row becomes an observed board card with rule-backed links (`mapletrace_reason/media.py`, stage
`media_links`); see [MEDIA.md](MEDIA.md). With `--llm`, `mapletrace_reason/vision.py` adds neutral image descriptions
to those cards from the separate cache `llm_cache/vision-<archive sha256>.jsonl` (replay-only without a key; frame
extraction needs an `ffmpeg` binary and only runs when recording; never install PyAV, which changes deepagents' `read_file` tool description and so the investigator cache key). Descriptions never reach claims, gaps, insights or the
investigator. `make backend-vision-record` (billed) records only that cache and rebuilds the snapshot.
Links come from cited rules only: the VMS export index, EXIF capture device and GPS, the MANIFEST.csv custodian and
title, and the facility directory (camera room, and events on the camera's floor during a clip).

## Readable titles

`mapletrace_reason/labels.py` gives cards a short `displayLabel` and, for raw `key=value` records, a plain
`displaySummary`, from the facility directory, MANIFEST.csv titles, saved contact names and explicit entity links;
sources get a `fileLabel`. With an LLM config, `mapletrace_reason/label_llm.py` replays optional model-written titles
(`claude-haiku-5-5`) for cards the rules leave unreadable from `llm_cache/labels-<archive sha256>.jsonl`, skipping
silently when there is none; they are display-only (`labelOrigin: "llm"`) and never reach any finding or model input.
`make backend-label-record` (billed) records them and rebuilds the snapshot. See [LABELS.md](LABELS.md).
