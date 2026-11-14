"""Claims: what people say in statements and interviews, as structured, testable assertions.

The deterministic extractor catches the common forms (whereabouts, "never been there", "haven't talked
to X in weeks"). With an LLM enabled, `llm.extract_claims` adds claims these patterns miss; both produce
the same structure and cite the exact sentence.
"""

from __future__ import annotations

import re
from datetime import datetime, time, timedelta

from .analytics import Context, case_tz
from .model import Item, stable_key
from .store import iso, parse_ts

_PLACE = r"(?P<place>home|my (?:house|place|apartment|flat)|the office|work|bed|[A-Z][\w'&.-]*(?:\s+[A-Z][\w'&.-]*){0,3})"
LOC_POS = re.compile(r"\b(?:I|we)\s+(?:was|were|stayed|remained|got|went|came|arrived|returned|drove|headed|left for)\s+"
                     r"(?:back\s+)?(?:at\s+|to\s+|in\s+)?" + _PLACE)
STAYED = re.compile(r"\b(?:I|we)\s+(?:was|were|stayed|remained)\s+(?:at\s+)?home\b.*?\b(all|the whole|the entire)\s+"
                    r"(night|evening|day|weekend|afternoon)\b|\b(all|the whole|the entire)\s+(night|evening)\b.*?\bhome\b", re.I)
DIDNT_LEAVE = re.compile(r"\b(?:I|we)\s+(?:didn't|did not|never)\s+(?:leave|go out|go back|go in)", re.I)
NEVER_PLACE = re.compile(r"\b(?:I|we)(?:'ve| have)?\s+(?:never|not)\s+(?:been|gone|went|visited)\s+(?:to|in|inside|into)\s+"
                         r"(?P<place>(?:the\s+)?[\w' -]{3,40}?)(?:[.,;]|$)", re.I)
CONTACT_DENY = re.compile(r"\b(?:I|we)\s+(?:haven't|have not|hadn't|had not|didn't|did not|never)\s+(?:talked|spoken|spoke|"
                          r"texted|called|seen|met|heard from|been in touch with|contacted|messaged)\s+(?:to|with|from)?\s*"
                          r"(?P<who>[A-Z][\w'-]+(?:\s+[A-Z][\w'-]+)?)(?:\s+(?:in|for)\s+(?P<span>weeks|months|days|years|a week|"
                          r"a month|ages|a long time|a while))?")
SHORT_NEVER = re.compile(r"^\s*(?:never|no)\b[.!]?\s*(?P<rest>.*)$", re.I)
_SPAN_DAYS = {"days": 3, "a week": 7, "weeks": 14, "a month": 30, "months": 60, "years": 365, "ages": 60,
              "a long time": 60, "a while": 14}


def _speaker_turn_ok(rec) -> bool:
    return rec.type == "statement_claim" or rec.attrs.get("speaker_role") == "interviewee"


def _match_person(case, text: str) -> int | None:
    t = text.lower().strip()
    hits = set()
    for pid in case.persons:
        toks = case.entities[pid]["value_norm"].split()
        if t == " ".join(toks) or (len(toks) >= 2 and t in (toks[0], toks[-1])):
            hits.add(pid)
    return hits.pop() if len(hits) == 1 else None


def _night_window(day: datetime, tz):
    start = datetime.combine(day.date(), time(18, 0), tzinfo=tz)
    return start, start + timedelta(hours=12)


def extract_claims(ctx: Context, episodes: list[Item]) -> list[Item]:
    case = ctx.case
    tz = case_tz(case)
    ep_days = [parse_ts(e.data["start"]).astimezone(tz) for e in episodes]
    items = []
    turns = sorted((r for r in case.records.values() if r.type in ("statement_claim", "interview_turn") and _speaker_turn_ok(r)),
                   key=lambda r: (r.file_id, r.locator.get("char_start", 0)))
    prev_question = {}
    for r in case.records.values():
        if r.type == "interview_turn" and r.attrs.get("speaker_role") == "interviewer":
            prev_question[(r.file_id, r.attrs.get("turn_index"))] = r
    for r in turns:
        speakers = [p for p, _, _ in ctx.persons_for(r)]
        if not speakers:
            continue
        spk = speakers[0]
        text = r.content
        window = (r.start, r.end) if r.start else (None, None)
        assumptions = []
        if window[0] is None and re.search(r"\b(night|evening|tonight|last night|saturday|sunday|friday|that day|all day)\b",
                                           text, re.I):
            header = r.attrs.get("interview_header") or r.attrs.get("statement_header") or {}
            incident = next((header[k] for k in ("date of incident", "incident date", "date of event") if header.get(k)), None)
            day = None
            if incident:
                from compstat_ingest.timeparse import parse_timestamp
                tv = parse_timestamp(incident, tz)
                day = tv.start.astimezone(tz) if tv and tv.start else None
            if day:
                window = _night_window(day, tz)
                assumptions.append("time window assumed to be the night of the incident date in the document header")
            elif ep_days:
                window = _night_window(ep_days[0], tz)
                assumptions.append("time window assumed to be the night of the key event; the sentence gives no date")
        interview_ts = parse_ts((r.attrs.get("interview_datetime") or {}).get("ts_utc")) if r.attrs.get("interview_datetime") else None
        found = []
        window_c = None
        m = STAYED.search(text) or (DIDNT_LEAVE.search(text) and re.search(r"\bhome\b", text, re.I))
        if m:
            found.append(("location", True, "home", None, "stayed home"))
        else:
            m = LOC_POS.search(text)
            if m and not re.search(r"\b(never|not|didn't|did not)\b", text[:m.start()], re.I):
                place = m.group("place")
                place = "home" if place.lower() in ("home", "my house", "my place", "my apartment", "my flat", "bed") else place
                found.append(("location", True, place, None, "whereabouts"))
        m = NEVER_PLACE.search(text)
        if m:
            found.append(("location", False, m.group("place").strip(), None, "never been there"))
        q = prev_question.get((r.file_id, (r.attrs.get("turn_index") or 0) - 1))
        if not m and q and SHORT_NEVER.match(text) and re.search(r"\b(been to|go to|visit|ever been)\b", q.content, re.I):
            pm = re.search(r"(?:been to|go to|visit)\s+(?:the\s+)?(?P<place>[\w' -]{3,40}?)[?.]", q.content, re.I)
            if pm:
                found.append(("location", False, pm.group("place").strip(), None, "denied in answer"))
        m = CONTACT_DENY.search(text)
        if m:
            who = _match_person(case, m.group("who"))
            days = _SPAN_DAYS.get((m.group("span") or "").lower(), 14)
            hdr = r.attrs.get("interview_header") or r.attrs.get("statement_header") or {}
            doc_date = next((hdr[k] for k in ("date", "date and time", "date of statement", "date of interview") if hdr.get(k)), None)
            if not interview_ts and doc_date:
                from compstat_ingest.timeparse import parse_timestamp
                tv = parse_timestamp(doc_date, tz)
                interview_ts = tv.end if tv else None
            end = interview_ts or r.ts or (parse_ts(case.info.get("ingested_at_utc")))
            window_c = (end - timedelta(days=days), end) if end else None
            found.append(("contact", False, None, who, f"no contact with {m.group('who')}"))
        for ctype, polarity, place, counterpart, label in found:
            w = window_c if ctype == "contact" and window_c else window
            items.append(Item(
                "claim", stable_key("claim", r.id, ctype, polarity, place, counterpart),
                f"{case.name(spk)}: {label}", text, certainty="observed", score=0.5, citations=[case.cite(r.id)],
                data={"speaker": spk, "subject": spk, "claim_type": ctype, "polarity": polarity, "place": place,
                      "counterpart": counterpart, "window": [iso(w[0]), iso(w[1])] if w and w[0] else None,
                      "record_id": r.id, "assumptions": assumptions + ([f"contact window is the {(w[1] - w[0]).days} days "
                                                                        f"before the interview"] if ctype == "contact" and w and w[0] else []),
                      "extraction": "rules", "quote": text}))
    return items
