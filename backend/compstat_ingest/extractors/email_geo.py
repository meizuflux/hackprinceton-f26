"""Email (EML / mbox, with attachments re-ingested) and GPS tracks (GPX / KML)."""

from __future__ import annotations

import hashlib
import mailbox
import re
from datetime import timezone
from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from pathlib import Path

from ..entities import parse_named_address, split_people_field
from ..timeparse import exact, parse_timestamp
from . import Outcome


def _body_text(msg) -> str:
    try:
        part = msg.get_body(preferencelist=("plain", "html"))
    except (KeyError, AttributeError):
        part = None
    if part is None:
        return ""
    try:
        text = part.get_content()
    except (LookupError, ValueError):
        text = part.get_payload(decode=True) or b""
        text = text.decode("utf-8", errors="replace") if isinstance(text, bytes) else str(text)
    if part.get_content_type() == "text/html":
        text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _ingest_message(ctx, file_id: int, msg, locator: dict) -> int:
    raw_date = msg.get("Date")
    ts = None
    if raw_date:
        try:
            dt = parsedate_to_datetime(str(raw_date))
            flags = []
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=ctx.tz)
                flags.append("tz_assumed")
            ts = exact(dt, str(raw_date), "second", flags)
        except (TypeError, ValueError):
            ts = parse_timestamp(str(raw_date), ctx.tz, ctx.dayfirst)
    sender = str(msg.get("From", "") or "")
    recipients = ", ".join(str(msg.get(h, "") or "") for h in ("To", "Cc", "Bcc") if msg.get(h))
    subject = str(msg.get("Subject", "") or "")
    body = _body_text(msg)
    attachments = []
    for att in msg.iter_attachments():
        name = att.get_filename() or "attachment.bin"
        data = att.get_payload(decode=True) or b""
        attachments.append({"filename": name, "size": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                            "content_type": att.get_content_type()})
        ctx.add_derived_file(file_id, name, data, "email_attachment")
    ents = [(sender, "sender")] + [(r, "recipient") for r in split_people_field(recipients)] if recipients else [(sender, "sender")]
    attrs = {"subject": subject, "message_id": str(msg.get("Message-ID", "") or ""), "to": recipients,
             "attachments": attachments, "x_mailer": str(msg.get("X-Mailer", "") or "") or None}
    received = msg.get_all("Received") or []
    if received:
        attrs["received_hops"] = len(received)
    rid = ctx.add_record(file_id, "email", ts=ts, actor=sender, target=recipients or None,
                         content=(f"Subject: {subject}\n\n{body}").strip(), attributes=attrs,
                         locator=locator, reliability="recorded", entities=ents)
    name, addr = parse_named_address(sender)
    if name and addr:
        ctx.link_identifiers(rid, name, addr, "email_display_name")
    return len(attachments)


def extract_email(ctx, file_id: int, path: Path, fmt: str) -> Outcome:
    if fmt == "mbox":
        box = mailbox.mbox(str(path), create=False)
        n = att = 0
        for i, msg in enumerate(box):
            m = BytesParser(policy=policy.default).parsebytes(msg.as_bytes())
            att += _ingest_message(ctx, file_id, m, {"mbox_index": i})
            n += 1
        box.close()
        return Outcome("parsed" if n else "partial", "mbox", [f"{n} emails", f"{att} attachments extracted for ingestion"])
    with open(path, "rb") as fh:
        msg = BytesParser(policy=policy.default).parse(fh)
    att = _ingest_message(ctx, file_id, msg, {"message": 0})
    return Outcome("parsed", "eml", [f"1 email; {att} attachments extracted for ingestion"])


# --------------------------------------------------------------------------- #
# Calendars (iCalendar / .ics)
# --------------------------------------------------------------------------- #


def _ics_unescape(v: str) -> str:
    return v.replace("\\n", "\n").replace("\\N", "\n").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")


def _ics_time(value: str, params: dict, default_tz):
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    from ..timeparse import TimeValue
    v = value.strip()
    if params.get("VALUE") == "DATE" or len(v) == 8:
        d = datetime.strptime(v[:8], "%Y%m%d").replace(tzinfo=default_tz)
        return TimeValue(d + timedelta(hours=12), d, d + timedelta(days=1, seconds=-1), v, "day", ["all_day_event"])
    flags = []
    dt = datetime.strptime(v.rstrip("Z")[:15], "%Y%m%dT%H%M%S")
    if v.endswith("Z"):
        dt = dt.replace(tzinfo=timezone.utc)
    elif params.get("TZID"):
        try:
            dt = dt.replace(tzinfo=ZoneInfo(params["TZID"].strip('"')))
        except ZoneInfoNotFoundError:
            dt = dt.replace(tzinfo=default_tz)
            flags.append("unknown_tzid_tz_assumed")
    else:
        dt = dt.replace(tzinfo=default_tz)
        flags.append("tz_assumed")
    return exact(dt, (f"TZID={params['TZID']}:" if params.get("TZID") else "") + v, "second", flags)


def extract_calendar(ctx, file_id: int, path: Path) -> Outcome:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    from ..intake import decode_text_file
    from ..timeparse import TimeValue
    text, _ = decode_text_file(path)
    lines, starts = [], []
    for i, raw in enumerate(text.splitlines()):
        if raw[:1] in (" ", "\t") and lines:
            lines[-1] += raw[1:]  # RFC 5545 line folding
        else:
            lines.append(raw)
            starts.append(i + 1)
    cal_name, cal_tz, ev, n, created = None, ctx.tz, None, 0, 0
    for line, ln in zip(lines, starts):
        name, _, value = line.partition(":")
        key, *params = name.split(";")
        key = key.upper()
        p = dict(x.split("=", 1) for x in params if "=" in x)
        if key == "X-WR-CALNAME":
            cal_name = value
        elif key == "X-WR-TIMEZONE":
            try:
                cal_tz = ZoneInfo(value.strip())
            except ZoneInfoNotFoundError:
                pass
        elif key == "BEGIN" and value.upper() == "VEVENT":
            ev = {"_line": ln, "ATTENDEE": []}
        elif key == "END" and value.upper() == "VEVENT" and ev is not None:
            n += 1
            start = _ics_time(*ev["DTSTART"], cal_tz) if "DTSTART" in ev else None
            end = _ics_time(*ev["DTEND"], cal_tz) if "DTEND" in ev else None
            ts = None
            if start:
                ts = TimeValue(start.utc, start.start, end.end if end else start.end, start.raw,
                               start.precision, start.flags + (["window_is_event_span"] if end else []))
            organizer = ev.get("ORGANIZER", "").replace("mailto:", "").replace("MAILTO:", "") or None
            attendees = [a.replace("mailto:", "").replace("MAILTO:", "") for a in ev["ATTENDEE"]]
            summary = _ics_unescape(ev.get("SUMMARY", "(no title)"))
            location = _ics_unescape(ev.get("LOCATION", "")) or None
            attrs = {k.lower(): _ics_unescape(v) for k, v in ev.items() if isinstance(v, str) and k not in {"SUMMARY"}}
            attrs.update({"attendees": attendees, "calendar": cal_name, "end": end.to_dict() if end else None})
            ents = [(organizer, "organizer")] + [(a, "attendee") for a in attendees] + [(cal_name, "calendar_owner")]
            ctx.add_record(file_id, "calendar_event", ts=ts, actor=cal_name or organizer,
                           content=summary + (f" @ {location}" if location else ""), attributes=attrs,
                           locator={"line": ev["_line"], "vevent_index": n, "uid": ev.get("UID")},
                           reliability="recorded", entities=ents)
            created += 1
            ev = None
        elif ev is not None:
            if key in {"DTSTART", "DTEND"}:
                ev[key] = (value, p)
            elif key == "ATTENDEE":
                ev["ATTENDEE"].append(value)
            else:
                ev[key] = value
    return Outcome("parsed" if created else "partial", "icalendar", [f"{created} calendar events", f"calendar: {cal_name or 'unnamed'}"])


# --------------------------------------------------------------------------- #
# Google semantic location history ("timelineObjects": placeVisit / activitySegment)
# --------------------------------------------------------------------------- #


def _e7(v):
    try:
        return float(v) / 1e7
    except (TypeError, ValueError):
        return None


def extract_takeout(ctx, file_id: int, data: dict) -> Outcome:
    from ..timeparse import TimeValue
    owner = ctx.file_owner_hint(file_id)
    visits = moves = skipped = low = 0
    for i, obj in enumerate(data.get("timelineObjects", [])):
        kind = "placeVisit" if "placeVisit" in obj else "activitySegment" if "activitySegment" in obj else None
        if not kind:
            skipped += 1
            continue
        item = obj[kind]
        dur = item.get("duration", {})
        start = parse_timestamp(dur.get("startTimestamp"), ctx.tz, ctx.dayfirst)
        end = parse_timestamp(dur.get("endTimestamp"), ctx.tz, ctx.dayfirst)
        ts = TimeValue(start.utc, start.start, end.end if end else start.end, f"{dur.get('startTimestamp')} / {dur.get('endTimestamp')}",
                       start.precision, start.flags + ["window_is_visit_span"]) if start else None
        loc_key = "location" if kind == "placeVisit" else "startLocation"
        loc = item.get(loc_key, {})
        lat, lon = _e7(loc.get("latitudeE7")), _e7(loc.get("longitudeE7"))
        if lat is None or lon is None:
            skipped += 1
            continue
        conf = item.get("placeConfidence") or item.get("confidence")
        attrs = {k: v for k, v in item.items() if not isinstance(v, (dict, list))}
        if kind == "placeVisit":
            attrs.update({k: v for k, v in loc.items() if k not in {"latitudeE7", "longitudeE7"}})
            content = loc.get("name") or loc.get("address") or f"{lat:.5f}, {lon:.5f}"
            rtype = "place_visit"
            visits += 1
        else:
            endloc = item.get("endLocation", {})
            attrs.update({"end_lat": _e7(endloc.get("latitudeE7")), "end_lon": _e7(endloc.get("longitudeE7")),
                          "activity_type": item.get("activityType")})
            content = f"{(item.get('activityType') or 'movement').lower().replace('_', ' ')}"
            rtype = "movement"
            moves += 1
        if conf and "LOW" in str(conf).upper():
            attrs["low_confidence"] = True
            low += 1
        ctx.add_record(file_id, rtype, ts=ts, actor=owner, lat=lat, lon=lon, content=content, attributes=attrs,
                       locator={"json_path": f"timelineObjects[{i}].{kind}", "id": item.get("visitId") or item.get("segmentId")},
                       reliability="recorded", entities=[(owner, "device_owner")])
    notes = [f"{visits} place visits, {moves} movement segments"]
    if low:
        notes.append(f"{low} low-confidence items kept and flagged (attributes.low_confidence)")
    if skipped:
        notes.append(f"skipped {skipped} items without coordinates")
    return Outcome("parsed" if visits + moves else "partial", "semantic_location_history", notes)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def extract_geo(ctx, file_id: int, path: Path, fmt: str) -> Outcome:
    from defusedxml import ElementTree as ET
    root = ET.parse(str(path)).getroot()
    owner = ctx.file_owner_hint(file_id)
    created = skipped = 0
    if fmt == "gpx":
        for i, el in enumerate(root.iter()):
            if _local(el.tag) not in {"trkpt", "wpt", "rtept"}:
                continue
            try:
                lat, lon = float(el.get("lat")), float(el.get("lon"))
            except (TypeError, ValueError):
                skipped += 1
                continue
            kids = {_local(c.tag): (c.text or "").strip() for c in el}
            ts = parse_timestamp(kids.get("time"), ctx.tz, ctx.dayfirst)
            attrs = {k: v for k, v in kids.items() if k in {"ele", "speed", "course", "name", "desc", "hdop"} and v}
            ctx.add_record(file_id, "location_fix", ts=ts, actor=owner, lat=lat, lon=lon,
                           content=kids.get("name") or f"{lat:.5f}, {lon:.5f}", attributes={"point_type": _local(el.tag), **attrs},
                           locator={"xml_element_index": i, "element": _local(el.tag)}, reliability="recorded",
                           entities=[(owner, "device_owner")])
            created += 1
    else:  # KML: Placemarks with Points, and gx:Track when/coord pairs
        for i, pm in enumerate(root.iter()):
            tag = _local(pm.tag)
            if tag == "Placemark":
                name = next((c.text for c in pm.iter() if _local(c.tag) == "name"), None)
                when = next((c.text for c in pm.iter() if _local(c.tag) in {"when", "begin"}), None)
                coords = next((c.text for c in pm.iter() if _local(c.tag) == "coordinates"), None)
                if not coords:
                    continue
                first = coords.strip().split()[0].split(",")
                try:
                    lon, lat = float(first[0]), float(first[1])
                except (IndexError, ValueError):
                    skipped += 1
                    continue
                ctx.add_record(file_id, "location_fix", ts=parse_timestamp(when, ctx.tz, ctx.dayfirst), actor=owner,
                               lat=lat, lon=lon, content=name or f"{lat:.5f}, {lon:.5f}", attributes={"placemark": name},
                               locator={"xml_element_index": i, "element": "Placemark"}, reliability="recorded",
                               entities=[(owner, "device_owner")])
                created += 1
            elif tag == "Track":
                whens = [c.text for c in pm if _local(c.tag) == "when"]
                coords = [c.text for c in pm if _local(c.tag) == "coord"]
                for j, (w, c) in enumerate(zip(whens, coords)):
                    parts = (c or "").split()
                    try:
                        lon, lat = float(parts[0]), float(parts[1])
                    except (IndexError, ValueError):
                        skipped += 1
                        continue
                    ctx.add_record(file_id, "location_fix", ts=parse_timestamp(w, ctx.tz, ctx.dayfirst), actor=owner,
                                   lat=lat, lon=lon, content=f"{lat:.5f}, {lon:.5f}", attributes={},
                                   locator={"xml_element_index": i, "track_point": j}, reliability="recorded",
                                   entities=[(owner, "device_owner")])
                    created += 1
    notes = [f"{created} location points"] + ([f"skipped {skipped} malformed points"] if skipped else [])
    if not owner:
        notes.append("track owner unknown (not in file name or metadata)")
    return Outcome("parsed" if created else "partial", fmt, notes)
