# Compstat backend: implementation plan (proposal)

> **Status: proposal.** [`SPEC.md`](../SPEC.md) stays the single product spec. Items that SPEC lists as open
> decisions (provider, hosting, backend schema) are marked **Proposed** here and need team agreement.
> Case data: [`cases/kestrel/`](../cases/kestrel/README.md), built by [`generator/`](../generator/README.md).

## 1. Who it is for, with real numbers

**Primary buyer: insurance Special Investigations Units (SIUs).** Secondary: police and corporate investigators.

| Figure | Source |
| --- | --- |
| Insurance fraud costs the US **$308.6B a year** | Coalition Against Insurance Fraud, Aug 2022 (still the current estimate) |
| SIU staffing grew **0.5%** 2022-2024; each investigator handles **174** accepted referrals a year | Coalition/Aon 2024 SIU Benchmarking Study (reported by ClaimsPages, Nov 2026) |
| Automated tools produce **45%** of SIU referrals but only **36%** are accepted, vs **70%** for adjuster referrals | Same study. Opaque flags get ignored; explained, cited leads are the opening |
| US clearance rates (2025): property crime **17.4%**, larceny-theft **18.6%**, violent crime **47.4%** | FBI, Reported Crimes in the Nation 2025 (Aug 2026) |
| Digital evidence in about **9 in 10** cases; **69%** of investigators lack time to review all of it; median lab backlog **3-4 weeks** | Cellebrite 2025 Industry Trends Survey (vendor survey) |
| Investigators spend about **10 h/week** reviewing video, **9 h** texts, **8 h** photos | Cellebrite 2019 survey via Route Fifty |
| 2025 US cargo theft losses about **$725M** (+60%), **$273,990** average per theft; thieves shifting to enterprise computing hardware | CargoNet / Verisk, Jan 2026 |
| Insiders involved in **22%** of cargo thefts globally | TT Club / BSI 2025 Cargo Theft Report (Apr 2026) |
| Trade-secret theft costs the US **$180B-$540B a year** | IP Commission 2017 update |
| First AI-related economic-espionage conviction (TPU/GPU designs) | US v. Linwei Ding, DOJ, Jan 2026 |

The demo case speaks the insurer's language: claim **LSI-CC-26-009812** ($1.15M, commercial crime policy)
turns on whether an officer took part (officer-knowledge exclusion). Compstat answers with cited evidence
and a ranked list of what to obtain next (gap G-09).

Before pitching, re-check the secondhand figures (the 2024 SIU study is members-only). Do not claim accuracy
or time savings until we measure them.

## 2. Architecture

```
upload.zip
  -> 1 Ingest      unpack read-only, SHA-256 every file, check against MANIFEST.csv, audit entry
  -> 2 Parse       one parser per format -> typed events, each with {evidence_id, path, sha256, locator}
  -> 3 Clean       time to UTC, dedupe, clock skew, OCR misreads, spam, low-confidence points (all logged)
  -> 4 ML          co-location clustering, anomaly detection, entity resolution, NER + claim extraction
  -> 5 Graph       nodes and edges with citations -> graph.json on disk
  -> 6 Reason      deepagents: directed questions -> answers with citations, or gaps + next artifacts
  -> 7 Verify      every citation must resolve to source text; uncited claims are dropped
  -> 8 API         /upload /status /graph /gaps /insights /audit /source -> React board
  audit.jsonl      append-only and hash-chained, written at every step
```

Each job lives in `data/jobs/<job_id>/`: `original/` (read-only), `events.parquet`, `cleaning_report.json`,
`graph.json`, `analysis.json`, `audit.jsonl`. The filesystem is the source of truth, as SPEC describes.

## 3. Workstreams

Each workstream can be built in parallel against the Kestrel data. The repo holds no answer key; acceptance
criteria use the local one from `make data-truth` (`.truth/kestrel/`, git-ignored, never model input).

### WS0 Data and evaluation (generator done; scorer next)
- Done: deterministic generator, 56 evidence files, labels, `make data-verify`.
- Next: `eval/score.py` compares a pipeline run with the local answer key:
  - facts recovered with the correct locator
  - insights matched (supporting-fact overlap; optionally an LLM judge)
  - gaps found, and how well the artifact ranking matches `artifact_value.json`
  - red herrings cleared
  - bias trap RH-03 not flagged
  - citation validity
- Training variants: `python generator/generate.py --seed <s> --out <dir>` (same facts, different noise).

### WS1 Ingestion service (`backend/`, FastAPI, Python 3.11+)
- `POST /upload` (ZIP up to 100 MB, matching the frontend limit) returns `jobId`; the work runs as a background task.
- Unzip safely: no paths outside the job folder, size and count limits. Hash every file; compare with `MANIFEST.csv` if present.
- Parsers, all emitting `Event(time_utc, kind, actors, place, attrs, source)`:

| Format | Library | Kestrel files |
| --- | --- | --- |
| CSV logs | `pandas` | badge, LPR, RFID, visitors, guard, workstation, VMS, carrier records, messages |
| JSONL / JSON | stdlib | cabinet audit, location history |
| ICS | `icalendar` | CEO calendar |
| EML | `email` stdlib | 5 emails |
| TXT statements / interviews | line-addressed reader | 12 documents (locator `line=N`) |
| DNA | CSV + report text | allele table, lab conclusions |
| JPEG | `Pillow` / `piexif` | EXIF time, offset, GPS, make and model |
| MP4 | `ffprobe` (+ VMS analytics CSV) | clip times; vision models optional later |

### WS2 Normalisation and cleaning
- Time rules come from `MANIFEST.csv` `time_basis` (UTC, local without offset, epoch ms, US 12-hour,
  burned-in) plus the reader drift in `doors_readers.csv` (E-2-LAB-A runs +167 s).
- Rules: exact-duplicate removal; plate matching within edit distance 1 and confidence ≥ 0.8; drop cell
  records with no location or a radius over 5 km for co-location; drop LOW_CONFIDENCE visits; flag RFID
  single misses.
- Message noise classifier: rules plus TF-IDF and logistic regression, trained on the `noise_type` labels in
  `record_labels.csv`.
- Output `cleaning_report.json`: every removed or corrected record, with the reason (shown in the audit view).
- Acceptance: at least 95% of labelled noise records handled; zero key records removed.

### WS3 Traditional ML

| Method | Purpose | Expected Kestrel result |
| --- | --- | --- |
| Space-time co-location (DBSCAN on lat, lon, time, or a sector-overlap join) | Who is repeatedly together | Halvorsen and +1-408-555-0147 on 9 evenings (I-06) |
| IsolationForest on access events (hour, weekday, reader, mode, PIN result, held-door, credential history) | Unusual access | Cabinet 22:51 Sat with failed PIN; P2 held door on a Saturday night (I-02, I-03) |
| Rule-based co-presence check | One credential, two places | Badge at EBC while the face-unlocked workstation was active 40 m away (I-02) |
| Record linkage (`rapidfuzz` + rules on names, numbers, companies, addresses) | Aliases | "Vince (Supply)" = 0147 = Pacific Harbor = V. Shen = Arbor Row (I-05) |
| NER (`spaCy`) + LLM claim extraction with a schema | Claims in statements and interviews | Halvorsen "home all evening"; Shen "home before nine" |
| Claim-vs-record contradiction | Lies and errors | I-04, I-07; Ortega's "around 11:30" reconciled to 23:03 (I-10) |

Protected attributes (`id_issuing_country`, nationality) are dropped before any feature is built.

### WS4 Graph builder
- Nodes: person, location, device, event, statement, evidence.
- Edges: temporal, spatial, communication, claim, supports, contradicts.
- Every node and edge carries `citations: [{evidence_id, locator}]` and a flag `observed | inferred`.
- Adapter to the frontend's current `CaseData` (`frontend/src/api/types.ts`); the final contract is still open in SPEC.
- Target: 60-120 legible nodes for Kestrel. Filter by default to key and supporting entities.

### WS5 Reasoning agent (LangChain deepagents)
- Package: `deepagents` 0.7.38 (2026-11-13), Python 3.11+. Since 0.7: no built-in base prompt,
  `write_todos` is opt-in via `TodoListMiddleware`, `FilesystemBackend(virtual_mode=True)` is the default,
  and backend factories are removed.
- **Proposed** models: Anthropic Claude, kept behind the provider string so OpenAI remains a config change.
  - Main agent: `anthropic:claude-opus-5-5`. Its default effort is `medium`; set `high` for the main pass.
    Forced `tool_choice` (`any`/`tool`) is rejected, so steer tool use from the prompt.
  - Verifier and extractor subagents: `anthropic:claude-sonnet-5-5`, or `claude-haiku-5-5` for bulk extraction.
  - Both models have a 1M-token context.
  - Keep the system prompt and tool list byte-stable so prompt caching works.
  - Handle the `refusal` stop reason.
- Sketch:

```python
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend

agent = create_deep_agent(
    model="anthropic:claude-opus-5-5",
    system_prompt=INVESTIGATOR_PROMPT,          # observation vs inference, cite or drop, gaps are not proof
    tools=[query_events, get_source, run_colocation, run_anomaly, list_contradictions,
           record_insight, record_gap],
    subagents=[{"name": "verifier", "description": "Checks that every citation resolves to source text",
                "system_prompt": VERIFIER_PROMPT, "tools": [get_source],
                "model": "anthropic:claude-sonnet-5-5"}],
    backend=FilesystemBackend(root_dir=job_dir, virtual_mode=True),
)
```

- Directed-question loop:
  1. For each key event and each person of interest, generate who / when / where / how questions.
  2. Answer each with tools.
  3. If a question cannot be answered, record a gap: the question, why it matters, affected claims, missing
     evidence, recommended artifact types, and a concrete example request.
  4. Rank artifacts by the gaps they close, weighted by priority and deadline
     (for example: priority x 1.0 for a full fix or 0.5 for a partial one, x 1.25 if the gap has a deadline).
- Guardrails:
  - `record_insight` rejects any insight without at least one resolvable locator.
  - Insights never cite protected attributes.
  - Gaps are worded as uncertainty, not accusation.

### WS6 Audit trail
- `audit.jsonl` records each step and each tool call: input hash, output hash, citations, model, timestamps,
  and `prev_hash` (a hash chain, so edits are detectable).
- Capture agent steps with `agent.stream(..., stream_mode=["updates", "messages", "custom"], subgraphs=True)`;
  LangSmith tracing is optional.
- Acceptance: each item on the board links to the audit entries and source lines that produced it.

### WS7 API
- From SPEC's initial proposal:
  - `POST /upload`, `GET /status/:id`
  - `GET /graph`, `/gaps`, `/insights`, `/audit`
  - **Proposed** addition: `GET /source/:evidenceId?locator=` for source inspection.
- Scope every route by job. Return a typed error body.

### WS8 Frontend integration (frontend team)
- Swap the mock adapter in `frontend/src/api/client.ts` for an HTTP adapter. Keep `isMock` for offline demos.
- No frontend changes on this branch. The frontend fixture case is a mock and is not used by the backend.

### WS9 Deployment (Proposed; open in SPEC)
- Docker Compose adds a `backend` service next to `frontend`.
- A single VM (for example Vultr, 4 vCPU / 8 GB) with TLS through Caddy. API keys in environment variables.
  Job data on an encrypted volume, no public buckets, and a delete-after-demo policy.

## 4. Demo script (3 minutes, Kestrel)

1. Upload `kestrel_case_upload.zip`. Progress shows the real stages (ingest, clean, ML, graph, reason) and file counts.
2. Board: the cabinet event points at the CEO's own badge, and staff name Raman and Bellini. That is the obvious read.
3. Open insight **I-02**: the badge opened the cabinet while the CEO's face-unlocked workstation was active 40 m away. Show both source rows.
4. Open **I-06**: co-location clustering finds nine private evenings with the "Vince (Supply)" number. **I-05** resolves it to Vivian Shen.
5. Open gap **G-01** (who is UF-1?). Show why it matters, what is missing, and the top-ranked artifacts with concrete requests and deadlines (she flies out Friday).
6. Red herrings: Raman's Tahoe alibi and the Chen travel bias guard.
7. Audit trail: every step, hash and citation.

## 5. Suggested hackathon order

| Hours | Work |
| --- | --- |
| 0-6 | WS1 ingest and parsers, WS2 time normalisation; in parallel WS0 scorer and WS4 graph schema |
| 6-14 | WS3 co-location, anomaly and contradiction rules; WS5 agent skeleton with tools over events |
| 14-22 | WS5 gaps and artifact ranking; WS6 audit; WS7 API; frontend adapter |
| 22-30 | Score against the local answer key, fix misses, tune prompts; deployment |
| 30-36 | Demo rehearsal and backup recording |

## 6. Risks

- **Invented citations:** the verifier subagent plus resolvable-locator checks in `record_insight`.
- **Overfitting to Kestrel:** test on seed variants, and keep the answer key and `generator/` out of prompts and code paths.
- **Bias:** protected attributes stripped; RH-03 is a regression test.
- **Time:** video vision models are optional. The VMS analytics CSV already gives person counts.
- **Privacy:** real evidence needs retention, access-control and provider-policy decisions (open in SPEC).
