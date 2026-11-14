"""Photos (EXIF), video and audio (container metadata).

Content analysis (object detection, transcription) is a later stage; here we
capture *when, where and with what device* each item was recorded, and how
trustworthy that timestamp is.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ..timeparse import TimeValue, exact, parse_exif_datetime
from . import Outcome


def _ratio(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError, ZeroDivisionError):
        num, den = x
        return float(num) / float(den)


def _dms(values, ref) -> float | None:
    try:
        d, m, s = (_ratio(v) for v in values)
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    val = d + m / 60 + s / 3600
    if str(ref).upper().startswith(("S", "W")):
        val = -val
    return val


def _clean(v):
    if isinstance(v, bytes):
        v = v.decode("utf-8", errors="replace")
    return str(v).strip("\x00 ").strip() if v is not None else None


def _container_time_fallback(ctx, file_id: int):
    mtime = ctx.file_container_mtime(file_id)
    if not mtime:
        return None
    dt = datetime.fromisoformat(mtime).replace(tzinfo=ctx.tz)
    return TimeValue(dt, dt, dt, mtime, "second", ["container_mtime_only", "tz_assumed", "low_reliability"])


def extract_photo(ctx, file_id: int, path: Path) -> Outcome:
    from PIL import ExifTags, Image, UnidentifiedImageError
    notes = []
    try:
        with Image.open(path) as img:
            width, height = img.size
            exif = img.getexif()
            exif_ifd = exif.get_ifd(ExifTags.IFD.Exif)
            gps = exif.get_ifd(ExifTags.IFD.GPSInfo)
            fmt = img.format
    except (UnidentifiedImageError, OSError) as exc:
        return Outcome("failed", "photo_exif", [f"could not open image: {exc}"])

    ts = parse_exif_datetime(_clean(exif_ifd.get(36867) or exif_ifd.get(36868) or exif.get(306)),
                             _clean(exif_ifd.get(36881) or exif_ifd.get(36880)), ctx.tz)
    source = "exif"
    if ts is None:
        ts = _container_time_fallback(ctx, file_id)
        source = "container_mtime" if ts else "none"
        notes.append("no EXIF capture time" + ("; using archive modification time (weak)" if ts else ""))
    lat = lon = None
    if gps:
        lat, lon = _dms(gps.get(2), gps.get(1)), _dms(gps.get(4), gps.get(3))
        if lat is not None and lon is not None and lat == 0 and lon == 0:
            lat = lon = None
    make, model = _clean(exif.get(271)), _clean(exif.get(272))
    serial = _clean(exif_ifd.get(42033))
    software = _clean(exif.get(305))
    device = " ".join(x for x in (make, model) if x) or None
    meta = {
        "format": fmt, "orientation": exif.get(274), "lens": _clean(exif_ifd.get(42036)),
        "exposure_time": str(exif_ifd.get(33434)) if exif_ifd.get(33434) else None,
        "artist": _clean(exif.get(315)), "description": _clean(exif.get(270)),
        "user_comment": _clean(exif_ifd.get(37510)),
    }
    meta = {k: v for k, v in meta.items() if v not in (None, "")}
    if software:
        meta["software"] = software
        if any(s in software.lower() for s in ("photoshop", "gimp", "lightroom", "snapseed", "picsart")):
            meta["edited_with"] = software
            notes.append(f"image processed by editing software: {software}")
    ctx.add_media(file_id, "photo", ts, source, lat, lon, make, model, serial, software, width, height, None, meta)
    name = ctx.file_original_path(file_id)
    content = f"Photo {name} captured" + (f" with {device}" if device else "") + (f" at {lat:.5f}, {lon:.5f}" if lat is not None else "")
    ctx.add_record(file_id, "media_capture", ts=ts, actor=device, lat=lat, lon=lon, content=content,
                   attributes={"media_kind": "photo", "time_source": source, "device_serial": serial, **meta},
                   locator={"media": "exif"}, reliability="recorded",
                   entities=[(("device", (serial or device or "").lower(), device), "capture_device")] if device else [])
    if lat is None:
        notes.append("no GPS coordinates")
    return Outcome("parsed", "photo_exif", notes or ["EXIF capture time and device read"])


def extract_av(ctx, file_id: int, path: Path, kind: str) -> Outcome:
    notes: list[str] = []
    md = None
    try:
        from hachoir.core import config as hconfig
        from hachoir.metadata import extractMetadata
        from hachoir.parser import createParser
        hconfig.quiet = True
        parser = createParser(str(path))
        if parser:
            with parser:
                md = extractMetadata(parser)
    except Exception as exc:  # noqa: BLE001 - container parsers fail in many ways on damaged files
        notes.append(f"metadata parser error: {exc}")

    def get(key):
        try:
            return md.get(key) if md is not None and md.has(key) else None
        except (ValueError, KeyError):
            return None

    created = get("creation_date")
    ts, source = None, "none"
    if isinstance(created, datetime) and created.year > 1970:
        # MP4/MOV creation times are defined as UTC by the container spec
        dt = created if created.tzinfo else created.replace(tzinfo=timezone.utc)
        ts, source = exact(dt, created.isoformat(), "second", ["container_time_utc_by_spec"]), "container"
    else:
        ts = _container_time_fallback(ctx, file_id)
        if ts:
            source = "container_mtime"
            notes.append("no creation time in media container; using archive modification time (weak)")
        else:
            notes.append("no creation time found")
    duration = get("duration")
    duration_s = duration.total_seconds() if duration is not None else None
    width, height = get("width"), get("height")
    meta = {"mime_type": get("mime_type"), "producer": get("producer"), "comment": get("comment"),
            "frame_rate": get("frame_rate"), "sample_rate": get("sample_rate"), "nb_channel": get("nb_channel")}
    meta = {k: str(v) for k, v in meta.items() if v not in (None, "")}
    ctx.add_media(file_id, kind, ts, source, None, None, None, None, None, meta.get("producer"), width, height, duration_s, meta)
    name = ctx.file_original_path(file_id)
    content = f"{kind.capitalize()} {name}" + (f", {duration_s:.0f}s" if duration_s else "") + " recorded"
    end_ts = ts
    if ts and ts.utc and duration_s:
        from datetime import timedelta
        end_ts = TimeValue(ts.utc, ts.utc, ts.utc + timedelta(seconds=duration_s), ts.raw, ts.precision, ts.flags + ["window_is_recording_span"])
    ctx.add_record(file_id, "media_capture", ts=end_ts, content=content,
                   attributes={"media_kind": kind, "time_source": source, "duration_s": duration_s, **meta},
                   locator={"media": "container"}, reliability="recorded")
    notes.append("visual/audio content not analyzed at ingestion (transcription and detection run in a later stage)")
    return Outcome("parsed" if md is not None else "partial", f"{kind}_container", notes)
