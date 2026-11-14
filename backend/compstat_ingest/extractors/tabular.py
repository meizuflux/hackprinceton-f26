"""Structured tables: messages, call logs, location history, contacts, generic event logs."""

from __future__ import annotations

from collections import Counter

from ..classify import norm_col
from ..entities import looks_like_person
from ..timeparse import parse_timestamp
from . import Outcome


def _row_time(ctx, row: dict, cmap: dict):
    ts_col = cmap.get("timestamp")
    date_col = cmap.get("date_only")
    if ts_col and norm_col(ts_col) in {"time", "clock", "eventtime"} and date_col and date_col != ts_col:
        combined = f"{row.get(date_col, '')} {row.get(ts_col, '')}".strip()
        return parse_timestamp(combined, ctx.tz, ctx.dayfirst)
    if ts_col:
        return parse_timestamp(row.get(ts_col), ctx.tz, ctx.dayfirst)
    if date_col:
        return parse_timestamp(row.get(date_col), ctx.tz, ctx.dayfirst)
    return None


def _float(v):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def _scaled(row: dict, cmap: dict, role: str):
    """Read a coordinate, undoing the E7 integer encoding used by Google exports (latitudeE7)."""
    col = cmap.get(role)
    if not col:
        return None
    v = _float(row.get(col))
    if v is not None and norm_col(col).endswith("e7"):
        v /= 1e7
    return v


def _device(v, role="device"):
    """Device identifiers (handsets, cameras, trackers) are their own entity type, never people."""
    if v in (None, ""):
        return (None, role)
    return (("device", str(v).strip().lower(), str(v).strip()), role)


def _extras(row: dict, used: set[str]) -> dict:
    return {k: v for k, v in row.items() if k not in used and v not in (None, "")}


def extract_table(ctx, file_id: int, evidence_type: str, payload: dict, decision) -> Outcome:
    rows: list[dict] = payload["rows"]
    cmap: dict = decision.column_map
    used_cols = {c for v in cmap.values() for c in v.split("|")}
    skipped: Counter = Counter()
    seen: set[tuple] = set()
    created = 0
    file_owner = ctx.file_owner_hint(file_id)

    for idx, row in enumerate(rows):
        sig = tuple(sorted((k, str(v)) for k, v in row.items()))
        if sig in seen:
            skipped["exact_duplicate_row"] += 1
            continue
        seen.add(sig)
        if all(v in (None, "") for v in row.values()):
            skipped["empty_row"] += 1
            continue
        locator = {"row": idx + 2 if payload.get("data_format") == "csv" else idx, "row_kind": "line" if payload.get("data_format") == "csv" else "index"}
        ts = _row_time(ctx, row, cmap)
        extras = _extras(row, used_cols)
        if ts is None and (cmap.get("timestamp") or cmap.get("date_only")):
            extras["_time_unparsed"] = row.get(cmap.get("timestamp") or cmap.get("date_only"))

        if evidence_type == "messages":
            body = row.get(cmap["body"])
            sender, recipient = row.get(cmap.get("sender", ""), None), row.get(cmap.get("recipient", ""), None)
            if not (sender or recipient) and cmap.get("party"):
                # phone-extraction layout: one "other party" column plus a direction
                party = row.get(cmap["party"]) or row.get(cmap.get("party_name", ""), None)
                outgoing = str(row.get(cmap.get("direction", ""), "")).lower().startswith(("out", "sent"))
                sender, recipient = (file_owner, party) if outgoing else (party, file_owner)
                if cmap.get("party_name") and row.get(cmap["party_name"]):
                    extras["party_name"] = row.get(cmap["party_name"])
            rid = ctx.add_record(file_id, "message", ts=ts, actor=sender, target=recipient, content=body,
                                 attributes=extras, locator=locator, reliability="recorded",
                                 entities=[(sender, "sender"), (recipient, "recipient")])
        elif evidence_type == "call_log":
            sender, recipient = row.get(cmap.get("sender", ""), None), row.get(cmap.get("recipient", ""), None)
            direction = row.get(cmap.get("direction", ""), None)
            if not sender and not recipient:
                # carrier records: the subscriber (msisdn) owns the record, the other party is the counterpart
                other = row.get(cmap.get("party", ""), None) or (None if cmap.get("party") else row.get(cmap.get("phone", ""), None))
                owner = file_owner or (row.get(cmap["phone"]) if cmap.get("party") and cmap.get("phone") else None)                     or row.get(cmap.get("device", ""), None)
                incoming = str(direction or "").lower().startswith(("in", "recv", "mt"))
                sender, recipient = (other, owner) if incoming else (owner, other)
            dur = _float(row.get(cmap.get("duration", "")))
            kind = row.get(cmap.get("event", ""), None) or "call"
            attrs = {**extras, "duration_s": dur, "direction": direction, "event_type": kind}
            lat, lon = _scaled(row, cmap, "lat"), _scaled(row, cmap, "lon")
            content = f"{(direction or '').lower()} {str(kind).lower()}, {int(dur) if dur is not None else '?'}s".strip()
            rid = ctx.add_record(file_id, "call", ts=ts, actor=sender or file_owner, target=recipient, content=content,
                                 lat=lat, lon=lon, attributes=attrs, locator=locator, reliability="recorded",
                                 entities=[(sender or file_owner, "caller"), (recipient, "callee")])
        elif evidence_type == "location":
            lat, lon = _scaled(row, cmap, "lat"), _scaled(row, cmap, "lon")
            if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180) or (lat == 0 and lon == 0):
                skipped["invalid_coordinates"] += 1
                continue
            device = row.get(cmap.get("device", ""), None)
            acc = _float(row.get(cmap.get("accuracy", "")))
            attrs = {**extras, "accuracy_m": acc, **({"device": device} if device else {})}
            place = row.get(cmap.get("location_name", ""), None)
            rid = ctx.add_record(file_id, "location_fix", ts=ts, actor=file_owner or device, lat=lat, lon=lon,
                                 content=place or f"{lat:.5f}, {lon:.5f}", attributes=attrs, locator=locator,
                                 reliability="recorded", entities=[(file_owner, "device_owner"), _device(device)])
        elif evidence_type == "contacts":
            name = row.get(cmap["name"])
            phone = row.get(cmap.get("phone", ""), None)
            email = row.get(cmap.get("email", ""), None)
            rid = ctx.add_record(file_id, "contact", ts=None, actor=file_owner, target=name,
                                 content=", ".join(str(x) for x in (name, phone, email) if x),
                                 attributes=extras, locator=locator, reliability="recorded",
                                 entities=[(name, "contact"), (phone, "contact"), (email, "contact")])
            ctx.link_contact(rid, name, phone, email)
        else:  # generic timestamped records (CCTV analytics, badge access, app logs, ...)
            candidates = [row.get(cmap.get(r, ""), None) for r in ("name", "sender")]
            person = next((c for c in candidates if c and looks_like_person(c)), None)
            device = row.get(cmap.get("device", ""), None)
            actor = person or device or next((c for c in candidates if c), None)
            event = row.get(cmap.get("event", ""), None) or row.get(cmap.get("body", ""), None)
            place = row.get(cmap.get("location_name", ""), None)
            lat, lon = _scaled(row, cmap, "lat"), _scaled(row, cmap, "lon")
            summary = event or "; ".join(f"{k}={v}" for k, v in list(extras.items())[:6])
            if place:
                summary = f"{summary} @ {place}"
            rid = ctx.add_record(file_id, "event", ts=ts, actor=actor, content=summary, lat=lat, lon=lon,
                                 attributes={**extras, **({"event": event} if event else {}), **({"place": place} if place else {})},
                                 locator=locator, reliability="recorded",
                                 entities=[(person, "subject"), _device(device)]
                                 + [(c, "subject") for c in candidates if c and c != person])
        created += 1

    ctx.save_schema(file_id, payload, decision, len(rows), skipped)
    notes = [f"{created} records from {len(rows)} rows"] + [f"skipped {n} {why.replace('_', ' ')}" for why, n in skipped.items()]
    status = "parsed" if created else "partial"
    return Outcome(status, "tabular", notes)
