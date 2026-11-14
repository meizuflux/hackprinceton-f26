"""Timestamp normalization.

Every timestamp becomes a TimeValue: a UTC point estimate plus an uncertainty
window, the raw text, a precision label and flags describing every assumption
made (e.g. that a naive time was in the case's local time zone). Human
statements ("around 11:30 pm") get wide windows; machine logs get exact ones.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from dateutil import parser as du_parser

UTC = timezone.utc


@dataclass
class TimeValue:
    utc: datetime | None
    start: datetime | None
    end: datetime | None
    raw: str
    precision: str
    flags: list[str] = field(default_factory=list)

    @staticmethod
    def iso(dt: datetime | None) -> str | None:
        if dt is None:
            return None
        return dt.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")

    def as_columns(self) -> dict:
        return {
            "ts_utc": self.iso(self.utc),
            "ts_start_utc": self.iso(self.start),
            "ts_end_utc": self.iso(self.end),
            "ts_raw": self.raw,
            "ts_precision": self.precision,
            "ts_flags": self.flags,
        }

    def to_dict(self) -> dict:
        return self.as_columns()


def exact(dt: datetime, raw: str, precision: str = "second", flags: list[str] | None = None) -> TimeValue:
    return TimeValue(dt, dt, dt, raw, precision, list(flags or []))


# --------------------------------------------------------------------------- #
# Machine timestamps (logs, CSV columns, EXIF, email headers)
# --------------------------------------------------------------------------- #

_NUMERIC = re.compile(r"^-?\d+(\.\d+)?$")
_HAS_SECONDS = re.compile(r"\d{1,2}:\d{2}:\d{2}")
_HAS_MINUTES = re.compile(r"\d{1,2}:\d{2}")
_HAS_AMPM_HOUR = re.compile(r"\b\d{1,2}\s*(a\.?m\.?|p\.?m\.?)\b", re.I)
_SLASH_DATE = re.compile(r"^\s*(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2,4})")

# Plausible range for evidence timestamps.
_MIN_YEAR, _MAX_YEAR = 1970, 2100
_EPOCH_RANGES = [  # (min, max, divisor, label)
    (3.0e8, 4.2e9, 1, "epoch_seconds"),
    (3.0e11, 4.2e12, 1e3, "epoch_milliseconds"),
    (3.0e14, 4.2e15, 1e6, "epoch_microseconds"),
]


_TZ_ABBREVIATIONS = {  # ambiguous worldwide, so only the North American ones evidence usually carries
    "PDT": "America/Los_Angeles", "PST": "America/Los_Angeles", "MDT": "America/Denver", "MST": "America/Denver",
    "CDT": "America/Chicago", "CST": "America/Chicago", "EDT": "America/New_York", "EST": "America/New_York",
    "UTC": "UTC", "GMT": "UTC", "Z": "UTC",
}
_TZINFOS = {k: ZoneInfo(v) for k, v in _TZ_ABBREVIATIONS.items()}


def _localize(dt: datetime, tz: ZoneInfo, flags: list[str]) -> datetime:
    if dt.tzinfo is None:
        flags.append("tz_assumed")
        return dt.replace(tzinfo=tz)
    return dt


def parse_timestamp(value, tz: ZoneInfo, dayfirst: bool = False) -> TimeValue | None:
    """Parse a machine-recorded timestamp. Returns None when nothing usable is present."""
    if value is None:
        return None
    if isinstance(value, datetime):
        flags: list[str] = []
        dt = _localize(value, tz, flags)
        return exact(dt, value.isoformat(), "second", flags)

    raw = str(value).strip()
    if not raw or raw.lower() in {"nan", "null", "none", "n/a", "na", "-", "unknown"}:
        return None

    if _NUMERIC.match(raw):
        num = float(raw)
        for lo, hi, div, label in _EPOCH_RANGES:
            if lo <= num <= hi:  # negative numbers are coordinates or offsets, never evidence times
                dt = datetime(1970, 1, 1, tzinfo=UTC) + timedelta(seconds=num / div)
                return exact(dt, raw, "second", [label])
        return None  # a bare number we can't interpret as time

    flags = []
    m = _SLASH_DATE.match(raw)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if a <= 12 and b <= 12 and a != b:
            flags.append("day_month_ambiguous")

    dt = None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00")) if "T" in raw or re.match(r"^\d{4}-\d{2}-\d{2}", raw) else None
    except ValueError:
        dt = None
    if dt is None:
        sentinel = datetime(1900, 1, 1)
        try:
            dt = du_parser.parse(raw, dayfirst=dayfirst, default=sentinel, tzinfos=_TZINFOS)
        except (ValueError, OverflowError, TypeError):
            return None
        if dt.year == 1900 and not re.search(r"1900", raw):
            return None  # a time of day with no date: not placeable on a timeline

    if not (_MIN_YEAR <= dt.year <= _MAX_YEAR):
        return None

    if _HAS_SECONDS.search(raw):
        precision = "second"
    elif _HAS_MINUTES.search(raw):
        precision = "minute"
    elif _HAS_AMPM_HOUR.search(raw):
        precision = "hour"
    else:
        precision = "day"

    dt = _localize(dt, tz, flags)
    if precision == "day":
        start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1) - timedelta(seconds=1)
        return TimeValue(start + timedelta(hours=12), start, end, raw, "day", flags)
    if precision == "minute":
        return TimeValue(dt, dt, dt + timedelta(seconds=59), raw, "minute", flags)
    if precision == "hour":
        return TimeValue(dt, dt, dt + timedelta(minutes=59, seconds=59), raw, "hour", flags)
    return exact(dt, raw, "second", flags)


def parse_exif_datetime(raw: str | None, offset: str | None, tz: ZoneInfo) -> TimeValue | None:
    if not raw:
        return None
    raw = str(raw).strip().strip("\x00")
    try:
        dt = datetime.strptime(raw[:19], "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return parse_timestamp(raw, tz)
    flags: list[str] = []
    if offset:
        try:
            sign = 1 if offset.strip()[0] == "+" else -1
            hh, mm = offset.strip()[1:].split(":")
            dt = dt.replace(tzinfo=timezone(sign * timedelta(hours=int(hh), minutes=int(mm))))
        except (ValueError, IndexError):
            flags.append("exif_offset_unparseable")
    if dt.tzinfo is None:
        flags.append("exif_no_offset")
    dt = _localize(dt, tz, flags)
    return exact(dt, raw + (f" {offset}" if offset else ""), "second", flags)


# --------------------------------------------------------------------------- #
# Human time references in free text (statements, interviews, lab notes)
# --------------------------------------------------------------------------- #

_QUAL = (
    r"sometime around|shortly after|shortly before|just after|just before|a little after|"
    r"a little before|around|about|approximately|approx\.?|roughly|maybe|probably|"
    r"before|after|by|until|till|at|~"
)
TIME_MENTION = re.compile(
    rf"(?:(?P<qual>{_QUAL})\s+)?"
    r"(?P<time>\b(?:[01]?\d|2[0-3])(?::[0-5]\d)?\s*(?:a\.?m\.?|p\.?m\.?)(?![a-z])"
    r"|\b(?:[01]?\d|2[0-3]):[0-5]\d\b"
    r"|\bmidnight\b|\bnoon\b)",
    re.I,
)
_MONTHS = "january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec"
DATE_MENTION = re.compile(
    r"\b\d{4}-\d{2}-\d{2}\b"
    r"|\b\d{1,2}/\d{1,2}/\d{2,4}\b"
    rf"|\b(?:{_MONTHS})\.?\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s+\d{{4}})?\b"
    rf"|\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:of\s+)?(?:{_MONTHS})\.?(?:,?\s+\d{{4}})?\b"
    # "on 10/17" / "Saturday 10/17": month/day without a year, only when clearly used as a date
    r"|\b(?:on|(?:mon|tues|wednes|thurs|fri|satur|sun)day)\s+(?:0?[1-9]|1[0-2])/(?:0?[1-9]|[12]\d|3[01])\b",
    re.I,
)
_HEADER_DATE = re.compile(
    r"^\s*(?:date of (?:incident|event|offen[cs]e)|incident date|date of interview|interview date|date)\s*[:\-]\s*(.+)$",
    re.I | re.M,
)


def _parse_human_date(text: str, ref_year: int | None, dayfirst: bool) -> date | None:
    try:
        default = datetime(ref_year or 1900, 1, 1)
        d = du_parser.parse(text, dayfirst=dayfirst, default=default, fuzzy=True)
    except (ValueError, OverflowError, TypeError):
        return None
    if d.year == 1900:
        return None
    return d.date()


def find_reference_date(text: str, dayfirst: bool = False) -> date | None:
    """Date given in a document header ('Date of incident: ...'), else the first date mentioned."""
    m = _HEADER_DATE.search(text)
    if m:
        d = _parse_human_date(m.group(1), None, dayfirst)
        if d:
            return d
    m = DATE_MENTION.search(text)
    if m:
        return _parse_human_date(m.group(0), None, dayfirst)
    return None


_EVENING = re.compile(r"\b(night|evening|tonight|late|bed|asleep|sleep|dark|dinner|pm|p\.m\.)\b", re.I)
_MORNING = re.compile(r"\b(morning|breakfast|woke|wake|sunrise|am|a\.m\.)\b", re.I)


def _to_hour_minute(token: str) -> tuple[int, int, str]:
    t = token.lower().replace(".", "").replace(" ", "")
    if t == "midnight":
        return 0, 0, "hour"
    if t == "noon":
        return 12, 0, "hour"
    ampm = None
    if t.endswith("am") or t.endswith("pm"):
        ampm, t = t[-2:], t[:-2]
    if ":" in t:
        h, m = (int(x) for x in t.split(":"))
        prec = "minute"
    else:
        h, m = int(t), 0
        prec = "hour"
    if ampm == "pm" and h < 12:
        h += 12
    if ampm == "am" and h == 12:
        h = 0
    return h, m, prec


def _window(qual: str | None, prec: str) -> tuple[timedelta, timedelta, str]:
    q = (qual or "").lower()
    if q in {"before", "by", "until", "till", "shortly before", "just before", "a little before"}:
        return timedelta(minutes=60 if "short" not in q and "just" not in q else 20), timedelta(0), "before"
    if q in {"after", "shortly after", "just after", "a little after"}:
        return timedelta(0), timedelta(minutes=60 if q == "after" else 20), "after"
    if q and q not in {"at"}:
        return timedelta(minutes=30), timedelta(minutes=30), "approximate"
    if prec == "minute":
        return timedelta(minutes=10), timedelta(minutes=10), "stated"
    return timedelta(minutes=30), timedelta(minutes=30), "stated"


@dataclass
class TimeMention:
    value: TimeValue
    char_start: int
    char_end: int
    qualifier: str


class HumanTimeResolver:
    """Resolves time mentions in narrative text, carrying the date forward and
    rolling over midnight when a narrative moves from late evening to early morning."""

    def __init__(self, tz: ZoneInfo, ref_date: date | None, dayfirst: bool = False):
        self.tz = tz
        self.current_date = ref_date
        self.dayfirst = dayfirst
        self.last_dt: datetime | None = None

    def resolve(self, sentence: str, offset: int = 0) -> list[TimeMention]:
        for dm in DATE_MENTION.finditer(sentence):
            d = _parse_human_date(dm.group(0), self.current_date.year if self.current_date else None, self.dayfirst)
            if d:
                self.current_date = d
                self.last_dt = None
        out: list[TimeMention] = []
        for m in TIME_MENTION.finditer(sentence):
            token = m.group("time")
            # skip things like "3:1" ratios or list numbering that slipped through
            h, mi, prec = _to_hour_minute(token)
            before, after, kind = _window(m.group("qual"), prec)
            flags = ["human_reported"]
            if token.lower() == "midnight":
                flags.append("midnight_ambiguous")
            if self.current_date is None:
                tv = TimeValue(None, None, None, m.group(0).strip(), "approximate", flags + ["date_unknown"])
                tv.flags.append(f"time_of_day={h:02d}:{mi:02d}")
            else:
                d = self.current_date
                explicit = bool(re.search(r"[ap]\.?m", token, re.I)) or token.lower() in {"midnight", "noon"}
                local = datetime.combine(d, time(h, mi), tzinfo=self.tz)
                if not explicit and 1 <= h <= 11:
                    # "around 10:30" with no am/pm: decide from narrative order, then from context words
                    if self.last_dt is not None:
                        cands = [datetime.combine(d, time(h, mi), tzinfo=self.tz),
                                 datetime.combine(d, time(h + 12, mi), tzinfo=self.tz),
                                 datetime.combine(d + timedelta(days=1), time(h, mi), tzinfo=self.tz)]
                        later = [c for c in cands if c >= self.last_dt - timedelta(hours=1)]
                        local = min(later) if later else cands[1]
                        flags.append("am_pm_inferred_from_sequence")
                    elif _EVENING.search(sentence) and not _MORNING.search(sentence):
                        local = local.replace(hour=h + 12)
                        flags.append("am_pm_inferred_from_context")
                    else:
                        flags.append("am_pm_unspecified")
                if token.lower() == "midnight" and self.last_dt is not None and self.last_dt.hour >= 12:
                    local += timedelta(days=1)
                elif self.last_dt is not None and self.last_dt.hour >= 18 and local.hour < 12 \
                        and local.date() == d and local < self.last_dt:
                    local += timedelta(days=1)
                if local.date() != d:
                    flags.append("date_rolled_overnight")
                if local.date() != d:
                    self.current_date = local.date()
                self.last_dt = local
                flags.append("tz_assumed")
                tv = TimeValue(local, local - before, local + after, m.group(0).strip(),
                               "approximate" if kind != "stated" or prec == "hour" else "minute", flags)
            out.append(TimeMention(tv, offset + m.start(), offset + m.end(), kind))
        return out
