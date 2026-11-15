"""End-to-end ingestion: zip in, SQLite case database out.

    intake (safe extract + hash) -> sniff + infer type -> extract records
    -> normalize time and identifiers -> resolve entities -> flag duplicates
    -> coverage report

Every step writes to the hash-chained audit log.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import traceback
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import __version__
from .classify import classify_file
from .db import AuditLog, canonical_json, connect, init_db, utc_now_iso
from .entities import (EMAIL_RE, PHONE_RE, classify_identifier, looks_like_person, normalize_email, normalize_phone,
                       parse_named_address, person_key, split_people_field)
from .extractors import Outcome
from .extractors import dna as dna_x
from .extractors import documents as doc_x
from .extractors import email_geo as eg_x
from .extractors import media as media_x
from .extractors import tabular as tab_x
from .intake import IntakeError, Limits, extract_zip, hash_file, make_read_only, sniff_format
from .timeparse import TimeValue

MANIFEST_NAMES = {"case_manifest.json", "manifest.json", "evidence_manifest.json"}
MANIFEST_CSV_NAMES = {"manifest.csv", "evidence_manifest.csv"}
_ZONE_WORDS = [  # (case-sensitive abbreviations, case-insensitive words, IANA zone)
    (r"\b(PDT|PST)\b", r"\bpacific\b", "America/Los_Angeles"),
    (r"\b(EDT|EST)\b", r"\beastern\b", "America/New_York"),
    (r"\b(CDT|CST)\b", r"\bcentral\b", "America/Chicago"),
    (r"\b(MDT|MST)\b", r"\bmountain\b", "America/Denver"),
]


def _zone_from_basis(basis: str) -> str | None:
    """'UTC ISO-8601 (Z)' -> 'UTC'; 'local wall time (PDT), no offset' -> 'America/Los_Angeles'.
    Returns None when the timestamps carry their own offset or the basis is unknown."""
    b = basis or ""
    m = re.search(r"\b([A-Z][a-z]+/[A-Za-z_]+)\b", b)
    if m:
        return m.group(1)
    if re.search(r"\bUTC\b|epoch", b, re.I) and not re.search(r"local", b, re.I):
        return "UTC"
    for abbr, word, zone in _ZONE_WORDS:
        if re.search(abbr, b) or re.search(word, b, re.I):
            return zone
    return None
_GENERIC_NAME_WORDS = {
    "location", "locations", "history", "gps", "track", "tracks", "sms", "messages", "message", "chat", "call",
    "calls", "log", "logs", "export", "phone", "data", "records", "contacts", "contact", "cell", "mobile",
    "statement", "witness", "interview", "transcript", "photo", "photos", "video", "img", "dna", "lab", "report",
    "the", "of", "and", "from", "for", "csv", "json", "txt", "vehicle", "car", "device", "backup", "copy", "final",
    "whatsapp", "imessage", "signal", "email", "emails", "mail", "inbox", "case", "file", "cctv", "cam", "camera",
    "iphone", "android", "pixel", "samsung", "galaxy", "timeline", "cdr", "subscriber", "extraction", "notes",
    "custody", "audit", "inventory", "visitor", "visitors", "badge", "guard", "tours", "readers", "doors", "acl",
}
_MENTION_STOP = {"will", "may", "june", "april", "mark", "bill", "rose", "grace", "hope", "faith", "joy", "page",
                 "long", "young", "white", "black", "brown", "green", "street", "north", "south", "east", "west",
                 "home", "office", "officer", "detective", "witness", "subject", "interviewer"}


@dataclass
class IngestOptions:
    timezone: str = "UTC"
    dayfirst: bool = False
    default_country_code: str = "1"
    case_name: str | None = None
    limits: Limits = field(default_factory=Limits)
    overwrite: bool = False
    trace: object | None = None   # optional trace.TraceWriter: presentation telemetry, never part of the evidence


class Ingestor:
    def __init__(self, out_dir: Path, options: IngestOptions):
        self.out = Path(out_dir)
        self.opts = options
        try:
            self.tz = ZoneInfo(options.timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"unknown time zone {options.timezone!r}") from exc
        self.dayfirst = options.dayfirst
        self.default_cc = options.default_country_code
        self.conn = None
        self.audit: AuditLog | None = None
        self.queue: deque[int] = deque()
        self._owner_hints: dict[int, tuple[str, str]] = {}
        self._file_cache: dict[int, dict] = {}
        self._entity_cache: dict[tuple[str, str], int] = {}
        self.manifest: dict = {}
        self.case_tz = self.tz
        self._file_tz: dict[int, ZoneInfo] = {}
        self.trace = options.trace
        self._manifest_match: dict[int, bool] = {}
        self._hash_traced = False

    # ------------------------------------------------------------------ run
    def run(self, zip_path: Path) -> dict:
        zip_path = Path(zip_path).resolve()
        if self.out.exists() and any(self.out.iterdir()):
            if not self.opts.overwrite:
                raise FileExistsError(f"{self.out} is not empty (use --overwrite to replace it)")
            _rmtree_readonly(self.out)
        (self.out / "evidence").mkdir(parents=True, exist_ok=True)
        self.conn = connect(self.out / "case.db")
        init_db(self.conn)
        self.audit = AuditLog(self.conn)

        zip_sha, zip_md5 = hash_file(zip_path)
        info = {"case_name": self.opts.case_name or zip_path.stem, "source_archive": zip_path.name,
                "source_archive_sha256": zip_sha, "source_archive_md5": zip_md5,
                "source_archive_bytes": zip_path.stat().st_size, "ingested_at_utc": utc_now_iso(),
                "pipeline_version": __version__, "assumed_timezone": self.opts.timezone,
                "dayfirst_dates": str(self.dayfirst), "default_country_code": self.default_cc}
        self.conn.executemany("INSERT OR REPLACE INTO case_info(key, value) VALUES (?,?)", list(info.items()))
        if self.trace:
            self.trace.emit("ingest", "run_started", **{"mode": "replay", "llm": False, "model": None,
                            "archive": {"filename": zip_path.name, "sha256": zip_sha, "bytes": info["source_archive_bytes"]},
                            **self.trace.context})
            self.trace.phase("ingest", "Hashing evidence")
        self.audit.write("intake", "archive_received", {k: info[k] for k in ("source_archive", "source_archive_sha256", "source_archive_bytes")})

        members = extract_zip(zip_path, self.out / "evidence", self.opts.limits, lambda a, d: self.audit.write("intake", a, d))
        for m in members:
            self._register_file(None, "zip_member", m.original_path, m.stored_path, m.size, m.sha256, m.md5, m.container_mtime, depth=0)
        self.audit.write("intake", "archive_extracted", {"files": len(members)})
        self.conn.commit()
        self._load_manifest()
        if self.trace:
            for fid in list(self._file_cache):
                self._trace_hashed(fid)
            self._hash_traced = True
            self.trace.phase("ingest", "Parsing evidence")

        while self.queue:
            fid = self.queue.popleft()
            self._process(fid)
            self.conn.commit()
            if self.trace:
                self._trace_parsed(fid)

        if self.trace:
            self.trace.phase("ingest", "Linking entities")
        self._resolve_entities()
        self._link_mentions()
        self._flag_cross_source_duplicates()
        self.conn.commit()
        if self.trace:
            self.trace.emit("ingest", "entities_linked",
                            entities=self.conn.execute("SELECT COUNT(DISTINCT canonical_id) FROM entities").fetchone()[0],
                            links=self.conn.execute("SELECT COUNT(*) FROM entity_links").fetchone()[0])
            self.trace.phase("ingest", "Writing the coverage report")

        from .report import build_report, write_summary_markdown
        report = build_report(self.conn)
        (self.out / "ingest_report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        write_summary_markdown(report, self.out / "ingest_summary.md")
        self.audit.write("report", "coverage_report_written", {"records": report["totals"]["records"],
                                                                "files": report["totals"]["files"]})
        self.conn.commit()
        head = self.audit.head
        self.conn.close()
        db_sha, _ = hash_file(self.out / "case.db")
        run_manifest = {"case": info, "database": "case.db", "database_sha256": db_sha, "audit_head_hash": head,
                        "report": "ingest_report.json", "summary": "ingest_summary.md"}
        (self.out / "run_manifest.json").write_text(json.dumps(run_manifest, indent=2), encoding="utf-8")
        return report

    # ------------------------------------------------------------ files
    def _register_file(self, parent, origin, original_path, stored_path, size, sha, md5, mtime, depth) -> int:
        rel = stored_path.relative_to(self.out).as_posix()
        cur = self.conn.execute(
            "INSERT INTO evidence_files(parent_file_id, origin, original_path, stored_path, size_bytes, sha256, md5, "
            "container_mtime, extension) VALUES (?,?,?,?,?,?,?,?,?)",
            (parent, origin, original_path, rel, size, sha, md5, mtime, Path(original_path).suffix.lower() or None))
        fid = cur.lastrowid
        self._file_cache[fid] = {"original_path": original_path, "path": stored_path, "mtime": mtime, "depth": depth}
        self.audit.write("intake", "file_registered", {"original_path": original_path, "sha256": sha, "size": size,
                                                       "origin": origin, "parent_file_id": parent}, fid)
        self.queue.append(fid)
        if self.trace and self._hash_traced:
            self._trace_hashed(fid)
        return fid

    # ------------------------------------------------------------ trace (telemetry only)
    def _evidence_id(self, fid: int) -> str:
        row = self.conn.execute("SELECT external_id FROM evidence_files WHERE file_id=?", (fid,)).fetchone()
        return (row[0] if row else None) or f"FILE-{fid}"

    def _trace_hashed(self, fid: int) -> None:
        row = self.conn.execute("SELECT original_path, sha256, size_bytes FROM evidence_files WHERE file_id=?", (fid,)).fetchone()
        self.trace.emit("ingest", "file_hashed", evidenceId=self._evidence_id(fid), filename=row[0], sha256=row[1],
                        bytes=row[2], manifestMatch=self._manifest_match.get(fid))

    def _trace_parsed(self, fid: int) -> None:
        row = self.conn.execute("SELECT original_path, sniffed_format, parse_status, record_count FROM evidence_files "
                                "WHERE file_id=?", (fid,)).fetchone()
        types = {t: n for t, n in self.conn.execute("SELECT record_type, COUNT(*) FROM records WHERE file_id=? "
                                                     "GROUP BY record_type ORDER BY 2 DESC", (fid,))}
        self.trace.emit("ingest", "file_parsed", evidenceId=self._evidence_id(fid), filename=row[0], format=row[1],
                        parseStatus=row[2], records=row[3] or 0, recordTypes=types)

    def add_derived_file(self, parent_id: int, name: str, data: bytes, origin: str) -> int | None:
        depth = self._file_cache[parent_id]["depth"] + 1
        if depth > self.opts.limits.max_archive_depth:
            self.audit.write("intake", "max_depth_reached", {"name": name}, parent_id)
            return None
        safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name) or "unnamed"
        dest = self.out / "evidence" / "_derived" / str(parent_id) / safe
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            dest = dest.with_name(f"{dest.stem}__{hashlib.sha256(data).hexdigest()[:8]}{dest.suffix}")
        dest.write_bytes(data)
        sha, md5 = hash_file(dest)
        make_read_only(dest)
        parent_path = self._file_cache[parent_id]["original_path"]
        return self._register_file(parent_id, origin, f"{parent_path}::{name}", dest, len(data), sha, md5, None, depth)

    def _set_case_tz(self, tz_name: str, source: str, fid: int) -> None:
        if self.opts.timezone != "UTC":
            return  # an explicit --tz always wins
        try:
            self.case_tz = self.tz = ZoneInfo(tz_name)
        except ZoneInfoNotFoundError:
            return
        self.conn.execute("UPDATE case_info SET value=? WHERE key='assumed_timezone'", (tz_name,))
        self.audit.write("intake", "timezone_from_manifest", {"timezone": tz_name, "source": source}, fid)

    def _load_manifest(self) -> None:
        for fid, meta in list(self._file_cache.items()):
            name = Path(meta["original_path"]).name.lower()
            if name in MANIFEST_NAMES:
                try:
                    self.manifest = json.loads(meta["path"].read_text(encoding="utf-8-sig"))
                except (ValueError, OSError) as exc:
                    self.audit.write("intake", "manifest_unreadable", {"error": str(exc)}, fid)
                    continue
                self.audit.write("intake", "manifest_loaded", {"keys": sorted(self.manifest)}, fid)
                if self.manifest.get("timezone"):
                    self._set_case_tz(self.manifest["timezone"], "case_manifest.json", fid)
                if self.manifest.get("case_name") and not self.opts.case_name:
                    self.conn.execute("UPDATE case_info SET value=? WHERE key='case_name'", (self.manifest["case_name"],))
            elif name in MANIFEST_CSV_NAMES:
                self._load_csv_manifest(fid, meta)

    def _load_csv_manifest(self, fid: int, meta: dict) -> None:
        """MANIFEST.csv (path, sha256, evidence_id, custodian, time_basis, ...): verify hashes against what
        arrived, attach evidence IDs, and learn each file's time basis (UTC vs local wall time)."""
        import csv
        try:
            rows = list(csv.DictReader(meta["path"].read_text(encoding="utf-8-sig").splitlines()))
        except (OSError, csv.Error) as exc:
            self.audit.write("intake", "manifest_unreadable", {"error": str(exc)}, fid)
            return
        if not rows or "path" not in rows[0] or "sha256" not in rows[0]:
            return
        base = str(Path(meta["original_path"]).parent.as_posix())
        base = "" if base == "." else base + "/"
        by_path = {fm["original_path"]: (f, fm) for f, fm in self._file_cache.items()}
        matched, mismatched, missing, local_zones = 0, [], [], []
        for row in rows:
            key = base + row["path"].replace("\\", "/")
            hit = by_path.get(key)
            if not hit:
                missing.append(row["path"])
                continue
            f, fm = hit
            sha = self.conn.execute("SELECT sha256 FROM evidence_files WHERE file_id=?", (f,)).fetchone()[0]
            if sha == row["sha256"].lower():
                matched += 1
                self._manifest_match[f] = True
            else:
                mismatched.append(row["path"])
                self._manifest_match[f] = False
            self._set_file(f, external_id=row.get("evidence_id") or row.get("id"), manifest_json=json.dumps(row))
            zone = _zone_from_basis(row.get("time_basis", ""))
            if zone == "UTC":
                self._file_tz[f] = ZoneInfo("UTC")
            elif zone:
                local_zones.append(zone)
                self._file_tz[f] = ZoneInfo(zone)
            # a phone/location extraction whose custodian is named in the file name belongs to that person
            cust = (row.get("custodian") or "").strip()
            surname = cust.split()[-1].lower() if cust and re.fullmatch(r"[A-Z][a-z]+(?: [A-Z][a-z'\-]+){1,2}", cust) else None
            if surname and surname in Path(row["path"]).stem.lower():
                self._owner_hints[f] = (cust, "manifest")
        if local_zones:
            self._set_case_tz(max(set(local_zones), key=local_zones.count), "MANIFEST.csv time_basis", fid)
        self.audit.write("intake", "manifest_hashes_checked", {"matched": matched, "mismatched": mismatched,
                                                               "listed_but_missing": missing}, fid)

    def _process(self, fid: int) -> None:
        meta = self._file_cache[fid]
        path: Path = meta["path"]
        if Path(meta["original_path"]).name.lower() in MANIFEST_NAMES and self.manifest:
            self._set_file(fid, sniffed_format="json", evidence_type="case_manifest", type_confidence=1.0,
                           type_reason="case manifest supplied with the submission", parse_status="parsed",
                           parser="manifest", parse_notes=json.dumps(["used for owners, devices and time zone"]))
            return
        self.tz = self._file_tz.get(fid, self.case_tz)  # the manifest may say this file is UTC or local time
        try:
            fmt = sniff_format(path)
            decision, payload = classify_file(path, fmt)
            self._set_file(fid, sniffed_format=fmt, evidence_type=decision.evidence_type,
                           type_confidence=decision.confidence, type_reason=decision.reason)
            self.audit.write("classify", "type_inferred", {"format": fmt, "type": decision.evidence_type,
                                                           "confidence": decision.confidence, "reason": decision.reason,
                                                           "scores": decision.scores}, fid)
            outcome = self._route(fid, path, fmt, decision, payload)
        except Exception as exc:  # noqa: BLE001 - one bad file must never stop the case
            outcome = Outcome("failed", "error", [f"{type(exc).__name__}: {exc}"])
            self.audit.write("extract", "file_failed", {"error": str(exc), "trace": traceback.format_exc(limit=3)}, fid)
        count = self.conn.execute("SELECT COUNT(*) FROM records WHERE file_id=?", (fid,)).fetchone()[0]
        self._set_file(fid, parse_status=outcome.status, parser=outcome.parser,
                       parse_notes=json.dumps(outcome.notes), record_count=count)
        self.audit.write("extract", "file_processed", {"status": outcome.status, "parser": outcome.parser,
                                                       "records": count, "notes": outcome.notes}, fid)

    def _route(self, fid, path, fmt, decision, payload) -> Outcome:
        t = decision.evidence_type
        rows = payload.get("rows")
        text_payload = "text" in payload
        if t == "case_manifest":
            return Outcome("parsed", "manifest", ["used for evidence IDs, hash checks, owners and per-file time basis"])
        if t == "calendar":
            return eg_x.extract_calendar(self, fid, path)
        if t == "location" and "takeout" in payload:
            return eg_x.extract_takeout(self, fid, payload["takeout"])
        if t == "photo":
            return media_x.extract_photo(self, fid, path)
        if t in {"video", "audio"}:
            return media_x.extract_av(self, fid, path, t)
        if t == "email":
            return eg_x.extract_email(self, fid, path, fmt)
        if t == "location" and fmt in {"gpx", "kml"}:
            return eg_x.extract_geo(self, fid, path, fmt)
        if t == "dna":
            if fmt == "fasta":
                return dna_x.extract_fasta(self, fid, path)
            if fmt == "vcf":
                return dna_x.extract_vcf(self, fid, path)
            if rows is not None:
                return dna_x.extract_dna_table(self, fid, payload, decision)
            if text_payload:
                return dna_x.extract_lab_report(self, fid, payload)
        if rows is not None and t in {"messages", "call_log", "location", "contacts", "records"}:
            return tab_x.extract_table(self, fid, t, payload, decision)
        if text_payload:
            if t == "messages":
                return doc_x.extract_chat_export(self, fid, payload)
            if t == "statement":
                return doc_x.extract_statement(self, fid, payload)
            if t == "interview":
                return doc_x.extract_interview(self, fid, payload)
            return doc_x.extract_document(self, fid, payload)
        if t == "archive":
            return self._expand_archive(fid, path)
        if t == "empty":
            return Outcome("unsupported", "none", ["empty file"])
        return Outcome("unsupported", "none", [decision.reason or "no parser for this format; file is hashed and inventoried"])

    def _expand_archive(self, fid: int, path: Path) -> Outcome:
        depth = self._file_cache[fid]["depth"] + 1
        if depth > self.opts.limits.max_archive_depth:
            return Outcome("unsupported", "zip", ["nested archive deeper than the limit; not expanded"])
        dest = self.out / "evidence" / "_derived" / str(fid)
        members = extract_zip(path, dest, self.opts.limits, lambda a, d: self.audit.write("intake", a, d, fid))
        parent = self._file_cache[fid]["original_path"]
        for m in members:
            self._register_file(fid, "nested_archive", f"{parent}::{m.original_path}", m.stored_path, m.size,
                                m.sha256, m.md5, m.container_mtime, depth)
        return Outcome("parsed", "zip", [f"{len(members)} files extracted for ingestion"])

    def _set_file(self, fid: int, **cols) -> None:
        sets = ", ".join(f"{k}=?" for k in cols)
        self.conn.execute(f"UPDATE evidence_files SET {sets} WHERE file_id=?", (*cols.values(), fid))

    # --------------------------------------------- context API for extractors
    def file_original_path(self, fid: int) -> str:
        return self._file_cache[fid]["original_path"]

    def file_container_mtime(self, fid: int) -> str | None:
        return self._file_cache[fid]["mtime"]

    def file_owner_hint(self, fid: int) -> str | None:
        if fid in self._owner_hints:
            return self._owner_hints[fid][0]
        original = self._file_cache[fid]["original_path"]
        files = self.manifest.get("files", {}) if isinstance(self.manifest.get("files"), dict) else {}
        entry = files.get(original) or files.get(original.split("::")[0]) or {}
        if entry.get("owner"):
            self._owner_hints[fid] = (entry["owner"], "manifest")
            return entry["owner"]
        stem = Path(original.split("::")[-1]).stem.lower()
        tokens = [t for t in re.split(r"[^a-z]+", stem) if t and t not in _GENERIC_NAME_WORDS and len(t) >= 3]
        if len(tokens) == 1:
            self._owner_hints[fid] = (tokens[0], "filename")
            return tokens[0]
        self._owner_hints[fid] = (None, "none")
        return None

    def entity_id(self, etype: str, value: str, display: str | None) -> int:
        key = (etype, value)
        if key in self._entity_cache:
            return self._entity_cache[key]
        self.conn.execute("INSERT OR IGNORE INTO entities(entity_type, value_norm, display_name) VALUES (?,?,?)",
                          (etype, value, display))
        eid = self.conn.execute("SELECT entity_id FROM entities WHERE entity_type=? AND value_norm=?", key).fetchone()[0]
        self.conn.execute("UPDATE entities SET canonical_id=entity_id WHERE entity_id=? AND canonical_id IS NULL", (eid,))
        self._entity_cache[key] = eid
        return eid

    def _entity_specs(self, fid: int, spec) -> list[tuple[str, str, str]]:
        if spec is None or spec == "":
            return []
        if isinstance(spec, tuple):
            etype, val, disp = spec
            return [(etype, val, disp)] if val else []
        raw = str(spec)
        hint = self._owner_hints.get(fid)
        if hint and hint[1] == "filename" and raw == hint[0]:
            return [("account", f"filename:{raw}", raw)]
        out = []
        for part in split_people_field(raw) if ("@" in raw or ";" in raw) else [raw]:
            ident = classify_identifier(part, self.default_cc)
            if ident:
                out.append(ident)
        return out

    def add_record(self, fid: int, record_type: str, *, ts: TimeValue | None = None, actor=None, target=None,
                   content=None, lat=None, lon=None, attributes=None, locator=None, reliability="recorded",
                   entities=()) -> int:
        tcols = ts.as_columns() if ts else {"ts_utc": None, "ts_start_utc": None, "ts_end_utc": None,
                                            "ts_raw": None, "ts_precision": "unknown", "ts_flags": []}
        locator = locator or {}
        content = None if content is None else str(content)
        sha = hashlib.sha256(canonical_json([self.conn.execute("SELECT sha256 FROM evidence_files WHERE file_id=?", (fid,)).fetchone()[0],
                                             locator, content, tcols["ts_raw"]]).encode()).hexdigest()
        cur = self.conn.execute(
            "INSERT INTO records(file_id, record_type, ts_utc, ts_start_utc, ts_end_utc, ts_raw, ts_precision, ts_flags, "
            "actor, target, lat, lon, content, attributes_json, locator_json, record_sha256, reliability) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (fid, record_type, tcols["ts_utc"], tcols["ts_start_utc"], tcols["ts_end_utc"], tcols["ts_raw"],
             tcols["ts_precision"], json.dumps(tcols["ts_flags"]), None if actor is None else str(actor),
             None if target is None else str(target), lat, lon, content,
             canonical_json(attributes or {}), canonical_json(locator), sha, reliability))
        rid = cur.lastrowid
        for spec, role in entities:
            for etype, val, disp in self._entity_specs(fid, spec):
                self.conn.execute("INSERT OR IGNORE INTO record_entities(record_id, entity_id, role) VALUES (?,?,?)",
                                  (rid, self.entity_id(etype, val, disp), role))
            # "Ana Ruiz <a.ruiz@example.gov>": the display name is evidence linking a person to the address
            if isinstance(spec, str) and "@" in spec and "<" in spec:
                for part in split_people_field(spec):
                    name, addr = parse_named_address(part)
                    k = person_key(name) if name and looks_like_person(name) else None
                    if k and addr:
                        pid = self.entity_id("person", k, name)
                        self.conn.execute("INSERT OR IGNORE INTO record_entities(record_id, entity_id, role) VALUES (?,?,?)",
                                          (rid, pid, role))
                        self.link_identifiers(rid, name, addr, "email_display_name")
        return rid

    def add_media(self, fid, kind, ts, source, lat, lon, make, model, serial, software, width, height, duration_s, meta):
        self.conn.execute(
            "INSERT INTO media(file_id, media_kind, captured_utc, captured_raw, captured_source, time_flags, gps_lat, "
            "gps_lon, device_make, device_model, device_serial, software, width, height, duration_s, metadata_json) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (fid, kind, TimeValue.iso(ts.utc) if ts else None, ts.raw if ts else None, source,
             json.dumps(ts.flags if ts else []), lat, lon, make, model, serial, software, width, height, duration_s,
             canonical_json(meta or {})))

    def save_schema(self, fid, payload, decision, row_count, skipped) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO inferred_schemas(file_id, data_format, columns_json, column_map_json, "
            "type_scores_json, row_count, rows_skipped, skip_reasons_json) VALUES (?,?,?,?,?,?,?,?)",
            (fid, payload.get("data_format"), json.dumps(payload.get("columns")), json.dumps(decision.column_map),
             json.dumps(decision.scores), row_count, sum(dict(skipped).values()), json.dumps(dict(skipped))))

    def _link(self, a: int, b: int, rule: str, rid: int | None, conf: float) -> None:
        if a == b:
            return
        exists = self.conn.execute("SELECT 1 FROM entity_links WHERE ((entity_a=? AND entity_b=?) OR (entity_a=? AND entity_b=?)) AND rule=?",
                                   (a, b, b, a, rule)).fetchone()
        if not exists:
            self.conn.execute("INSERT INTO entity_links(entity_a, entity_b, rule, record_id, confidence) VALUES (?,?,?,?,?)",
                              (a, b, rule, rid, conf))

    def link_contact(self, rid: int, name, phone, email) -> None:
        ids = []
        if name and (k := person_key(str(name))):
            ids.append(self.entity_id("person", k, str(name)))
        if phone and (p := normalize_phone(str(phone), self.default_cc)):
            ids.append(self.entity_id("phone", p, str(phone)))
        if email and (e := normalize_email(str(email))):
            ids.append(self.entity_id("email", e, str(email)))
        for other in ids[1:]:
            self._link(ids[0], other, "contacts_entry", rid, 0.95)

    def link_identifiers(self, rid: int, name: str, addr: str, rule: str) -> None:
        k = person_key(name) if looks_like_person(name) else None  # "Cabinet Inventory <...>" is not a person
        if k and normalize_email(addr):
            self._link(self.entity_id("person", k, name), self.entity_id("email", normalize_email(addr), addr), rule, rid, 0.9)

    # ------------------------------------------------------------ post passes
    def _resolve_entities(self) -> None:
        people = self.conn.execute("SELECT entity_id, value_norm FROM entities WHERE entity_type='person'").fetchall()
        full = [(r["entity_id"], r["value_norm"].split()) for r in people if len(r["value_norm"].split()) >= 2]
        partial = [(r["entity_id"], r["value_norm"].split()) for r in people if len(r["value_norm"].split()) == 1]
        by_surname, by_first = {}, {}
        for eid, toks in full:
            by_surname.setdefault(toks[-1], set()).add(eid)
            by_first.setdefault(toks[0], set()).add(eid)
        full_map = dict(full)
        for eid, toks in full:
            # "D Vance" / "D. Vance" -> "Daniel Vance"
            if len(toks[0]) == 1:
                cands = {c for c in by_surname.get(toks[-1], set())
                         if c != eid and len(full_map[c][0]) > 1 and full_map[c][0].startswith(toks[0])}
                if len(cands) == 1:
                    self._link(eid, cands.pop(), "initial_and_surname", None, 0.8)
            # "Dan V" -> "Daniel Vance" (first-name prefix + surname initial), only when unambiguous
            elif len(toks) == 2 and len(toks[1]) == 1 and len(toks[0]) >= 3:
                cands = {c for c, ft in full if c != eid and len(ft[-1]) > 1 and ft[-1].startswith(toks[1])
                         and ft[0].startswith(toks[0])}
                if len(cands) == 1:
                    self._link(eid, cands.pop(), "first_name_prefix_and_surname_initial", None, 0.65)
        for eid, (tok,) in partial:
            if len(by_surname.get(tok, ())) == 1:
                self._link(eid, next(iter(by_surname[tok])), "unique_surname", None, 0.7)
            elif len(by_first.get(tok, ())) == 1:
                self._link(eid, next(iter(by_first[tok])), "unique_first_name", None, 0.6)
        # account hints taken from file names ("location_dvance.csv")
        for r in self.conn.execute("SELECT entity_id, display_name FROM entities WHERE entity_type='account' AND value_norm LIKE 'filename:%'").fetchall():
            tok = (r["display_name"] or "").lower()
            cands = {eid for eid, toks in full if tok in {toks[-1], toks[0][0] + toks[-1], toks[0] + toks[-1], toks[0]}}
            if len(cands) == 1:
                self._link(r["entity_id"], cands.pop(), "file_name_owner_hint", None, 0.6)

        parent = {r[0]: r[0] for r in self.conn.execute("SELECT entity_id FROM entities")}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for a, b in self.conn.execute("SELECT entity_a, entity_b FROM entity_links WHERE confidence >= 0.6"):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)
        # each group is represented by its most descriptive member: the longest person name, else email, phone, ...
        info = {r["entity_id"]: (r["entity_type"], r["value_norm"], r["display_name"] or "")
                for r in self.conn.execute("SELECT entity_id, entity_type, value_norm, display_name FROM entities")}
        rank = {"person": 0, "email": 1, "phone": 2, "account": 3, "device": 4, "sample": 5}
        groups: dict[int, list[int]] = {}
        for e in parent:
            groups.setdefault(find(e), []).append(e)
        updates = []
        for members in groups.values():
            # prefer the fullest, naturally written name ("Jordan Ellis" over "ELLIS, JORDAN")
            rep = min(members, key=lambda e: (rank.get(info[e][0], 9), -len(info[e][1].split()),
                                              info[e][2].isupper() or "," in info[e][2], e))
            updates += [(rep, e) for e in members]
        self.conn.executemany("UPDATE entities SET canonical_id=? WHERE entity_id=?", updates)
        n_links = self.conn.execute("SELECT COUNT(*) FROM entity_links").fetchone()[0]
        n_canon = self.conn.execute("SELECT COUNT(DISTINCT canonical_id) FROM entities").fetchone()[0]
        self.audit.write("resolve", "entities_resolved", {"links": n_links, "entities": len(parent), "canonical_entities": n_canon})

    def _link_mentions(self) -> None:
        names: dict[str, set[int]] = {}
        for r in self.conn.execute("SELECT entity_id, value_norm, display_name FROM entities WHERE entity_type='person'"):
            toks = r["value_norm"].split()
            if len(toks) >= 2:
                names.setdefault(" ".join(toks), set()).add(r["entity_id"])
                for t in (toks[0], toks[-1]):
                    if len(t) >= 3 and t not in _MENTION_STOP:
                        names.setdefault(t, set()).add(r["entity_id"])
        unique = {k: next(iter(v)) for k, v in names.items() if len(v) == 1}
        pattern = re.compile(r"\b(" + "|".join(sorted((re.escape(k) for k in unique), key=len, reverse=True)) + r")\b", re.I) if unique else None
        added = 0
        rows = self.conn.execute("SELECT record_id, content FROM records WHERE content IS NOT NULL AND record_type IN "
                                 "('message','email','statement_claim','interview_turn','document_chunk','lab_finding','lab_note','event')").fetchall()
        for r in rows:
            text = r["content"]
            found: set[int] = set()
            if pattern:
                for m in pattern.finditer(text):
                    found.add(unique[m.group(1).lower()])
            for m in EMAIL_RE.finditer(text):
                found.add(self.entity_id("email", m.group(0).lower(), m.group(0)))
            for m in PHONE_RE.finditer(text):
                p = normalize_phone(m.group(0), self.default_cc)
                if p and len(re.sub(r"\D", "", m.group(0))) >= 10:
                    found.add(self.entity_id("phone", p, m.group(0)))
            for eid in found:
                cur = self.conn.execute("INSERT OR IGNORE INTO record_entities(record_id, entity_id, role) VALUES (?,?, 'mentioned')", (r["record_id"], eid))
                added += cur.rowcount
        self.audit.write("resolve", "mentions_linked", {"mention_links": added})

    def _flag_cross_source_duplicates(self) -> None:
        seen: dict[tuple, int] = {}
        flagged = 0
        for r in self.conn.execute("SELECT record_id, file_id, record_type, ts_utc, content FROM records "
                                   "WHERE record_type IN ('message','call','email') AND ts_utc IS NOT NULL ORDER BY record_id").fetchall():
            key = (r["record_type"], r["ts_utc"][:16], re.sub(r"\W+", " ", (r["content"] or "").lower()).strip())
            if key in seen and seen[key][1] != r["file_id"]:
                self.conn.execute("UPDATE records SET duplicate_of=? WHERE record_id=?", (seen[key][0], r["record_id"]))
                flagged += 1
            else:
                seen.setdefault(key, (r["record_id"], r["file_id"]))
        self.audit.write("clean", "cross_source_duplicates_flagged", {"records": flagged})


def _rmtree_readonly(path: Path) -> None:
    import os
    import stat

    # Only ever delete a directory that is clearly a previous Mapletrace run.
    if not ((path / "run_manifest.json").exists() or (path / "case.db").exists()):
        raise FileExistsError(f"{path} is not empty and does not look like a previous Mapletrace run; refusing to delete it")

    def onexc(func, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    shutil.rmtree(path, onexc=onexc)


def ingest_zip(zip_path: str | Path, out_dir: str | Path, **kwargs) -> dict:
    """Programmatic entry point (used by the API layer)."""
    opts = IngestOptions(**kwargs)
    return Ingestor(Path(out_dir), opts).run(Path(zip_path))


__all__ = ["IngestOptions", "Ingestor", "ingest_zip", "IntakeError"]
