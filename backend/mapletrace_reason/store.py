"""Read-only access to an ingested case (`case.db`) plus citation helpers.

The analysis never writes to case.db: evidence stays immutable and every derived
result lives in the analysis output, citing records by evidence ID and locator.
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import cached_property
from pathlib import Path

PROTECTED_KEYS = re.compile(r"(issuing_country|nationality|citizenship|ethnicity|race|religion|national_id_country|"
                            r"place_of_birth|immigration)", re.I)
_PLACE_KEYS = ("place", "door", "checkpoint", "zone", "room", "location", "computer", "host", "cabinet_id",
               "reader_id", "camera_id", "address", "site", "building", "name")
_ID_KEYS = ("seq", "event_id", "record_id", "scan_id", "read_id", "visit_id", "entry_id", "id", "uid",
            "segmentId", "visitId", "message_id")


def parse_ts(s: str | None) -> datetime | None:
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def iso(dt: datetime | None) -> str | None:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z") if dt else None


def haversine_m(lat1, lon1, lat2, lon2) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def locator_label(locator: dict, attrs: dict) -> str:
    """The human-readable locator used in citation ids (`EV-071:seq=40162`). `attrs` must already have protected
    attributes removed (see PROTECTED_KEYS)."""
    for k in _ID_KEYS:
        if k in locator and k not in ("char_start",):
            return f"{k}={locator[k]}"
    for k in _ID_KEYS:
        if attrs.get(k) not in (None, ""):
            return f"{k}={attrs[k]}"
    loc = locator
    if "doc_line" in loc:
        return f"line={loc['doc_line']}"
    if "row" in loc:
        return f"row={loc['row']}"
    if "page" in loc:
        return f"page={loc['page']}" + (f" line={loc['line']}" if "line" in loc else "")
    if "paragraph" in loc:
        return f"paragraph={loc['paragraph']}"
    if "line" in loc:
        return f"line={loc['line']}"
    if "json_path" in loc:
        return loc["json_path"]
    return ",".join(f"{k}={v}" for k, v in loc.items()) or "file"


def unique_labels(items) -> dict:
    """Citation labels that identify exactly one record. `items` yields `(key, file_id, locator, attrs)`. An attribute
    shared by several records of one file (an event code such as `event_id=9001`, not a record ID) would merge distinct
    records into one citation, so those records fall back to their position in the file (`row=`, `line=`, ...)."""
    first = {key: (file_id, locator_label(loc, attrs), loc) for key, file_id, loc, attrs in items}
    counts = Counter((file_id, label) for file_id, label, _ in first.values())
    return {key: label if counts[(file_id, label)] == 1 else locator_label(loc, {})
            for key, (file_id, label, loc) in first.items()}


def citation_id(evidence_id: str, label: str) -> str:
    return f"{evidence_id}:{label}"


@dataclass
class Record:
    id: int
    file_id: int
    type: str
    ts: datetime | None
    start: datetime | None
    end: datetime | None
    precision: str
    flags: list[str]
    actor: str | None
    target: str | None
    lat: float | None
    lon: float | None
    content: str
    attrs: dict
    locator: dict
    reliability: str
    duplicate_of: int | None
    entities: list[tuple[int, str]] = field(default_factory=list)  # (canonical entity id, role)

    @property
    def place(self) -> str | None:
        for k in _PLACE_KEYS:
            v = self.attrs.get(k)
            if v and isinstance(v, str) and k != "name":
                return v
        if self.type == "place_visit":
            return self.attrs.get("name") or self.content
        return None

    @property
    def uncertain(self) -> bool:
        return self.precision not in ("second", "minute") or any(
            f in self.flags for f in ("human_reported", "container_mtime_only", "day_month_ambiguous",
                                      "am_pm_unspecified", "am_pm_inferred_from_sequence", "am_pm_inferred_from_context",
                                      "date_rolled_overnight", "midnight_ambiguous", "low_reliability"))


class Case:
    """Everything the analysis needs from one ingested case, loaded once."""

    def __init__(self, run_dir: Path):
        self.run_dir = Path(run_dir)
        db = self.run_dir / "case.db"
        if not db.exists():
            raise FileNotFoundError(f"{db} not found; run ingestion first")
        self.conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.info = {r["key"]: r["value"] for r in self.conn.execute("SELECT key, value FROM case_info")}
        self.files = {r["file_id"]: dict(r) for r in self.conn.execute(
            "SELECT file_id, original_path, stored_path, sha256, evidence_type, parse_status, parse_notes, external_id, "
            "manifest_json, record_count, type_reason FROM evidence_files")}
        for f in self.files.values():
            f["manifest"] = json.loads(f["manifest_json"]) if f["manifest_json"] else {}
        self.entities = {r["entity_id"]: dict(r) for r in self.conn.execute(
            "SELECT entity_id, entity_type, value_norm, display_name, canonical_id FROM entities")}
        self.links = [dict(r) for r in self.conn.execute("SELECT * FROM entity_links")]
        self._load_records()

    def _load_records(self) -> None:
        ents: dict[int, list[tuple[int, str]]] = {}
        for r in self.conn.execute("SELECT record_id, entity_id, role FROM record_entities"):
            canon = self.entities[r["entity_id"]]["canonical_id"] or r["entity_id"]
            ents.setdefault(r["record_id"], []).append((canon, r["role"]))
        self.records: dict[int, Record] = {}
        for r in self.conn.execute("SELECT * FROM records"):
            attrs = {k: v for k, v in json.loads(r["attributes_json"] or "{}").items() if not PROTECTED_KEYS.search(k)}
            self.records[r["record_id"]] = Record(
                r["record_id"], r["file_id"], r["record_type"], parse_ts(r["ts_utc"]), parse_ts(r["ts_start_utc"]),
                parse_ts(r["ts_end_utc"]), r["ts_precision"] or "unknown", json.loads(r["ts_flags"] or "[]"),
                r["actor"], r["target"], r["lat"], r["lon"], r["content"] or "", attrs,
                json.loads(r["locator_json"] or "{}"), r["reliability"], r["duplicate_of"],
                list(dict.fromkeys(ents.get(r["record_id"], []))))

    # ------------------------------------------------------------ entities
    def name(self, eid: int) -> str:
        e = self.entities.get(eid)
        return (e["display_name"] or e["value_norm"]) if e else f"entity {eid}"

    def etype(self, eid: int) -> str:
        return self.entities[eid]["entity_type"] if eid in self.entities else "unknown"

    @cached_property
    def persons(self) -> set[int]:
        return {e["canonical_id"] for e in self.entities.values() if e["entity_type"] == "person"}

    def person_of(self, rec: Record, roles: tuple[str, ...] | None = None) -> list[int]:
        out = []
        for eid, role in rec.entities:
            if roles and role not in roles:
                continue
            if self.etype(eid) == "person" and eid not in out:
                out.append(eid)
        return out

    @cached_property
    def timed(self) -> list[Record]:
        return sorted((r for r in self.records.values() if r.ts and r.duplicate_of is None), key=lambda r: r.ts)

    # ------------------------------------------------------------ citations
    @cached_property
    def _labels(self) -> dict[int, str]:
        return unique_labels((r.id, r.file_id, r.locator, r.attrs) for r in self.records.values())

    def locator_label(self, rec: Record) -> str:
        return self._labels[rec.id]

    def cite(self, rid: int) -> dict:
        rec = self.records[rid]
        f = self.files[rec.file_id]
        ev = f["external_id"] or f"FILE-{rec.file_id}"
        label = self.locator_label(rec)
        return {"id": citation_id(ev, label), "evidence_id": ev, "locator": label, "record_id": rid,
                "path": f["original_path"], "sha256": f["sha256"]}

    def origin_of(self, rid: int) -> str:
        """Which independent source produced a record: the custodian/system, not the file.
        Two exports from the same phone are one source; a carrier and a phone are two."""
        f = self.files[self.records[rid].file_id]
        m = f["manifest"]
        if m.get("custodian"):
            return f"{m.get('custodian')}|{m.get('modality', f['evidence_type'])}"
        return f"{f['evidence_type']}|{f['original_path'].split('::')[0].rsplit('/', 1)[0]}"
