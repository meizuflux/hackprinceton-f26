"""Coverage report: what was ingested, how reliable its timing is, and what is missing."""

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path

from .db import verify_audit_chain

EXPECTED_TYPES = {
    "messages": "text messages / chats",
    "call_log": "call records",
    "location": "phone or vehicle location data",
    "photo": "photos",
    "video": "video (e.g. CCTV)",
    "statement": "witness statements",
    "interview": "suspect/witness interviews",
    "dna": "biological / lab results",
    "email": "email",
}


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def build_report(conn: sqlite3.Connection) -> dict:
    q = lambda sql, *a: conn.execute(sql, a).fetchall()  # noqa: E731
    one = lambda sql, *a: conn.execute(sql, a).fetchone()[0]  # noqa: E731

    case = {r["key"]: r["value"] for r in q("SELECT key, value FROM case_info")}
    files = q("SELECT file_id, original_path, evidence_type, type_confidence, type_reason, parse_status, parser, "
              "record_count, parse_notes, sha256, size_bytes, external_id FROM evidence_files ORDER BY file_id")
    manifest_check = conn.execute("SELECT detail_json FROM audit_log WHERE action='manifest_hashes_checked' ORDER BY seq DESC LIMIT 1").fetchone()
    manifest_check = json.loads(manifest_check[0]) if manifest_check else None
    by_type: dict[str, dict] = {}
    for f in files:
        t = by_type.setdefault(f["evidence_type"] or "unknown", {"files": 0, "records": 0})
        t["files"] += 1
        t["records"] += f["record_count"]

    flags = Counter()
    for r in q("SELECT ts_flags FROM records"):
        for fl in json.loads(r["ts_flags"] or "[]"):
            flags[fl.split("=")[0]] += 1
    span = conn.execute("SELECT MIN(ts_utc), MAX(ts_utc) FROM records WHERE ts_utc IS NOT NULL AND duplicate_of IS NULL").fetchone()

    # largest silences in the machine-recorded timeline (candidate evidence gaps)
    times = [_dt(r[0]) for r in q("SELECT ts_utc FROM records WHERE ts_utc IS NOT NULL AND duplicate_of IS NULL "
                                  "AND reliability='recorded' ORDER BY ts_utc")]
    gaps = sorted(((b - a).total_seconds(), a, b) for a, b in zip(times, times[1:]))[-5:][::-1]

    present = {t for t in by_type}
    missing_types = [{"type": t, "description": d} for t, d in EXPECTED_TYPES.items() if t not in present]
    problem_files = [{"file": f["original_path"], "status": f["parse_status"], "notes": json.loads(f["parse_notes"] or "[]")}
                     for f in files if f["parse_status"] in {"failed", "unsupported", "partial"}]

    top_entities = [dict(r) for r in q(
        "SELECT c.entity_id, c.entity_type, COALESCE(c.display_name, c.value_norm) AS name, "
        "COUNT(DISTINCT re.record_id) AS records, "
        "(SELECT COUNT(*) FROM entities a WHERE a.canonical_id = c.entity_id) AS aliases "
        "FROM entities e JOIN entities c ON c.entity_id = e.canonical_id "
        "JOIN record_entities re ON re.entity_id = e.entity_id "
        "GROUP BY c.entity_id ORDER BY records DESC LIMIT 15")]

    ok, chain_msg = verify_audit_chain(conn)
    return {
        "case": case,
        "totals": {
            "files": len(files),
            "records": one("SELECT COUNT(*) FROM records"),
            "timestamped_records": one("SELECT COUNT(*) FROM records WHERE ts_utc IS NOT NULL"),
            "media_items": one("SELECT COUNT(*) FROM media"),
            "entities": one("SELECT COUNT(*) FROM entities"),
            "canonical_entities": one("SELECT COUNT(DISTINCT canonical_id) FROM entities"),
            "entity_links": one("SELECT COUNT(*) FROM entity_links"),
            "cross_source_duplicates": one("SELECT COUNT(*) FROM records WHERE duplicate_of IS NOT NULL"),
        },
        "time_span_utc": {"earliest": span[0], "latest": span[1]},
        "by_evidence_type": by_type,
        "by_record_type": {r[0]: r[1] for r in q("SELECT record_type, COUNT(*) FROM records GROUP BY 1 ORDER BY 2 DESC")},
        "by_reliability": {r[0]: r[1] for r in q("SELECT reliability, COUNT(*) FROM records GROUP BY 1")},
        "time_quality": {
            "records_without_time": one("SELECT COUNT(*) FROM records WHERE ts_utc IS NULL"),
            "flags": dict(flags.most_common()),
        },
        "top_entities": top_entities,
        "coverage_gaps": {
            "evidence_types_not_submitted": missing_types,
            "files_needing_attention": problem_files,
            "largest_timeline_silences": [{"hours": round(s / 3600, 2), "from": a.isoformat(), "to": b.isoformat()} for s, a, b in gaps if s > 0],
            "human_times_without_date": flags.get("date_unknown", 0),
            "photos_without_gps": one("SELECT COUNT(*) FROM media WHERE media_kind='photo' AND gps_lat IS NULL"),
            "media_without_capture_time": one("SELECT COUNT(*) FROM media WHERE captured_source IN ('none','container_mtime')"),
        },
        "manifest_check": manifest_check,
        "files": [{"file_id": f["file_id"], "evidence_id": f["external_id"], "path": f["original_path"], "type": f["evidence_type"],
                   "confidence": f["type_confidence"], "why": f["type_reason"], "status": f["parse_status"],
                   "parser": f["parser"], "records": f["record_count"], "sha256": f["sha256"],
                   "notes": json.loads(f["parse_notes"] or "[]")} for f in files],
        "audit": {"chain_valid": ok, "detail": chain_msg},
    }


def write_summary_markdown(report: dict, path: Path) -> None:
    c, t = report["case"], report["totals"]
    lines = [
        f"# Ingestion summary: {c.get('case_name')}",
        "",
        f"- Source archive: `{c.get('source_archive')}` (SHA-256 `{c.get('source_archive_sha256', '')[:16]}…`)",
        f"- Ingested: {c.get('ingested_at_utc')} · assumed time zone: {c.get('assumed_timezone')}",
        f"- {t['files']} files → {t['records']} records ({t['timestamped_records']} on the timeline), "
        f"{t['media_items']} media items, {t['canonical_entities']} distinct entities",
        f"- Time span: {report['time_span_utc']['earliest']} → {report['time_span_utc']['latest']}",
        f"- Audit chain: {'valid' if report['audit']['chain_valid'] else 'INVALID'} ({report['audit']['detail']})",
    ]
    mc = report.get("manifest_check")
    if mc:
        lines.append(f"- Manifest hash check: {mc['matched']} files match"
                     + (f"; MISMATCH: {', '.join(mc['mismatched'])}" if mc["mismatched"] else "")
                     + (f"; listed but missing: {', '.join(mc['listed_but_missing'])}" if mc["listed_but_missing"] else ""))
    lines += [
        "",
        "## Evidence by type",
        "",
        "| Type | Files | Records |",
        "|---|---|---|",
    ]
    for typ, v in sorted(report["by_evidence_type"].items(), key=lambda kv: -kv[1]["records"]):
        lines.append(f"| {typ} | {v['files']} | {v['records']} |")
    lines += ["", "## Files", "", "| File | Type (confidence) | Status | Records | Why this type |", "|---|---|---|---|---|"]
    for f in report["files"]:
        lines.append(f"| `{f['path']}` | {f['type']} ({f['confidence']}) | {f['status']} | {f['records']} | {f['why'] or ''} |")
    lines += ["", "## Key entities", ""]
    for e in report["top_entities"][:10]:
        lines.append(f"- {e['name']} ({e['entity_type']}): {e['records']} records" + (f", {e['aliases']} linked identifiers" if e["aliases"] > 1 else ""))
    g = report["coverage_gaps"]
    lines += ["", "## Gaps and caveats", ""]
    if g["evidence_types_not_submitted"]:
        lines.append("- Not in this submission: " + ", ".join(m["description"] for m in g["evidence_types_not_submitted"]))
    for f in g["files_needing_attention"]:
        lines.append(f"- `{f['file']}`: {f['status']}: {'; '.join(f['notes'])}")
    for s in g["largest_timeline_silences"][:3]:
        lines.append(f"- No machine-recorded activity for {s['hours']} h ({s['from']} → {s['to']})")
    tq = report["time_quality"]
    if tq["flags"]:
        lines.append("- Timestamp assumptions: " + ", ".join(f"{k} ×{v}" for k, v in tq["flags"].items()))
    if g["human_times_without_date"]:
        lines.append(f"- {g['human_times_without_date']} times mentioned in statements could not be dated")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
