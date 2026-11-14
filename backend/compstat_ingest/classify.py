"""Evidence-type inference.

Decides what a file *is* (messages, location history, witness statement, DNA
profile, ...) from its content structure, with the file name only as a tie-
breaker. Every decision carries a score table and a plain-language reason so
investigators can see why a file was treated the way it was.
"""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .intake import decode_text_file

MEDIA_FORMATS = {
    "photo": {"jpeg", "png", "gif", "tiff", "bmp", "webp", "heic"},
    "video": {"mp4", "mov", "avi", "matroska", "3gp"},
    "audio": {"wav", "mp3", "flac", "ogg", "amr", "m4a"},
}
TABULAR_EXT = {".csv", ".tsv", ".tab", ".psv"}

# --------------------------------------------------------------------------- #
# Column roles
# --------------------------------------------------------------------------- #


def norm_col(c: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(c).lower())


ROLE_SYNONYMS: dict[str, list[str]] = {
    "timestamp": ["timestamp", "datetime", "datetimeutc", "timestamputc", "timestampms", "timems", "epochms",
                  "unixms", "timestamplocal", "time", "date", "sentat", "sent", "createdat",
                  "starttime", "start", "timeutc", "recordedat", "capturedat", "ts", "epoch", "unixtime", "when",
                  "occurredat", "eventtime", "receivedat", "datesent", "messagedate", "calldate", "loggedat"],
    "date_only": ["date", "day", "eventdate"],
    "time_only": ["time", "clock", "eventtime"],
    "sender": ["sender", "from", "author", "sendernumber", "fromnumber", "sendername", "fromaddress", "caller",
               "callernumber", "originator", "source", "fromphone"],
    "recipient": ["recipient", "to", "receiver", "tonumber", "recipientnumber", "destination", "callee",
                  "dialed", "dialednumber", "toaddress", "tophone", "recipients"],
    "party": ["partynumber", "party", "otherparty", "counterparty", "remotenumber", "contactnumber", "remoteparty"],
    "party_name": ["partyname", "remotename", "counterpartyname"],
    "body": ["body", "message", "text", "content", "msg", "messagetext", "smsbody", "messagebody"],
    "lat": ["latitude", "lat", "gpslat", "gpslatitude", "locationlat", "latitudee7", "sitelat", "celllat", "towerlat"],
    "lon": ["longitude", "lon", "lng", "long", "gpslon", "gpslng", "gpslongitude", "locationlon", "longitudee7",
            "sitelon", "celllon", "towerlon"],
    "accuracy": ["accuracy", "accuracym", "horizontalaccuracy", "hdop", "radius", "uncertaintym"],
    "duration": ["duration", "durations", "durationsec", "durationseconds", "callduration", "length", "lengths"],
    "direction": ["direction", "calltype", "type", "status", "callstatus"],
    "device": ["device", "deviceid", "imei", "handset", "owner", "subject", "sourcedevice", "account",
               "tracker", "vehicle", "camera", "cameraid"],
    "name": ["name", "contactname", "fullname", "displayname", "contact", "cardholder", "holder", "user",
             "username", "employee", "person", "operator", "staff"],
    "phone": ["phone", "phonenumber", "number", "mobile", "cell", "tel", "telephone", "msisdn"],
    "email": ["email", "emailaddress", "mail"],
    "event": ["event", "eventtype", "activity", "action", "description", "detection", "label", "observation"],
    "location_name": ["location", "place", "address", "site", "area", "zone"],
    "sample": ["sample", "sampleid", "specimen", "specimenid", "item", "itemid", "exhibit", "samplename"],
    "locus": ["locus", "marker", "locusname", "markername"],
    "allele": ["allele", "allele1", "allele2", "allele3", "alleles", "a1", "a2"],
    "comparison": ["likelihoodratio", "lr", "rmp", "randommatchprobability", "matchprobability", "conclusion",
                   "result", "inclusion", "exclusion"],
    "reference": ["reference", "referencesample", "referenceid", "comparedto", "knownsample", "reference_sample"],
    "questioned": ["questioned", "questionedsample", "evidence", "evidencesample", "unknownsample", "crimescenesample"],
    "confidence": ["confidence", "score", "probability"],
}
STR_LOCI = {"d8s1179", "d21s11", "d7s820", "csf1po", "d3s1358", "th01", "d13s317", "d16s539", "d2s1338",
            "d19s433", "vwa", "tpox", "d18s51", "d5s818", "fga", "amelogenin", "amel", "d1s1656", "d2s441",
            "d10s1248", "d12s391", "d22s1045", "se33", "pentae", "pentad", "dys391"}

FILENAME_HINTS = {
    "messages": ["sms", "message", "chat", "whatsapp", "imessage", "text", "signal", "telegram"],
    "call_log": ["call", "calllog", "cdr"],
    "location": ["location", "gps", "gpx", "kml", "tracking", "geo", "cell_site", "cellsite"],
    "contacts": ["contact", "addressbook", "phonebook"],
    "dna": ["dna", "str", "allele", "genotype", "lab", "forensic_lab", "serology"],
    "statement": ["statement", "witness", "affidavit", "declaration", "report_by"],
    "interview": ["interview", "transcript", "interrogation", "questioning"],
    "records": ["log", "export", "events", "cctv", "access", "badge"],
}


def map_columns(columns: list[str]) -> dict[str, str]:
    """Assign each semantic role to at most one column, preferring exact synonym order."""
    normalized = {c: norm_col(c) for c in columns}
    last_segment = {c: norm_col(str(c).split(".")[-1]) for c in columns}  # flattened JSON keys
    used: set[str] = set()
    mapping: dict[str, str] = {}
    for role, syns in ROLE_SYNONYMS.items():
        if role == "allele":
            continue
        for syn in syns:
            hit = next((c for c, n in normalized.items() if n == syn and c not in used), None)
            if not hit:
                hit = next((c for c, n in last_segment.items() if "." in str(c) and n == syn and c not in used), None)
            if hit:
                mapping[role] = hit
                if role not in {"date_only", "time_only"}:
                    used.add(hit)
                break
    alleles = [c for c, n in normalized.items() if re.fullmatch(r"(allele|a)\d*s?", n)]
    if alleles:
        mapping["allele"] = "|".join(alleles)
    return mapping


# --------------------------------------------------------------------------- #
# Table loading
# --------------------------------------------------------------------------- #


def _flatten(obj: dict, prefix: str = "") -> dict:
    out = {}
    for k, v in obj.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(_flatten(v, key + "."))
        elif isinstance(v, list) and all(not isinstance(x, (dict, list)) for x in v):
            out[key] = "; ".join(str(x) for x in v)
        else:
            out[key] = v
    return out


def load_table(path: Path, fmt: str) -> tuple[list[str], list[dict], str]:
    """Return (columns, rows, data_format). Rows keep their original order (row index = provenance)."""
    text, _ = decode_text_file(path)
    if fmt == "json":
        data = json.loads(text)
        rows = _largest_record_list(data)
        rows = [_flatten(r) for r in rows]
        cols = list(dict.fromkeys(k for r in rows for k in r))
        return cols, rows, "json"
    if fmt == "jsonl":
        rows = []
        for line in text.splitlines():
            line = line.strip()
            if line:
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict):
                    rows.append(_flatten(obj))
        cols = list(dict.fromkeys(k for r in rows for k in r))
        return cols, rows, "jsonl"
    sample = text[:20000]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel_tab if path.suffix.lower() in {".tsv", ".tab"} else csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    cols = [c.strip() for c in (reader.fieldnames or []) if c is not None]
    rows = []
    for r in reader:
        rows.append({(k or "").strip(): (v.strip() if isinstance(v, str) else v) for k, v in r.items() if k is not None})
    return cols, rows, "csv"


def _largest_record_list(data) -> list[dict]:
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    best: list[dict] = []
    if isinstance(data, dict):
        for v in data.values():
            cand = _largest_record_list(v) if isinstance(v, (dict, list)) else []
            if len(cand) > len(best):
                best = cand
        if not best:
            best = [data]
    return best


def looks_tabular(path: Path, fmt: str) -> bool:
    if fmt in {"json", "jsonl"}:
        return True
    if path.suffix.lower() in TABULAR_EXT:
        return True
    if fmt != "text":
        return False
    text, _ = decode_text_file(path, 20000)
    lines = [l for l in text.splitlines()[:20] if l.strip()]
    if len(lines) < 3:
        return False
    for delim in (",", "\t", ";", "|"):
        counts = {l.count(delim) for l in lines}
        if len(counts) == 1 and next(iter(counts)) >= 2:
            return True
    return False


# --------------------------------------------------------------------------- #
# Type inference
# --------------------------------------------------------------------------- #


@dataclass
class TypeDecision:
    evidence_type: str
    confidence: float
    reason: str
    scores: dict[str, float] = field(default_factory=dict)
    column_map: dict[str, str] = field(default_factory=dict)


def _name_hints(path: Path) -> dict[str, float]:
    """Match hint words against whole name tokens ('str' must not match 'extraction')."""
    tokens = [t for t in re.split(r"[^a-z0-9]+", path.name.lower()) if t]

    def hit(w: str) -> bool:
        return any(t == w or (len(w) >= 4 and t.startswith(w)) for t in tokens)
    return {t: 1.0 for t, words in FILENAME_HINTS.items() if any(hit(w) for w in words)}


def _decide(scores: dict[str, float], reasons: dict[str, str]) -> TypeDecision:
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    best, best_score = ranked[0]
    second = ranked[1][1] if len(ranked) > 1 else 0.0
    conf = round(min(0.99, best_score / (best_score + second + 0.5)), 2) if best_score > 0 else 0.1
    return TypeDecision(best, conf, reasons.get(best, ""), {k: round(v, 2) for k, v in ranked})


def _detect_time_column(columns: list[str], rows: list[dict], cmap: dict) -> None:
    """When no column is *named* like a timestamp, pick one whose values mostly parse as times."""
    if "timestamp" in cmap:
        return
    from zoneinfo import ZoneInfo

    from .timeparse import parse_timestamp
    used = {c for v in cmap.values() for c in v.split("|")}
    best, best_rate = None, 0.0
    for c in columns:
        n = norm_col(c)
        if c in used or not any(k in n for k in ("time", "date", "ts", "epoch", "when", "at")):
            continue
        vals = [r.get(c) for r in rows[:50] if r.get(c) not in (None, "")]
        if not vals:
            continue
        rate = sum(parse_timestamp(v, ZoneInfo("UTC")) is not None for v in vals) / len(vals)
        if rate > best_rate:
            best, best_rate = c, rate
    if best and best_rate >= 0.7:
        cmap["timestamp"] = best


def classify_table(path: Path, columns: list[str], rows: list[dict]) -> TypeDecision:
    cmap = map_columns(columns)
    _detect_time_column(columns, rows, cmap)
    has = set(cmap)
    ncols = {norm_col(c) for c in columns}
    loci_cols = ncols & STR_LOCI
    hints = _name_hints(path)
    scores: dict[str, float] = {}
    reasons: dict[str, str] = {}

    def add(t, s, why):
        scores[t] = scores.get(t, 0) + s
        reasons[t] = (reasons.get(t, "") + "; " + why).strip("; ")

    if {"lat", "lon"} <= has:
        add("location", 3, f"latitude/longitude columns ({cmap['lat']}, {cmap['lon']})")
        if "timestamp" in has:
            add("location", 1, f"timestamp column ({cmap['timestamp']})")
    if "body" in has and ({"sender", "recipient"} <= has or {"party", "direction"} <= has):
        how = "sender and recipient" if {"sender", "recipient"} <= has else f"other party ({cmap['party']}) and direction"
        add("messages", 3, f"message body ({cmap['body']}) with {how} columns")
        if "timestamp" in has:
            add("messages", 1, "timestamp column")
    elif "body" in has and (has & {"sender", "recipient", "party"}):
        add("messages", 0.8, f"message body ({cmap['body']}) with one party column")  # often a system log
    if "duration" in has and (has & {"sender", "recipient", "phone", "party"}) and "body" not in has:
        add("call_log", 3, f"call duration ({cmap['duration']}) with party columns")
        if "direction" in has:
            add("call_log", 1, f"direction column ({cmap['direction']})")
    if "name" in has and (has & {"phone", "email"}) and "timestamp" not in has:
        add("contacts", 3, "name with phone/email columns and no timestamps")
    if ("locus" in has and "allele" in has) or len(loci_cols) >= 3:
        add("dna", 4, "STR locus/allele columns" if "locus" in has else f"{len(loci_cols)} STR loci as columns")
    if "comparison" in has and (has & {"sample", "reference", "questioned"}):
        add("dna", 4, f"sample comparison columns ({cmap['comparison']})")
    if "timestamp" in has or "date_only" in has:
        add("records", 1, "generic timestamped records")
    else:
        add("records", 0.5, "generic table without recognized roles")
    for t, s in hints.items():
        if t in scores:
            add(t, s, "file name hint")
    d = _decide(scores, reasons)
    d.column_map = cmap
    return d


_SPEAKER_LINE = re.compile(r"^\s*(?:\[?\d{1,2}:\d{2}(?::\d{2})?\]?\s*)?([A-Z][\w .'\-]{0,40}|Q|A)\s*:\s+\S", re.M)
_CHAT_LINE = re.compile(
    r"^\[?(\d{1,4}[/.\-]\d{1,2}[/.\-]\d{1,4}),?\s+(\d{1,2}:\d{2}(?::\d{2})?\s*(?:[AaPp]\.?[Mm]\.?)?)\]?\s*(?:[-–]\s*)?([^:\n]{1,60}?):\s",
    re.M,
)
_DNA_TERMS = re.compile(r"\b(allele|locus|loci|STR|DNA profile|likelihood ratio|electropherogram|genotype|"
                        r"reference sample|mixture|amelogenin|random match|excluded as a contributor|"
                        r"cannot be excluded|swab)\b", re.I)
_FIRST_PERSON = re.compile(r"\b(I|I'm|I've|I'd|my|me)\b")
_STATEMENT_TERMS = re.compile(r"\b(statement|witness|i declare|i saw|i heard|i noticed|i was|sworn|affirm|signed)\b", re.I)


def classify_text(path: Path, text: str) -> TypeDecision:
    scores: dict[str, float] = {"document": 1.0}
    reasons: dict[str, str] = {"document": "free text with no stronger structure"}
    hints = _name_hints(path)
    lines = [l for l in text.splitlines() if l.strip()]
    n = max(len(lines), 1)

    chat = len(_CHAT_LINE.findall(text))
    if chat >= 3 and chat / n > 0.3:
        scores["messages"] = 3 + min(chat / n, 1)
        reasons["messages"] = f"{chat} chat-export lines (date, time, sender: message)"

    speakers = [s.strip().lower() for s in _SPEAKER_LINE.findall(text)]
    distinct = set(speakers)
    repeat_speakers = sum(1 for s in distinct if speakers.count(s) >= 2)
    # a dialogue has speakers who talk more than once; a form ("Reported by: ...") does not
    if len(speakers) >= 4 and repeat_speakers >= 2 and len(speakers) / max(len(distinct), 1) >= 1.5:
        scores["interview"] = 2 + min(len(speakers) / n, 1) * 2
        reasons["interview"] = f"{len(speakers)} speaker turns by {len(distinct)} speakers"

    dna_hits = len(_DNA_TERMS.findall(text))
    if dna_hits >= 3:
        scores["dna"] = 2 + min(dna_hits / 10, 2)
        reasons["dna"] = f"{dna_hits} DNA/lab terms (allele, locus, likelihood ratio, ...)"

    fp = len(_FIRST_PERSON.findall(text))
    st = len(_STATEMENT_TERMS.findall(text))
    words = max(len(text.split()), 1)
    if fp / words > 0.02 or st >= 2:
        scores["statement"] = 1.5 + min(fp / words * 20, 1.5) + min(st * 0.5, 1)
        reasons["statement"] = f"first-person narrative ({fp} first-person words) with {st} statement cues"

    for t, s in hints.items():
        if t in scores:
            scores[t] += s * 1.5
            reasons[t] += "; file name hint"
        elif t in {"statement", "interview", "dna"}:
            scores[t] = 1.6
            reasons[t] = "file name hint only"
    return _decide(scores, reasons)


def classify_file(path: Path, fmt: str) -> tuple[TypeDecision, dict]:
    """Return a decision and any pre-loaded payload (e.g. parsed table) for the extractor."""
    for kind, fmts in MEDIA_FORMATS.items():
        if fmt in fmts:
            return TypeDecision(kind, 0.99, f"{fmt} file signature"), {}
    if fmt in {"eml", "mbox"}:
        return TypeDecision("email", 0.97, f"{fmt.upper()} message headers"), {}
    if fmt in {"gpx", "kml"}:
        return TypeDecision("location", 0.98, f"{fmt.upper()} geodata"), {}
    if fmt == "ics":
        return TypeDecision("calendar", 0.98, "iCalendar (VCALENDAR) export"), {}
    if path.name.lower() in {"manifest.csv", "evidence_manifest.csv"}:
        cols, rows, _ = load_table(path, "csv")
        if {"path", "sha256"} <= {norm_col(c) for c in cols}:
            return TypeDecision("case_manifest", 0.99, "evidence manifest (paths + SHA-256)"), {"columns": cols, "rows": rows}
    if fmt == "json":
        try:
            data = json.loads(decode_text_file(path)[0])
        except ValueError:
            data = None
        if isinstance(data, dict) and isinstance(data.get("timelineObjects"), list):
            return TypeDecision("location", 0.97, "Google semantic location history (timelineObjects)"), {"takeout": data}
    if fmt in {"fasta", "vcf"}:
        return TypeDecision("dna", 0.97, f"{fmt.upper()} sequence/variant format"), {}
    if fmt == "zip":
        return TypeDecision("archive", 0.99, "zip archive (contents ingested recursively)"), {}
    if fmt in {"empty"}:
        return TypeDecision("empty", 1.0, "zero-length file"), {}
    if fmt in {"binary", "exe", "elf", "sqlite", "riff", "xlsx", "html", "xml"} and fmt not in {"html"}:
        return TypeDecision("unsupported", 0.9, f"{fmt} content is not parsed by this version (hashed and inventoried only)"), {}

    if looks_tabular(path, fmt):
        try:
            cols, rows, data_fmt = load_table(path, fmt if fmt in {"json", "jsonl"} else "csv")
        except (ValueError, csv.Error):
            cols, rows = [], []  # not really a table: fall through and read it as text
            fmt = "text"
        if cols and rows:
            d = classify_table(path, cols, rows)
            return d, {"columns": cols, "rows": rows, "data_format": data_fmt}

    if fmt in {"pdf", "docx", "text", "html", "json"}:
        from .extractors.documents import read_document_text
        try:
            text, segments = read_document_text(path, fmt)
        except Exception as exc:  # noqa: BLE001 - any parser failure is reported, not fatal
            return TypeDecision("unsupported", 0.4, f"could not read text: {exc}"), {}
        if not text.strip():
            return TypeDecision("document", 0.3, "no extractable text (possibly scanned; OCR not enabled)"), {"text": "", "segments": segments}
        d = classify_text(path, text)
        return d, {"text": text, "segments": segments}
    return TypeDecision("unsupported", 0.5, f"unrecognized format {fmt}"), {}
