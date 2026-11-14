# Mapletrace backend: evidence ingestion

Turns an uploaded case `.zip` into one SQLite database, `case.db`. Every row can be traced back to the exact file and line, row, page or JSON path it came from. This is stages 1–3 of [`docs/IMPLEMENTATION_PLAN.md`](../docs/IMPLEMENTATION_PLAN.md) (ingest, parse, clean). The ML, graph and reasoning stages read from `case.db`.

```
upload.zip ──► mapletrace_ingest ──► case.db (+ ingest_report.json) ──► ML / graph ──► deep agents ──► API ──► frontend
```

**The backend is authoritative.** The schema in `case.db` and the report it writes are the source of truth for case data. The frontend's `CaseData` types and fixtures are a view of that data, not a contract the backend must match. When the two disagree, the frontend adapter changes. See "Backend authority" in [`AGENTS.md`](../AGENTS.md).

## Quick start

Requires Python 3.11+. From `backend/`:

```sh
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt           # macOS/Linux: .venv/bin/pip

python -m mapletrace_ingest ingest ../cases/kestrel/kestrel_case_upload.zip --out runs/kestrel
python -m mapletrace_ingest verify runs/kestrel             # re-check evidence hashes, DB hash, audit chain
python -m pytest -q tests
```

Or, from the repository root: `make backend-install`, `make backend-test`, `make backend-ingest-kestrel`.

Options for `ingest`:
- `--tz America/Los_Angeles`: time zone for timestamps that don't specify one. Defaults to UTC, or to the time zone named in a submitted manifest.
- `--dayfirst`: read `03/04/2026` as 3 April.
- `--country-code`: country code for local phone numbers.
- `--overwrite`: replace a previous run. It refuses to delete any folder that isn't a previous run.

From Python (for the future `POST /upload` handler):

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

All 57 files parse: 5,609 records, 3,106 of them on the timeline. All 56 `MANIFEST.csv` hashes match.

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

`python examples/make_sample_case.py` builds a small fictional case, `examples/harbor_street_case.zip`, used by `tests/test_ingest.py`. Kestrel remains the main demo case.

## Not done yet (next workstreams)
- **API:** a FastAPI service (`POST /upload`, `/status`, ...) wrapping `ingest_zip`.
- **Frontend adapter:** maps `case.db` → `CaseData`.
- **Content analysis:** OCR, speech-to-text and vision on media.
- **Cleaning rules from the plan:** reader clock drift, plate edit distance, message noise classifier, RFID single misses. The raw facts they need (`attributes`, `locator`, time flags) are already stored.
- **Not parsed yet:** XLSX, phone backup SQLite databases, disk images. They're hashed and listed as `unsupported`.
