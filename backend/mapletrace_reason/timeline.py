"""Timeline reconstruction: one ordered timeline across every evidence type, with uncertain times,
missing periods and conflicts made explicit rather than hidden."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import timedelta
from statistics import median

from .analytics import Context, case_tz
from .model import Item, stable_key
from .store import Record, iso

_FLAG_TEXT = {
    "tz_assumed": "recorded without a time zone; read as {tz} (case or manifest setting)",
    "human_reported": "a person's recollection, kept as a time window rather than a point",
    "am_pm_inferred_from_sequence": "am/pm not stated; inferred from the order of the account",
    "am_pm_inferred_from_context": "am/pm not stated; inferred from words like 'night'",
    "am_pm_unspecified": "am/pm not stated and could not be inferred",
    "day_month_ambiguous": "the date can be read two ways (e.g. 03/04)",
    "container_mtime_only": "only the archive's file date is available, not a capture time",
    "date_rolled_overnight": "the account crosses midnight; the date was moved to the next day",
    "midnight_ambiguous": "'midnight' could mean the start or end of the day",
    "date_unknown": "a time was mentioned without any date",
    "low_confidence": "the source itself marks this record as low confidence",
}


def _interval(seconds: float) -> str:
    """A typical spacing between records, in words: 'under a second', '12 s', '14 min', '2.5 h'."""
    if seconds < 1:
        return "under a second"
    if seconds < 60:
        return f"{seconds:.0f} s"
    if seconds < 90 * 60:
        return f"{seconds / 60:.0f} min"
    return f"{seconds / 3600:.1f} h"


def _reasons(r: Record, tz: str) -> list[str]:
    out = [_FLAG_TEXT[f].format(tz=tz) for f in r.flags if f in _FLAG_TEXT]
    if r.precision == "day":
        out.append("only the date is known")
    elif r.precision in ("hour", "approximate") and "human_reported" not in r.flags:
        out.append(f"time is only known to the {r.precision}")
    if r.attrs.get("low_confidence"):
        out.append(_FLAG_TEXT["low_confidence"])
    return out


def focus_windows(episodes: list[Item], pad_hours: int = 6):
    from .store import parse_ts
    return [(parse_ts(e.data["start"]) - timedelta(hours=pad_hours), parse_ts(e.data["end"]) + timedelta(hours=pad_hours), e)
            for e in episodes]


def uncertain_times(ctx: Context, episodes: list[Item]) -> list[Item]:
    case = ctx.case
    tzname = case.info.get("assumed_timezone", "UTC")
    agg = defaultdict(list)
    for r in case.records.values():
        if r.ts is None and r.type in ("statement_claim", "interview_turn"):
            continue
        for reason in _reasons(r, tzname):
            agg[(r.file_id, reason)].append(r.id)
    items = []
    for (fid, reason), rids in agg.items():
        f = case.files[fid]
        items.append(Item("uncertain_time", stable_key("unc", f["original_path"], reason),
                          f"{len(rids)} uncertain times in {f['original_path'].rsplit('/', 1)[-1]}",
                          f"{reason.capitalize()}. Affects {len(rids)} record(s); conclusions depending on exact order use "
                          f"the full window, not a single point.", certainty="observed",
                          score=round(min(1.0, len(rids) / 200), 2), citations=[case.cite(r) for r in rids[:3]],
                          data={"file": f["original_path"], "reason": reason, "count": len(rids), "record_ids": rids[:500]}))
    return sorted(items, key=lambda i: -i.data["count"])


def missing_periods(ctx: Context, episodes: list[Item]) -> list[Item]:
    """Silences inside the windows that matter: a log that normally reports often stops, or a person
    involved in a key event has no record placing them anywhere."""
    case = ctx.case
    tz = case_tz(case)
    items = []
    by_file = defaultdict(list)
    for r in case.timed:
        if r.reliability == "recorded":
            by_file[r.file_id].append(r)
    for (ws, we, ep) in focus_windows(episodes):
        for fid, rs in by_file.items():
            if len(rs) < 20:
                continue
            gaps_all = [(b.ts - a.ts).total_seconds() for a, b in zip(rs, rs[1:])]
            med = median(gaps_all)
            if not (rs[0].ts <= ws and rs[-1].ts >= we):
                continue  # only judge silences inside the span a log actually covers
            inside = [r for r in rs if ws <= r.ts <= we]
            pts = [ws] + [r.ts for r in inside] + [we]
            for a, b in zip(pts, pts[1:]):
                gap = (b - a).total_seconds()
                if gap > max(10 * med, 3600) and gap > 0:
                    f = case.files[fid]
                    neighbours = [r for r in rs if r.ts <= a][-1:] + [r for r in rs if r.ts >= b][:1]
                    items.append(Item("missing_period", stable_key("silence", f["original_path"], iso(a), iso(b)),
                                      f"{f['original_path'].rsplit('/', 1)[-1]} is silent {a.astimezone(tz):%a %H:%M}–{b.astimezone(tz):%H:%M}",
                                      f"This log's records are usually {_interval(med)} apart, but it has none for "
                                      f"{gap / 3600:.1f} h around {ep.title.lower()}. That may be normal inactivity, an outage, "
                                      f"or missing data.", certainty="observed", score=round(min(1.0, gap / 3600 / 6), 2),
                                      citations=[case.cite(r.id) for r in neighbours],
                                      data={"kind": "source_silence", "file": f["original_path"], "start": iso(a), "end": iso(b),
                                            "episode": ep.key}))
        # people involved in the key event with no whereabouts
        ws2, we2 = ws + timedelta(hours=4), we - timedelta(hours=4)
        for pid in ep.data.get("persons", []):
            if case.etype(pid) != "person":
                continue
            spans = sorted(((r.start or r.ts), max(r.end or r.ts, r.ts)) for r in case.timed
                           if (r.end or r.ts) >= ws2 and (r.start or r.ts) <= we2 and r.reliability == "recorded"
                           and any(p == pid for p, _, _ in ctx.persons_for(r)))
            holes, cursor = [], ws2
            for s0, e0 in spans:
                if s0 - cursor >= timedelta(minutes=45):
                    holes.append((cursor, s0))
                cursor = max(cursor, e0)
            if we2 - cursor >= timedelta(minutes=45):
                holes.append((cursor, we2))
            for a, b in holes:
                if True:
                    items.append(Item("missing_period", stable_key("unaccounted", case.name(pid), iso(a), iso(b)),
                                      f"No record places {case.name(pid)} {a.astimezone(tz):%a %H:%M}–{b.astimezone(tz):%H:%M}",
                                      f"Around {ep.title.lower()}, no machine record shows where {case.name(pid)} was for "
                                      f"{(b - a).total_seconds() / 60:.0f} minutes. Unknown whereabouts are not evidence of anything.",
                                      certainty="unknown", score=0.5, citations=ep.citations[:2],
                                      data={"kind": "unaccounted_person", "person": pid, "start": iso(a), "end": iso(b),
                                            "episode": ep.key}))
    return items


def timeline_entries(ctx: Context, record_ids: set[int], conflicts: dict[int, list[str]], limit: int = 400) -> list[dict]:
    case = ctx.case
    tzname = case.info.get("assumed_timezone", "UTC")
    recs = sorted((case.records[r] for r in record_ids if r in case.records and (case.records[r].ts or case.records[r].start)),
                  key=lambda r: r.ts or r.start)
    out = []
    for r in recs[:limit]:
        reasons = _reasons(r, tzname)
        out.append({"record_id": r.id, "time": iso(r.ts), "window": [iso(r.start), iso(r.end)], "precision": r.precision,
                    "uncertain": bool(reasons), "uncertainty": reasons, "type": r.type, "reliability": r.reliability,
                    "who": [case.name(p) for p, _, _ in ctx.persons_for(r)] or ([r.actor] if r.actor else []),
                    "what": r.content[:200], "where": r.place, "citation": case.cite(r.id),
                    "conflicts": conflicts.get(r.id, [])})
    return out


def source_coverage(ctx: Context) -> dict:
    case = ctx.case
    cov = {}
    for fid, f in case.files.items():
        ts = [r.ts for r in case.timed if r.file_id == fid]
        if ts:
            cov[f["original_path"]] = {"first": iso(min(ts)), "last": iso(max(ts)), "records": len(ts),
                                       "type": f["evidence_type"]}
    return cov


def type_counts(case) -> dict:
    return dict(Counter(r.type for r in case.records.values()))
