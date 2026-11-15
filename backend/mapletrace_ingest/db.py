"""SQLite schema and low-level helpers for the Mapletrace evidence store.

One database per case. Every row that the reasoning layer will cite carries
enough provenance (file_id + locator) to be traced back to the original bytes.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1"

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS case_info (
    key   TEXT PRIMARY KEY,
    value TEXT
);

-- Every file found in the submission (including files nested in archives
-- and email attachments). Hashes are computed before any parsing.
CREATE TABLE IF NOT EXISTS evidence_files (
    file_id          INTEGER PRIMARY KEY,
    parent_file_id   INTEGER REFERENCES evidence_files(file_id),
    origin           TEXT NOT NULL,          -- 'zip_member' | 'nested_archive' | 'email_attachment'
    original_path    TEXT NOT NULL,          -- path as it appeared in its container
    stored_path      TEXT NOT NULL,          -- read-only working copy, relative to the run dir
    size_bytes       INTEGER NOT NULL,
    sha256           TEXT NOT NULL,
    md5              TEXT NOT NULL,
    container_mtime  TEXT,                   -- timestamp recorded by the container (weak evidence)
    sniffed_format   TEXT,                   -- from magic bytes / structure, not the extension
    extension        TEXT,
    evidence_type    TEXT,                   -- inferred: photo, video, messages, statement, dna, ...
    type_confidence  REAL,
    type_reason      TEXT,                   -- human-readable justification for the inferred type
    parser           TEXT,
    parse_status     TEXT NOT NULL DEFAULT 'pending',  -- pending|parsed|partial|failed|unsupported
    parse_notes      TEXT,
    record_count     INTEGER NOT NULL DEFAULT 0,
    external_id      TEXT,                   -- evidence ID from a submitted manifest (e.g. EV-071)
    manifest_json    TEXT                    -- that manifest row: custodian, time basis, grade, ...
);

-- What the pipeline inferred about a structured file's layout.
CREATE TABLE IF NOT EXISTS inferred_schemas (
    file_id         INTEGER PRIMARY KEY REFERENCES evidence_files(file_id),
    data_format     TEXT,        -- csv | json | jsonl | text | ...
    columns_json    TEXT,        -- raw column names
    column_map_json TEXT,        -- semantic role -> column
    type_scores_json TEXT,       -- score per candidate evidence type
    row_count       INTEGER,
    rows_skipped    INTEGER,
    skip_reasons_json TEXT
);

-- Technical metadata for photos, video and audio.
CREATE TABLE IF NOT EXISTS media (
    media_id        INTEGER PRIMARY KEY,
    file_id         INTEGER NOT NULL REFERENCES evidence_files(file_id),
    media_kind      TEXT NOT NULL,       -- photo | video | audio
    captured_utc    TEXT,
    captured_raw    TEXT,
    captured_source TEXT,                -- exif | container | container_mtime | none
    time_flags      TEXT,                -- JSON list
    gps_lat         REAL,
    gps_lon         REAL,
    device_make     TEXT,
    device_model    TEXT,
    device_serial   TEXT,
    software        TEXT,
    width           INTEGER,
    height          INTEGER,
    duration_s      REAL,
    metadata_json   TEXT
);

-- The unified record table: one row per message, call, location fix,
-- statement claim, interview turn, DNA profile, email, media capture, ...
CREATE TABLE IF NOT EXISTS records (
    record_id     INTEGER PRIMARY KEY,
    file_id       INTEGER NOT NULL REFERENCES evidence_files(file_id),
    record_type   TEXT NOT NULL,
    ts_utc        TEXT,          -- best point estimate (ISO 8601, UTC)
    ts_start_utc  TEXT,          -- uncertainty window start
    ts_end_utc    TEXT,          -- uncertainty window end
    ts_raw        TEXT,          -- exactly as it appeared in the evidence
    ts_precision  TEXT,          -- second|minute|hour|day|approximate|unknown
    ts_flags      TEXT,          -- JSON list, e.g. ["tz_assumed","day_month_ambiguous"]
    actor         TEXT,
    target        TEXT,
    lat           REAL,
    lon           REAL,
    content       TEXT,
    attributes_json TEXT,
    locator_json  TEXT NOT NULL, -- where inside the file: row, line, page, char span, message index
    record_sha256 TEXT NOT NULL, -- hash of (file hash, locator, content) for integrity checks
    reliability   TEXT NOT NULL, -- recorded | asserted | expert_finding | derived
    duplicate_of  INTEGER REFERENCES records(record_id)
);

CREATE TABLE IF NOT EXISTS entities (
    entity_id    INTEGER PRIMARY KEY,
    entity_type  TEXT NOT NULL,     -- person | phone | email | device | sample | account
    value_norm   TEXT NOT NULL,
    display_name TEXT,
    canonical_id INTEGER,           -- after entity resolution
    UNIQUE (entity_type, value_norm)
);

CREATE TABLE IF NOT EXISTS record_entities (
    record_id INTEGER NOT NULL REFERENCES records(record_id),
    entity_id INTEGER NOT NULL REFERENCES entities(entity_id),
    role      TEXT NOT NULL,        -- sender | recipient | speaker | author | mentioned | subject | device ...
    PRIMARY KEY (record_id, entity_id, role)
);

-- Every entity-resolution decision, with the rule and the evidence behind it.
CREATE TABLE IF NOT EXISTS entity_links (
    link_id     INTEGER PRIMARY KEY,
    entity_a    INTEGER NOT NULL REFERENCES entities(entity_id),
    entity_b    INTEGER NOT NULL REFERENCES entities(entity_id),
    rule        TEXT NOT NULL,
    record_id   INTEGER REFERENCES records(record_id),
    confidence  REAL NOT NULL
);

-- Tamper-evident, append-only log of everything the pipeline did.
CREATE TABLE IF NOT EXISTS audit_log (
    seq         INTEGER PRIMARY KEY,
    ts_utc      TEXT NOT NULL,
    stage       TEXT NOT NULL,
    action      TEXT NOT NULL,
    file_id     INTEGER,
    detail_json TEXT,
    prev_hash   TEXT NOT NULL,
    entry_hash  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_records_ts   ON records(ts_start_utc);
CREATE INDEX IF NOT EXISTS idx_records_type ON records(record_type);
CREATE INDEX IF NOT EXISTS idx_records_file ON records(file_id);
CREATE INDEX IF NOT EXISTS idx_re_entity    ON record_entities(entity_id);

-- Convenience views for the next pipeline stage.
CREATE VIEW IF NOT EXISTS timeline AS
    SELECT r.record_id, r.ts_utc, r.ts_start_utc, r.ts_end_utc, r.ts_precision,
           r.record_type, r.reliability, r.actor, r.target, r.lat, r.lon, r.content,
           f.evidence_type, f.original_path, r.locator_json
    FROM records r JOIN evidence_files f ON f.file_id = r.file_id
    WHERE r.ts_utc IS NOT NULL AND r.duplicate_of IS NULL
    ORDER BY r.ts_utc;

CREATE VIEW IF NOT EXISTS entity_cooccurrence AS
    SELECT ea.canonical_id AS entity_a, eb.canonical_id AS entity_b,
           COUNT(DISTINCT a.record_id) AS weight
    FROM record_entities a
    JOIN record_entities b ON a.record_id = b.record_id
    JOIN entities ea ON ea.entity_id = a.entity_id
    JOIN entities eb ON eb.entity_id = b.entity_id
    WHERE ea.canonical_id < eb.canonical_id
    GROUP BY ea.canonical_id, eb.canonical_id;
"""

GENESIS_HASH = "0" * 64


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.execute("INSERT OR REPLACE INTO case_info(key, value) VALUES ('schema_version', ?)", (SCHEMA_VERSION,))
    conn.commit()


class AuditLog:
    """Hash-chained audit log: each entry commits to the previous one."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        row = conn.execute("SELECT entry_hash FROM audit_log ORDER BY seq DESC LIMIT 1").fetchone()
        self.head = row["entry_hash"] if row else GENESIS_HASH

    def write(self, stage: str, action: str, detail: dict | None = None, file_id: int | None = None) -> str:
        ts = utc_now_iso()
        detail_json = canonical_json(detail or {})
        payload = canonical_json([self.head, ts, stage, action, file_id, detail_json])
        entry_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        self.conn.execute(
            "INSERT INTO audit_log(ts_utc, stage, action, file_id, detail_json, prev_hash, entry_hash) "
            "VALUES (?,?,?,?,?,?,?)",
            (ts, stage, action, file_id, detail_json, self.head, entry_hash),
        )
        self.head = entry_hash
        return entry_hash


def verify_audit_chain(conn: sqlite3.Connection) -> tuple[bool, str]:
    prev = GENESIS_HASH
    count = 0
    for row in conn.execute("SELECT * FROM audit_log ORDER BY seq"):
        if row["prev_hash"] != prev:
            return False, f"chain broken at seq {row['seq']} (prev_hash mismatch)"
        payload = canonical_json([prev, row["ts_utc"], row["stage"], row["action"], row["file_id"], row["detail_json"]])
        if hashlib.sha256(payload.encode("utf-8")).hexdigest() != row["entry_hash"]:
            return False, f"entry {row['seq']} was modified (hash mismatch)"
        prev = row["entry_hash"]
        count += 1
    return True, f"{count} audit entries verified; head {prev[:16]}…"
