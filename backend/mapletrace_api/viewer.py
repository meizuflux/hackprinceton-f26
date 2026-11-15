"""Read-only evidence viewer: renders a stored evidence copy in a viewable form and resolves a citation locator to a
concrete position in it, so the UI can scroll to and highlight the cited row or line.

Nothing here writes: files are opened for reading, `case.db` is opened read-only by the caller, and every position comes
from the record's own `locator_json` written at ingestion. Responses are windowed (`offset`/`limit`) and every line is
capped, so a large file never produces a large response.
"""

from __future__ import annotations

import bisect
import csv
import io
import json
import re
import sqlite3
from pathlib import Path
from typing import Iterable, Optional

from mapletrace_ingest.extractors.documents import _strip_line_numbers, read_document_text
from mapletrace_ingest.intake import decode_text_file
from mapletrace_reason.store import PROTECTED_KEYS, unique_labels

MAX_TEXT_BYTES = 20 * 1024 * 1024   # whole-file decode (same decoder as ingestion); larger text is streamed
MAX_JSON_BYTES = 20 * 1024 * 1024   # pretty-printing needs the parsed document
MAX_LINE_CHARS = 4000               # longer lines are cut in the response and flagged
DEFAULT_LIMIT = 1000
MAX_LIMIT = 5000

IMAGE = {"jpeg": "image/jpeg", "png": "image/png", "gif": "image/gif", "webp": "image/webp", "bmp": "image/bmp",
         "tiff": "image/tiff", "heic": "image/heic"}
VIDEO = {"mp4": "video/mp4", "mov": "video/quicktime", "3gp": "video/3gpp", "avi": "video/x-msvideo",
         "matroska": "video/x-matroska"}
AUDIO = {"wav": "audio/wav", "mp3": "audio/mpeg", "m4a": "audio/mp4", "flac": "audio/flac", "ogg": "audio/ogg",
         "amr": "audio/amr"}
PDF = {"pdf": "application/pdf"}
# media the browser may render inline from our origin; everything else is always served as an attachment
INLINE_TYPES = {**IMAGE, **VIDEO, **AUDIO, **PDF}
TEXT_FORMATS = {"text", "ics", "eml", "mbox", "xml", "gpx", "kml", "html", "fasta", "vcf", "json", "jsonl", "csv"}


class ViewError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


# --------------------------------------------------------------------------- files
def stored_file(ingest_dir: Path, stored_path: str) -> Path:
    """The read-only working copy, refusing anything that resolves outside the run's evidence folder."""
    root = (ingest_dir / "evidence").resolve()
    p = (ingest_dir / stored_path).resolve()
    if p != root and root not in p.parents:
        raise ViewError(403, "outside_evidence", "the stored path is outside the evidence folder")
    if not p.is_file():
        raise ViewError(404, "evidence_missing", "the stored evidence copy is missing")
    return p


def media_type(fmt: str) -> Optional[str]:
    return INLINE_TYPES.get(fmt)


def view_kind(fmt: str, data_format: Optional[str]) -> str:
    if fmt in IMAGE:
        return "image"
    if fmt in VIDEO:
        return "video"
    if fmt in AUDIO:
        return "audio"
    if fmt in PDF:
        return "pdf"
    if fmt == "docx":
        return "document"
    if data_format == "csv":
        return "table"
    if data_format == "json" or fmt == "json":
        return "json"
    if fmt in TEXT_FORMATS or data_format == "jsonl":
        return "text"
    return "binary"


# --------------------------------------------------------------------------- locator -> records
def _attrs(raw: Optional[str]) -> dict:
    return {k: v for k, v in json.loads(raw or "{}").items() if not PROTECTED_KEYS.search(k)}


def resolve_records(con: sqlite3.Connection, file_id: int, locator: str) -> list[dict]:
    """Records of one file whose citation label (`mapletrace_reason.store.unique_labels`) equals `locator`.
    Several records can share a positional label (two sentences on one line); all of them are returned."""
    rows = con.execute("SELECT record_id, locator_json, attributes_json, content FROM records WHERE file_id = ? "
                       "ORDER BY record_id", (file_id,)).fetchall()
    locs = {r[0]: json.loads(r[1] or "{}") for r in rows}
    content = {r[0]: r[3] or "" for r in rows}
    labels = unique_labels((r[0], file_id, locs[r[0]], _attrs(r[2])) for r in rows)
    return [{"recordId": rid, "locator": locs[rid], "content": content[rid]}
            for rid, label in labels.items() if label == locator]


def split_by_excerpt(recs: list[dict], excerpt: Optional[str]) -> tuple[list[dict], list[dict]]:
    """When several records share one label, the board's source excerpt (`content[:1200]`, see
    `mapletrace_reason.board`) picks the record it actually cites; the others are returned separately."""
    if len(recs) < 2 or not excerpt:
        return recs, []
    primary = [r for r in recs if r["content"][:1200] == excerpt]
    if not primary:
        return recs, []
    return primary, [r for r in recs if r not in primary]


def positional_locator(locator: str) -> Optional[dict]:
    """A label that is itself a position (`row=71`, `line=14`, `page=2`) when no record carries it."""
    out = {}
    for part in re.split(r"[\s,]+", locator.strip()):
        m = re.fullmatch(r"(row|line|page|paragraph)=(\d{1,9})", part)
        if not m:
            return None
        out[m.group(1)] = int(m.group(2))
    return out or None


# --------------------------------------------------------------------------- helpers
def _cap(s: str) -> tuple[str, bool]:
    return (s[:MAX_LINE_CHARS], True) if len(s) > MAX_LINE_CHARS else (s, False)


def _split_lines(text: str) -> list[str]:
    """Split on \\n only, exactly as ingestion counts lines (`documents.Locator`)."""
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return [l[:-1] if l.endswith("\r") else l for l in lines]


def _window(total: int, anchor: Optional[int], offset: Optional[int], limit: int) -> int:
    if offset is not None:
        return max(0, min(offset, max(total - 1, 0)))
    if anchor is not None:
        return max(0, min(anchor - limit // 4, max(total - limit, 0)))
    return 0


def _read_text(path: Path) -> Optional[str]:
    return decode_text_file(path)[0] if path.stat().st_size <= MAX_TEXT_BYTES else None


def _stream_lines(path: Path) -> Iterable[str]:
    with open(path, "rb") as fh:
        for raw in fh:
            yield raw.decode("utf-8", errors="replace").rstrip("\r\n")


# --------------------------------------------------------------------------- ranges
class Ranges:
    """Highlight ranges in 0-based item indices (inclusive), optionally a column span inside a single item."""

    def __init__(self):
        self.items: list[dict] = []

    def add(self, start: int, end: Optional[int] = None, col_start: Optional[int] = None,
            col_end: Optional[int] = None) -> None:
        r = {"start": start, "end": start if end is None else max(start, end)}
        if col_start is not None and col_end is not None and r["end"] == r["start"] and col_end > col_start:
            r.update(colStart=col_start, colEnd=col_end)
        if r not in self.items:
            self.items.append(r)

    def anchor(self) -> Optional[int]:
        return min((r["start"] for r in self.items), default=None)


def _text_ranges(text: str, lines: list[str], locators: list[dict], ranges: Ranges, notes: list[str]) -> None:
    """Map document locators (line, char span, doc_line) onto the displayed lines of the original text."""
    stripped = _strip_line_numbers(text)
    body = stripped[0] if stripped else text
    starts = [0] + [m.end() for m in re.finditer(r"\n", body)]
    prefix = []
    if stripped:  # transcripts: the document's own "[0009] " numbers were stripped before offsets were taken
        for l in lines:
            m = re.match(r"^\[(\d{1,6})\]\s?", l)
            prefix.append((m.end(), int(m.group(1))) if m else (0, None))
    for loc in locators:
        line = loc.get("line")
        cs, ce = loc.get("char_start"), loc.get("char_end")
        if line is None and cs is not None:
            line = bisect.bisect_right(starts, cs)
        if line is None and "doc_line" in loc and prefix:
            line = next((i + 1 for i, (_, n) in enumerate(prefix) if n == loc["doc_line"]), None)
        if line is None or not 1 <= line <= len(lines):
            notes.append(f"locator {json.dumps(loc)} does not point at a line of this file")
            continue
        i = line - 1
        if cs is not None and ce is not None and ce > cs:
            end_line = bisect.bisect_right(starts, max(cs, ce - 1))
            if end_line == line:
                pad = prefix[i][0] if prefix else 0
                col = cs - starts[i] + pad
                ranges.add(i, i, col, col + (ce - cs))
            else:
                ranges.add(i, min(end_line, len(lines)) - 1)
        else:
            ranges.add(i)


def _ics_ranges(lines: list[str], locators: list[dict], ranges: Ranges) -> None:
    for loc in locators:
        line = loc.get("line")
        if not line or not 1 <= line <= len(lines):
            continue
        end = next((j for j in range(line - 1, len(lines)) if lines[j].strip().upper() == "END:VEVENT"), line - 1)
        ranges.add(line - 1, end)


def _email_ranges(lines: list[str], locators: list[dict], ranges: Ranges) -> None:
    starts = [i for i, l in enumerate(lines) if l.startswith("From ")]
    for loc in locators:
        if "mbox_index" in loc and loc["mbox_index"] < len(starts):
            k = loc["mbox_index"]
            ranges.add(starts[k], (starts[k + 1] - 1) if k + 1 < len(starts) else len(lines) - 1)
        elif "message" in loc and lines:
            ranges.add(0, len(lines) - 1)


_START_TAG = re.compile(r"<!--.*?-->|<!\[CDATA\[.*?\]\]>|<[!?][^>]*>|<([A-Za-z_][\w.\-:]*)([^>]*?)(/?)>", re.S)


def _xml_ranges(text: str, locators: list[dict], ranges: Ranges) -> None:
    """`xml_element_index` counts elements in document order (ElementTree `root.iter()`), which is start-tag order."""
    wanted = {loc["xml_element_index"] for loc in locators if isinstance(loc.get("xml_element_index"), int)}
    if not wanted:
        return
    starts = [0] + [m.end() for m in re.finditer(r"\n", text)]
    n = -1
    for m in _START_TAG.finditer(text):
        if not m.group(1):
            continue
        n += 1
        if n in wanted:
            first = bisect.bisect_right(starts, m.start()) - 1
            if m.group(3):
                last = bisect.bisect_right(starts, m.end() - 1) - 1
            else:
                close = text.find(f"</{m.group(1)}", m.end())
                last = bisect.bisect_right(starts, close) - 1 if close >= 0 else first
            ranges.add(first, last)
        if n >= max(wanted):
            break


def _jsonl_ranges(lines: list[str], locators: list[dict], ranges: Ranges) -> None:
    """`row` in a JSONL locator is the index among non-empty lines that parse as JSON objects (`load_table`)."""
    wanted = {loc["row"] for loc in locators if isinstance(loc.get("row"), int)}
    if not wanted:
        return
    idx = -1
    for i, line in enumerate(lines):
        s = line.strip()
        if not s:
            continue
        try:
            obj = json.loads(s)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            idx += 1
            if idx in wanted:
                ranges.add(i)


# --------------------------------------------------------------------------- JSON pretty-printing with paths
_PATH_PART = re.compile(r"\.?([^.\[\]]+)|\[(\d+)\]")


def _parse_path(path: str) -> Optional[tuple]:
    out, pos = [], 0
    for m in _PATH_PART.finditer(path):
        if m.start() != pos:
            return None
        out.append(int(m.group(2)) if m.group(2) is not None else m.group(1))
        pos = m.end()
    return tuple(out) if pos == len(path) and out else None


def _record_list_paths(data, path: tuple) -> list[tuple]:
    """Paths of the records ingestion read from a JSON document, in order: the same choice as
    `mapletrace_ingest.classify._largest_record_list`, so `row=N` maps to the Nth of them."""
    if isinstance(data, list):
        return [path + (i,) for i, r in enumerate(data) if isinstance(r, dict)]
    best: list[tuple] = []
    if isinstance(data, dict):
        for k, v in data.items():
            cand = _record_list_paths(v, path + (k,)) if isinstance(v, (dict, list)) else []
            if len(cand) > len(best):
                best = cand
        if not best:
            best = [path]
    return best


def pretty_json(data) -> tuple[list[str], dict]:
    """Indent-2 rendering of a JSON document, plus each container's (first line, last line) keyed by its path tuple."""
    lines: list[str] = []
    spans: dict = {}

    def emit(value, path: tuple, indent: int, prefix: str, suffix: str) -> None:
        pad = "  " * indent
        if isinstance(value, dict) and value:
            first = len(lines)
            lines.append(f"{pad}{prefix}{{")
            items = list(value.items())
            for j, (k, v) in enumerate(items):
                emit(v, path + (k,), indent + 1, json.dumps(k, ensure_ascii=False) + ": ", "," if j < len(items) - 1 else "")
            lines.append(f"{pad}}}{suffix}")
            spans[path] = (first, len(lines) - 1)
        elif isinstance(value, list) and value:
            first = len(lines)
            lines.append(f"{pad}{prefix}[")
            for j, v in enumerate(value):
                emit(v, path + (j,), indent + 1, "", "," if j < len(value) - 1 else "")
            lines.append(f"{pad}]{suffix}")
            spans[path] = (first, len(lines) - 1)
        else:
            spans[path] = (len(lines), len(lines))
            lines.append(f"{pad}{prefix}{json.dumps(value, ensure_ascii=False)}{suffix}")

    emit(data, (), 0, "", "")
    return lines, spans




# --------------------------------------------------------------------------- main
def build_view(con: sqlite3.Connection, ingest_dir: Path, file_row: sqlite3.Row, locator: Optional[str],
               offset: Optional[int], limit: int, excerpt: Optional[str] = None) -> dict:
    """`excerpt` is the board source's excerpt for this citation, used only to pick the cited record when several
    records share the label."""
    limit = max(1, min(limit, MAX_LIMIT))
    fid = file_row["file_id"]
    path = stored_file(ingest_dir, file_row["stored_path"])
    fmt = (file_row["sniffed_format"] or "").lower()
    schema = con.execute("SELECT data_format FROM inferred_schemas WHERE file_id = ?", (fid,)).fetchone()
    data_format = schema["data_format"] if schema else None
    kind = view_kind(fmt, data_format)
    manifest = json.loads(file_row["manifest_json"]) if file_row["manifest_json"] else {}
    listed = (manifest.get("sha256") or "").lower()
    out = {
        "evidenceId": file_row["external_id"] or f"FILE-{fid}",
        "fileId": fid,
        "path": file_row["original_path"],
        "filename": Path(file_row["original_path"].split("::")[-1]).name,
        "sha256": file_row["sha256"],
        "bytes": file_row["size_bytes"],
        "format": fmt,
        "evidenceType": file_row["evidence_type"],
        "parseStatus": file_row["parse_status"],
        "manifestMatch": (listed == file_row["sha256"]) if listed else None,
        "recordCount": con.execute("SELECT COUNT(*) FROM records WHERE file_id = ?", (fid,)).fetchone()[0],
        "kind": kind,
        "mediaType": media_type(fmt),
        "notes": [],
        "target": None,
    }
    notes: list[str] = out["notes"]

    # the citation: which records, and where they sit (from their locator_json only)
    primary: list[dict] = []
    shared: list[dict] = []
    if locator:
        recs = resolve_records(con, fid, locator)
        main, others = split_by_excerpt(recs, excerpt)
        primary, shared = [r["locator"] for r in main], [r["locator"] for r in others]
        out["target"] = {"locator": locator, "resolved": bool(recs), "recordIds": [r["recordId"] for r in main],
                         "sharedRecordIds": [r["recordId"] for r in others], "locators": primary,
                         "ranges": [], "sharedRanges": [], "page": None, "whole": False}
        if not recs:
            pos = positional_locator(locator)
            if pos and "row" in pos and kind == "text" and data_format != "jsonl" and "line" not in pos:
                pos["line"] = pos.pop("row")
            if pos:
                primary = [pos]
                notes.append(f"No record carries the label {locator!r}; it was read as a position in the file.")
            else:
                notes.append(f"No record in this file carries the citation label {locator!r}.")
        elif len(recs) > 1 and not others:
            notes.append(f"{len(recs)} records share the label {locator!r}; all of them are highlighted.")
    target = out["target"]

    if kind in ("image", "video", "audio", "pdf", "binary"):
        if kind == "binary":
            notes.append("This format has no viewer; download the read-only copy to inspect it.")
        if target is not None and primary:
            pages = [l["page"] for l in primary if isinstance(l.get("page"), int)]
            target["page"] = min(pages) if pages else None
            target["whole"] = not pages
        return out

    if kind == "table":
        mapper = _table_mapper
        return _table_view(out, path, mapper(primary), mapper(shared), offset, limit)

    items, mapper, unit = _items_and_mapper(out, path, fmt, data_format)
    return _lines_out(out, items, mapper(primary), mapper(shared), offset, limit, unit)


def _items_and_mapper(out: dict, path: Path, fmt: str, data_format: Optional[str]):
    """(items as (label, text), locators -> Ranges, unit) for every line-structured view."""
    notes = out["notes"]
    kind = out["kind"]

    if kind == "document":  # DOCX: one item per paragraph, then table rows, as ingestion reads them
        try:
            text, segments = read_document_text(path, "docx")
        except Exception as exc:  # noqa: BLE001 - an unreadable document still gets metadata and a download
            out["kind"] = "binary"
            notes.append(f"The document could not be read for preview ({type(exc).__name__}).")
            return [], lambda locs: Ranges(), "paragraph"
        parts = [s[1] for s in segments]
        offs = [s[0] for s in segments] + [len(text) + 1]
        items = [(f"¶{seg['paragraph']}" if "paragraph" in seg else f"T{seg.get('table')}.{seg.get('table_row')}",
                  text[offs[k]:offs[k + 1] - 1]) for k, seg in enumerate(parts)]

        def docx_map(locs):
            ranges = Ranges()
            for loc in locs:
                k = next((k for k, seg in enumerate(parts)
                          if ("paragraph" in loc and seg.get("paragraph") == loc["paragraph"])
                          or ("table" in loc and seg.get("table") == loc["table"]
                              and seg.get("table_row") == loc.get("table_row"))), None)
                if k is None and loc.get("char_start") is not None:
                    k = max(bisect.bisect_right(offs, loc["char_start"]) - 1, 0)
                if k is not None:
                    ranges.add(k)
            return ranges
        return items, docx_map, "paragraph"

    if kind == "json":
        if path.stat().st_size <= MAX_JSON_BYTES:
            try:
                data = json.loads(decode_text_file(path)[0])
            except json.JSONDecodeError:
                data = None
                notes.append("The file is not valid JSON; showing its lines as stored.")
            if data is not None:
                lines, spans = pretty_json(data)
                out["pretty"] = True
                notes.append("Pretty-printed for reading; line numbers refer to this rendering, not the stored bytes.")

                record_paths = _record_list_paths(data, ())

                def json_map(locs):
                    ranges = Ranges()
                    for loc in locs:
                        p = _parse_path(loc["json_path"]) if isinstance(loc.get("json_path"), str) else None
                        if p is None and isinstance(loc.get("row"), int) and 0 <= loc["row"] < len(record_paths):
                            p = record_paths[loc["row"]]  # tabular JSON: row = index into the record list
                        if p is not None and p in spans:
                            ranges.add(*spans[p])
                    return ranges
                return [(None, l) for l in lines], json_map, "line"
        else:
            notes.append("Too large to pretty-print; showing its lines as stored.")
        out["kind"] = "text"

    text = _read_text(path)
    if text is None:  # streamed: exact line positions only
        notes.append("Large file: lines are read as UTF-8 and positions inside lines are not highlighted.")
        lines = list(_stream_lines(path))

        def line_map(locs):
            ranges = Ranges()
            for loc in locs:
                if isinstance(loc.get("line"), int) and 1 <= loc["line"] <= len(lines):
                    ranges.add(loc["line"] - 1)
            return ranges
        return [(None, l) for l in lines], line_map, "line"

    lines = _split_lines(text)

    def text_map(locs):
        ranges = Ranges()
        if data_format == "jsonl" or fmt == "jsonl":
            _jsonl_ranges(lines, locs, ranges)
        elif fmt == "ics":
            _ics_ranges(lines, locs, ranges)
        elif fmt in ("eml", "mbox"):
            _email_ranges(lines, locs, ranges)
        elif fmt in ("xml", "gpx", "kml"):
            _xml_ranges(text, locs, ranges)
        else:
            _text_ranges(text, lines, locs, ranges, notes)
        return ranges
    return [(None, l) for l in lines], text_map, "line"


def _table_mapper(locs: list[dict]) -> Ranges:
    ranges = Ranges()
    for r in sorted({loc["row"] for loc in locs if isinstance(loc.get("row"), int) and loc["row"] >= 2}):
        ranges.add(r - 2)
    return ranges


def _finish_target(out: dict, ranges: Ranges, shared: Ranges) -> None:
    target = out["target"]
    if target is None:
        return
    target["ranges"] = ranges.items
    target["sharedRanges"] = [r for r in shared.items if r not in ranges.items]
    if target["resolved"] and not ranges.items:
        target["note"] = "The cited record was found, but its locator does not map to a position in this view."


def _lines_out(out: dict, items: list[tuple], ranges: Ranges, shared: Ranges, offset, limit, unit: str) -> dict:
    total = len(items)
    start = _window(total, ranges.anchor(), offset, limit)
    window = []
    for i in range(start, min(start + limit, total)):
        label, text = items[i]
        t, cut = _cap(text)
        item = {"n": i + 1, "text": t}
        if label:
            item["label"] = label
        if cut:
            item["truncated"] = True
        window.append(item)
    out["lines"] = {"unit": unit, "total": total, "offset": start, "limit": limit, "items": window}
    _finish_target(out, ranges, shared)
    return out


def _table_view(out: dict, path: Path, ranges: Ranges, shared: Ranges, offset, limit) -> dict:
    """CSV/TSV as columns and rows. `row` numbers match ingestion: the header is row 1 and the first data row is row 2,
    counted over the rows `csv.DictReader` yields (empty rows skipped) with the same sniffed dialect
    (`mapletrace_ingest.classify.load_table`). `line` is the physical line where the row starts."""
    if path.stat().st_size <= MAX_TEXT_BYTES:
        text = decode_text_file(path)[0]
        stream = io.StringIO(text)
        sample = text[:20000]
    else:  # stream large tables; only the requested window is kept
        stream = io.TextIOWrapper(open(path, "rb"), encoding="utf-8", errors="replace", newline="")
        sample = stream.read(20000)
        stream.seek(0)
        out["notes"].append("Large file: read as UTF-8.")
    anchor = ranges.anchor()
    start = offset if offset is not None else (max(0, anchor - limit // 4) if anchor is not None else 0)
    try:
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel_tab if path.suffix.lower() in {".tsv", ".tab"} else csv.excel
        reader = csv.reader(stream, dialect=dialect)
        header = next(reader, [])
        rows, total, line = [], 0, reader.line_num
        for cells in reader:
            if cells:
                if start <= total < start + limit:
                    rows.append({"row": total + 2, "line": line + 1, "cells": [_cap(c)[0] for c in cells]})
                total += 1
            line = reader.line_num
    finally:
        stream.close()
    out["table"] = {"columns": [_cap(c)[0] for c in header], "total": total, "offset": start, "limit": limit,
                    "items": rows}
    _finish_target(out, ranges, shared)
    return out
