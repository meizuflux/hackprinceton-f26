"""Text evidence: witness statements, suspect interviews, chat exports, general documents."""

from __future__ import annotations

import bisect
import html as html_lib
import re
from pathlib import Path

from ..intake import decode_text_file
from ..timeparse import HumanTimeResolver, find_reference_date, parse_timestamp
from . import Outcome

# --------------------------------------------------------------------------- #
# Reading text with locators
# --------------------------------------------------------------------------- #


def read_document_text(path: Path, fmt: str) -> tuple[str, list[tuple[int, dict]]]:
    """Return full text and a list of (char_offset, locator) marking where each page/paragraph starts."""
    parts: list[tuple[str, dict]] = []
    if fmt == "pdf":
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        for i, page in enumerate(reader.pages):
            parts.append((page.extract_text() or "", {"page": i + 1}))
    elif fmt == "docx":
        import docx
        d = docx.Document(str(path))
        for i, para in enumerate(d.paragraphs):
            parts.append((para.text, {"paragraph": i + 1}))
        for ti, table in enumerate(d.tables):
            for ri, row in enumerate(table.rows):
                parts.append((" | ".join(c.text for c in row.cells), {"table": ti + 1, "table_row": ri + 1}))
    else:
        text, enc = decode_text_file(path)
        if fmt == "html":
            text = re.sub(r"(?is)<(script|style).*?</\1>", " ", text)
            text = re.sub(r"(?s)<br\s*/?>|</p>|</div>", "\n", text)
            text = html_lib.unescape(re.sub(r"(?s)<[^>]+>", " ", text))
            return text, [(0, {"encoding": enc})]
        numbered = _strip_line_numbers(text)
        if numbered:
            return numbered
        return text, [(0, {"encoding": enc})]
    text_parts, segments, offset = [], [], 0
    for t, loc in parts:
        segments.append((offset, loc))
        text_parts.append(t)
        offset += len(t) + 1
    return "\n".join(text_parts), segments


_LINE_NO = re.compile(r"^\[(\d{1,6})\]\s?")


def _strip_line_numbers(text: str):
    """Transcripts often carry their own line numbers ("[0009] REYES: ..."). Strip them for parsing but
    keep each one as `doc_line` in the locator, since that is how investigators cite these documents."""
    lines = text.splitlines(keepends=True)
    content = [l for l in lines if l.strip()]
    if not content or sum(bool(_LINE_NO.match(l)) for l in content) / len(content) < 0.6:
        return None
    out, segs, off = [], [], 0
    for line in lines:
        m = _LINE_NO.match(line)
        body = line[m.end():] if m else line
        segs.append((off, {"doc_line": int(m.group(1))} if m else {}))
        out.append(body)
        off += len(body)
    return "".join(out), segs


class Locator:
    def __init__(self, text: str, segments: list[tuple[int, dict]]):
        self.line_starts = [0] + [m.end() for m in re.finditer(r"\n", text)]
        self.seg_offsets = [s[0] for s in segments] or [0]
        self.segments = segments or [(0, {})]

    def at(self, start: int, end: int) -> dict:
        line = bisect.bisect_right(self.line_starts, start)
        seg = self.segments[max(bisect.bisect_right(self.seg_offsets, start) - 1, 0)][1]
        loc = {k: v for k, v in seg.items() if k != "encoding"}
        loc.update({"line": line, "char_start": start, "char_end": end})
        return loc


_SENTENCE = re.compile(r"[^.!?\n]+(?:[.!?]+[\"')\]]*|(?=\n)|$)")
_HEADER_LINE = re.compile(r"^\s*([A-Za-z][A-Za-z /]{1,30})\s*:\s*(.+?)\s*$")
_AUTHOR_KEYS = {"name", "statement of", "witness", "witness name", "declarant", "deponent", "author", "from", "interviewee", "subject"}


def parse_header(text: str) -> tuple[dict, int]:
    """Read 'Key: value' lines at the top of a document. Returns (fields, char offset where body starts)."""
    fields, offset, titles = {}, 0, 0
    for i, line in enumerate(text.splitlines(keepends=True)):
        if i > 25:
            break
        stripped = line.strip()
        if not stripped:
            offset += len(line)
            if fields:
                break
            continue
        m = _HEADER_LINE.match(stripped)
        if m and len(m.group(1).split()) <= 4:
            fields[m.group(1).strip().lower()] = m.group(2).strip()
            offset += len(line)
        elif not fields and titles < 4 and (len(stripped.split()) <= 8 or stripped.isupper()) \
                and not stripped.endswith((".", "?", "!")):
            titles += 1  # a document title such as "WITNESS STATEMENT"
            offset += len(line)
        else:
            break
    if not fields:
        return {}, 0
    return fields, offset


_INCIDENT_KEYS = ("date of incident", "incident date", "date of event", "date of offence", "date of offense")


def incident_date(ctx, fields: dict):
    for k in _INCIDENT_KEYS:
        if fields.get(k):
            tv = parse_timestamp(fields[k], ctx.tz, ctx.dayfirst)
            if tv and tv.start:
                return tv.start.astimezone(ctx.tz).date()
    return None


def _author(fields: dict) -> str | None:
    for k in _AUTHOR_KEYS:
        if fields.get(k):
            return fields[k]
    return None


def sentences(text: str, start: int = 0):
    for m in _SENTENCE.finditer(text, start):
        s = m.group(0).strip()
        if len(s.split()) >= 3:
            lead = len(m.group(0)) - len(m.group(0).lstrip())
            yield s, m.start() + lead, m.start() + lead + len(s)


# --------------------------------------------------------------------------- #
# Extractors
# --------------------------------------------------------------------------- #


def extract_statement(ctx, file_id: int, payload: dict) -> Outcome:
    text, loc = payload["text"], Locator(payload["text"], payload["segments"])
    fields, body_start = parse_header(text)
    author = _author(fields)
    ref = incident_date(ctx, fields) or find_reference_date(text, ctx.dayfirst)
    resolver = HumanTimeResolver(ctx.tz, ref, ctx.dayfirst)
    created = with_time = 0
    for sent, s, e in sentences(text, body_start):
        mentions = resolver.resolve(sent, s)
        ts = mentions[0].value if mentions else None
        attrs = {"statement_header": fields, "time_mentions": [
            {"raw": m.value.raw, "qualifier": m.qualifier, **m.value.to_dict()} for m in mentions]}
        ctx.add_record(file_id, "statement_claim", ts=ts, actor=author, content=sent, attributes=attrs,
                       locator=loc.at(s, e), reliability="asserted", entities=[(author, "author")])
        created += 1
        with_time += bool(mentions and mentions[0].value.utc)
    notes = [f"{created} claims; {with_time} placed on the timeline", f"author: {author or 'unknown'}"]
    if not author:
        notes.append("no author found in header; claims are unattributed")
    return Outcome("parsed" if created else "partial", "statement", notes)


_TURN = re.compile(r"^\s*(?:\[?(?P<clock>\d{1,2}:\d{2}(?::\d{2})?)\]?\s*)?(?P<spk>[A-Z][\w .'\-]{0,40}?|Q|A)\s*:\s+(?P<txt>.*)$")
_INTERVIEWER = re.compile(r"\b(det|detective|officer|ofc|interviewer|investigator|sgt|sergeant|agent|insp|inspector|q)\b\.?", re.I)


def extract_interview(ctx, file_id: int, payload: dict) -> Outcome:
    text, loc = payload["text"], Locator(payload["text"], payload["segments"])
    fields, body_start = parse_header(text)
    interviewer = fields.get("interviewer") or fields.get("interviewing officer") or fields.get("officer")
    subject = fields.get("interviewee") or fields.get("subject") or fields.get("suspect") or fields.get("witness")
    # Times an interviewee mentions refer to the incident, not the interview day, so only an
    # explicit incident date (or dates spoken in the transcript itself) anchors them.
    resolver = HumanTimeResolver(ctx.tz, incident_date(ctx, fields), ctx.dayfirst)
    interview_dt = parse_timestamp(fields.get("date") or fields.get("date and time") or fields.get("date of interview")
                                   or fields.get("interview date"), ctx.tz, ctx.dayfirst)

    turns: list[dict] = []
    pos = 0
    for line in text.splitlines(keepends=True):
        start = pos
        pos += len(line)
        if start < body_start:
            continue
        m = _TURN.match(line.rstrip("\r\n"))
        if m and m.group("spk").strip().lower() not in {"note", "notes", "date", "time", "case", "location", "present",
                                                        "recorded", "subject", "date and time", "end", "start"}:
            turns.append({"speaker": m.group("spk").strip(), "text": m.group("txt").strip(), "start": start,
                          "end": start + len(line.rstrip()), "clock": m.group("clock")})
        elif turns and line.strip():
            turns[-1]["text"] += " " + line.strip()
            turns[-1]["end"] = start + len(line.rstrip())

    # full names available in the header ("Present: Det. Ana Reyes, Det. Sam Okoye, Richard Halvorsen")
    def _clean_name(n: str) -> str:
        return re.sub(r"\s*\(.*?\)", "", n).strip()
    roster = [_clean_name(n) for k in ("present", "interviewer", "interviewing officer", "officer", "interviewee",
                                        "subject", "suspect", "witness", "attendees")
              for n in re.split(r",|;|\band\b", fields.get(k, "")) if _clean_name(n)]
    subject = _clean_name(subject) if subject else subject

    def full_name(label: str) -> str | None:
        last = label.split()[-1].lower().strip(".")
        hits = {n for n in roster if n.split()[-1].lower().strip(".") == last}
        return hits.pop() if len(hits) == 1 else None

    created = 0
    for i, t in enumerate(turns):
        label = t["speaker"]
        if label == "Q":
            speaker, role = interviewer or "Interviewer", "interviewer"
        elif label == "A":
            speaker, role = subject or "Interviewee", "interviewee"
        else:
            speaker = label
            full = full_name(label) or ""
            is_int = bool(_INTERVIEWER.search(label)) or bool(_INTERVIEWER.search(full)) or \
                (interviewer and label.lower() in interviewer.lower())
            role = "interviewer" if is_int else "interviewee"
        mentions = resolver.resolve(t["text"], t["start"])
        ts = next((m.value for m in mentions if m.value.utc), None)
        attrs = {"speaker_role": role, "turn_index": i, "interview_header": fields,
                 "interview_datetime": interview_dt.to_dict() if interview_dt else None,
                 "time_mentions": [{"raw": m.value.raw, "qualifier": m.qualifier, **m.value.to_dict()} for m in mentions]}
        if t["clock"]:
            attrs["transcript_clock"] = t["clock"]
        # tie short transcript labels ("Det. Ruiz") to the full names in the header ("Det. Ana Ruiz")
        full = full_name(speaker) or (interviewer if role == "interviewer" else subject)
        same_person = bool(full) and speaker != full and speaker.split()[-1].lower().strip(".") in full.lower()
        ents = [(speaker, "speaker")] + ([(full, "speaker")] if same_person else [])
        ctx.add_record(file_id, "interview_turn", ts=ts, actor=full if same_person else speaker, content=t["text"],
                       attributes={**attrs, "speaker_label": speaker}, locator=loc.at(t["start"], t["end"]),
                       reliability="asserted", entities=ents)
        created += 1
    notes = [f"{created} speaker turns", f"interviewer: {interviewer or 'from labels'}; subject: {subject or 'from labels'}"]
    return Outcome("parsed" if created else "partial", "interview", notes)


_CHAT = re.compile(
    r"^\[?(?P<date>\d{1,4}[/.\-]\d{1,2}[/.\-]\d{1,4}),?\s+(?P<time>\d{1,2}:\d{2}(?::\d{2})?\s*(?:[AaPp]\.?[Mm]\.?)?)\]?\s*(?:[-–]\s*)?(?P<who>[^:\n]{1,60}?):\s(?P<msg>.*)$"
)


def extract_chat_export(ctx, file_id: int, payload: dict) -> Outcome:
    text, loc = payload["text"], Locator(payload["text"], payload["segments"])
    msgs: list[dict] = []
    pos = 0
    for line in text.splitlines(keepends=True):
        start = pos
        pos += len(line)
        m = _CHAT.match(line.rstrip("\r\n"))
        if m:
            msgs.append({**m.groupdict(), "start": start, "end": start + len(line.rstrip())})
        elif msgs and line.strip():
            msgs[-1]["msg"] += "\n" + line.strip()
            msgs[-1]["end"] = start + len(line.rstrip())
    participants = list(dict.fromkeys(m["who"].strip() for m in msgs))
    created = 0
    for i, m in enumerate(msgs):
        who = m["who"].strip()
        target = next((p for p in participants if p != who), None) if len(participants) == 2 else None
        ts = parse_timestamp(f"{m['date']} {m['time']}", ctx.tz, ctx.dayfirst)
        attrs = {"chat_participants": participants, "message_index": i}
        if m["msg"].strip() in {"<Media omitted>", "<attached>", "image omitted", "<image omitted>"}:
            attrs["media_placeholder"] = True
        ctx.add_record(file_id, "message", ts=ts, actor=who, target=target, content=m["msg"].strip(),
                       attributes=attrs, locator=loc.at(m["start"], m["end"]), reliability="recorded",
                       entities=[(who, "sender"), (target, "recipient")])
        created += 1
    notes = [f"{created} chat messages", f"participants: {', '.join(participants)}"]
    if len(participants) > 2:
        notes.append("group chat: recipients not individually attributed")
    return Outcome("parsed" if created else "partial", "chat_export", notes)


def extract_document(ctx, file_id: int, payload: dict) -> Outcome:
    text, loc = payload["text"], Locator(payload["text"], payload["segments"])
    if not text.strip():
        return Outcome("partial", "document", ["no extractable text (scanned document? OCR is not enabled)"])
    fields, _ = parse_header(text)
    author = _author(fields)
    created = 0
    # general documents keep every line (including any header) so nothing is silently dropped
    for m in re.finditer(r"(?s)(.+?)(?:\n\s*\n|$)", text):
        chunk = m.group(1).strip()
        if not chunk:
            continue
        s = m.start(1)
        # long paragraphs are split so citations stay precise
        for j in range(0, len(chunk), 1500):
            piece = chunk[j:j + 1500]
            dates = [parse_timestamp(d, ctx.tz, ctx.dayfirst) for d in re.findall(r"\b\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2})?)?\b", piece)]
            ts = next((d for d in dates if d), None)
            ctx.add_record(file_id, "document_chunk", ts=ts, actor=author, content=piece,
                           attributes={"document_header": fields} if fields else {},
                           locator=loc.at(s + j, s + j + len(piece)), reliability="recorded",
                           entities=[(author, "author")])
            created += 1
    return Outcome("parsed", "document", [f"{created} text chunks"])
