"""Readable card titles (presentation only): `displayLabel`, `displaySummary` and `labelOrigin` on board nodes and
`fileLabel` on sources (backend/LABELS.md).

Everything here is derived from the case's own evidence: the facility directory (a reference list of IDs with names,
floors and rooms, such as Kestrel's `doors_readers.csv`), MANIFEST.csv titles, contact names saved in a message
extraction, explicit `entity_links` and the record's own fields. Labels restate what those records say in plain words;
they add no facts, and nothing here reaches claims, gaps, insights, the investigator, chat or any model prompt. The
original `label` and `summary` are never changed (search and the LLM tools use them).
"""

from __future__ import annotations

import posixpath
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import timedelta

MAX_LABEL = 44
# attributes whose value can name a place or device listed in the directory, most specific first
_PLACE_ATTRS = ("cabinet_id", "reader_id", "camera_id", "computer", "host", "hostname", "door", "checkpoint_id",
                "place", "location", "room")
_ID_ATTRS = {"seq", "event_id", "record_id", "scan_id", "read_id", "visit_id", "entry_id", "id", "uid", "segmentId",
             "visitId", "message_id"}
_CODE = re.compile(r"^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$")          # DOOR_HELD_OPEN, IN_CABINET
_LEAD_CODE = re.compile(r"^([A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+)\b")   # USER_INPUT_ACTIVE (keyboard ...)
_RAW = re.compile(r"\b\w+=[^;=]+;")                               # "scan_id=RF-00111; reader_id=..."
_SEPARATORS = (" covering ", " facing ", " with ", " (", ", ")


@dataclass
class Place:
    """One row of a facility directory (a reference list of IDs with names), cited by its record."""
    id: str
    kind: str
    name: str
    floor: str
    room: str
    record_id: int


class Directory:
    """IDs, names, floors and rooms of doors, readers, cameras, cabinets and workstations, from reference-list files:
    every row has an `id`, a `kind` and a name. Only exact ID or exact (case-insensitive) name matches resolve."""

    def __init__(self, case):
        per_file: dict[int, list] = defaultdict(list)
        total = Counter(r.file_id for r in case.records.values())
        for r in case.records.values():
            a = r.attrs
            if r.duplicate_of is None and isinstance(a.get("id"), str) and a.get("kind") and r.actor:
                per_file[r.file_id].append(r)
        self.by_id: dict[str, Place] = {}
        self.by_name: dict[str, Place] = {}
        for fid, rows in per_file.items():
            if len(rows) < 3 or len(rows) < total[fid] / 2:
                continue  # not a reference list
            for r in sorted(rows, key=lambda r: r.id):
                p = Place(r.attrs["id"], str(r.attrs["kind"]), r.actor, str(r.attrs.get("floor") or ""),
                          str(r.attrs.get("room") or ""), r.id)
                self.by_id.setdefault(p.id, p)
                self.by_name.setdefault(p.name.casefold(), p)

    def __bool__(self) -> bool:
        return bool(self.by_id)

    def find(self, value) -> Place | None:
        if not isinstance(value, str) or not value:
            return None
        return self.by_id.get(value) or self.by_name.get(value.casefold())

    def for_record(self, rec) -> Place | None:
        for k in _PLACE_ATTRS:
            p = self.find(rec.attrs.get(k))
            if p:
                return p
        return self.find(rec.actor)

    def in_room(self, room: str) -> list[Place]:
        return [p for p in self.by_id.values() if room and p.room.casefold() == room.casefold()]

    def rooms(self) -> list[str]:
        return sorted({p.room for p in self.by_id.values() if p.room}, key=lambda s: (-len(s), s))


# ---------------------------------------------------------------- text helpers
def fit(text: str, limit: int = MAX_LABEL) -> str:
    """`text` cut at a word boundary to `limit` characters (an ellipsis marks the cut)."""
    text = " ".join(str(text).split())
    if len(text) <= limit:
        return text
    cut = text[:limit - 1].rsplit(" ", 1)[0].rstrip(" ,;:·-(")
    return (cut or text[:limit - 1]) + "…"


def short_name(name: str, limit: int = 30) -> str:
    """A directory name shortened at its first qualifier ("Garage P2 camera covering ..." -> "Garage P2 camera")."""
    if len(name) <= limit:
        return name
    cut = min((i for i in (name.find(s) for s in _SEPARATORS) if i > 0), default=-1)
    return name[:cut] if cut > 0 else fit(name, limit)


def humanize_code(value) -> str:
    """DOOR_HELD_OPEN -> "Door held open"; "USER_INPUT_ACTIVE (x)" -> "User input active (x)"; other text unchanged."""
    s = str(value).strip()
    if _CODE.match(s):
        return s.replace("_", " ").capitalize()
    m = _LEAD_CODE.match(s)
    if m:
        return m.group(1).replace("_", " ").capitalize() + s[m.end():]
    return s


def _value(v) -> str:
    s = str(v).strip()
    return s.replace("_", " ").lower() if _CODE.match(s) else s


def _first_clause(s: str) -> str:
    s = s.strip()
    for sep in (". ", " ("):
        i = s.find(sep)
        if i > 0:
            s = s[:i]
    return s.rstrip(".")


def person_name(name: str) -> str:
    """Readable form of an all-caps name: "CHEN, ANDREW" -> "Andrew Chen", "DELGADO, RAY (AEGIS)" -> "Ray Delgado
    (Aegis)". Mixed-case names are returned unchanged."""
    if not name or name != name.upper() or not re.search(r"[A-Z]", name):
        return name
    m = re.match(r"^\s*([^,()]+?)\s*,\s*([^,()]+?)\s*(\(.*\))?\s*$", name)
    base = f"{m.group(2)} {m.group(1)}" if m else re.sub(r"\(.*\)", "", name)
    tail = (m.group(3) if m else (re.search(r"\(.*\)", name) or [""])[0]) or ""
    out = " ".join(w.capitalize() if w.isalpha() else w.title() for w in base.split())
    return f"{out} {tail.title()}".strip() if tail else out


def phone_number(value: str) -> str:
    """+14085550147 -> +1 408-555-0147 (North American numbers only); anything else unchanged."""
    m = re.fullmatch(r"\+1(\d{3})(\d{3})(\d{4})", value or "")
    return f"+1 {m.group(1)}-{m.group(2)}-{m.group(3)}" if m else value


def file_label(f: dict) -> str:
    """A human name for an evidence file: its MANIFEST.csv title, else its type and file name."""
    title = (f.get("manifest") or {}).get("title")
    if title:
        return str(title)
    base = posixpath.basename(f.get("original_path") or "")
    kind = (f.get("evidence_type") or "evidence").replace("_", " ")
    return f"{kind.capitalize()} file {base}" if base else kind.capitalize()


# ---------------------------------------------------------------- labelling
class Labeller:
    def __init__(self, case, R, tz):
        self.case, self.R, self.tz = case, R, tz
        self.dir = Directory(case)
        self.items = {it.key: it for b in R.items.values() for it in b}
        self.links = defaultdict(list)
        for link in case.links:
            self.links[link["entity_a"]].append(link)

    # places --------------------------------------------------------
    def place_text(self, value: str, limit: int = MAX_LABEL) -> str | None:
        """Readable name of a directory ID ("SC-EBC-01" -> "Secure demo cabinet · EBC 4-12")."""
        p = self.dir.by_id.get(value)
        if not p:
            return None
        name = short_name(p.name)
        if p.room and p.room.casefold() not in name.casefold() and len(name) + 3 + len(p.room) <= limit:
            return f"{name} · {p.room}"
        return fit(name, limit)

    def where(self, rec) -> tuple[str | None, str | None]:
        """(short, long) readable place of a record, from the directory, else its raw place when that is a name."""
        p = self.dir.for_record(rec)
        if p:
            name = short_name(p.name, 40)
            long = name + (f" ({p.room})" if p.room and p.room.casefold() not in name.casefold() else "")
            return short_name(p.name), long
        pl = rec.place
        if pl and not _CODE.match(pl) and pl.upper() != pl:
            return pl, pl
        return None, None

    def substitute_ids(self, text: str) -> str:
        """Directory IDs in free text gain their name: "SC-EBC-01" -> "Secure demo cabinet (SC-EBC-01)"."""
        for pid in sorted(self.dir.by_id, key=len, reverse=True):
            p = self.dir.by_id[pid]
            text = re.sub(rf"(?<![\w-]){re.escape(pid)}(?![\w-])", f"{short_name(p.name)} ({pid})", text)
        return text

    def readable_text(self, text: str) -> str:
        """Free text with directory IDs named and event codes in words ("ACCESS_GRANTED @ X" -> "access granted at X")."""
        text = re.sub(r"(?<![\w-])[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+(?![\w-])",
                      lambda m: m.group(0).replace("_", " ").lower(), self.substitute_ids(text))
        return text.replace(" @ ", " at ")

    # records -------------------------------------------------------
    def record_phrase(self, rec) -> tuple[str, str, set[str]] | None:
        """(short phrase, full phrase, attribute keys used) describing what the record says happened."""
        a = rec.attrs
        ev = a.get("event") or a.get("event_type")
        if ev:
            full = humanize_code(ev)
            return _first_clause(full), full, {"event", "event_type"}
        if a.get("tag_id"):
            state = a.get("custody_state") or a.get("status")
            phrase = f"Tag {a['tag_id']}" + (f" {_value(state)}" if state else "")
            return phrase, phrase, {"tag_id", "custody_state", "status"}
        if a.get("checkpoint_id"):
            note = a.get("officer_note") or a.get("note")
            phrase = "Checkpoint scan" + (f": {note}" if note else "")
            return phrase, f"Checkpoint {a['checkpoint_id']} scanned" + (f" (note: {note})" if note else ""), \
                {"checkpoint_id", "officer_note", "note"}
        return None

    def record_label(self, rec) -> str | None:
        ph = self.record_phrase(rec)
        if not ph:
            return None
        what, short = ph[0], self.where(rec)[0]
        p = self.dir.for_record(rec)
        for where in (short, p.room if p else None):
            if where and len(what) + 3 + len(where) <= MAX_LABEL:
                return f"{what} · {where}"
        return fit(what)

    def record_sentence(self, rec, who: str = "") -> str | None:
        ph = self.record_phrase(rec)
        if not ph:
            return None
        _, full, used = ph
        long = self.where(rec)[1]
        p = self.dir.for_record(rec)
        used |= set(_PLACE_ATTRS) | _ID_ATTRS
        details = [f"{k.replace('_', ' ')} {_value(v)}" for k, v in rec.attrs.items()
                   if k not in used and v not in (None, "") and not isinstance(v, (dict, list))
                   and not (p and v in (p.id, p.name))]
        if ". " in full or full.endswith("."):
            full = f"“{full}”"  # a logged message, quoted as written
        s = (f"{who}: " if who else "") + full + (f" at {long}" if long else "")
        if self.tz and rec.ts:
            s += f", {rec.ts.astimezone(self.tz):%a %d %b %H:%M:%S}"
        if details:
            s += f" ({'; '.join(details[:5])})"
        return s.rstrip(".") + "."

    # entities ------------------------------------------------------
    def contact_name(self, eid: int) -> tuple[str, int] | None:
        """The one name a message extraction saved for this number (`party_name` on messages it sent)."""
        value = self.case.entities[eid]["value_norm"]
        names = Counter()
        files = Counter()
        for r in self.case.records.values():
            if r.actor == value and isinstance(r.attrs.get("party_name"), str) and r.attrs["party_name"].strip():
                names[r.attrs["party_name"].strip()] += 1
                files[r.file_id] += 1
        if len(names) != 1:
            return None
        return next(iter(names)), files.most_common(1)[0][0]

    def sender_service(self, value: str) -> str | None:
        services = {str(r.attrs.get("service")) for r in self.case.records.values()
                    if r.actor == value and r.attrs.get("service")}
        return services.pop() if len(services) == 1 else None

    # nodes ---------------------------------------------------------
    def label_node(self, n: dict) -> dict:
        nid = n["id"]
        out: dict[str, str] = {}
        if n.get("media"):
            return out  # media cards: see label_media
        if nid.startswith("loc-"):
            t = self.place_text(n["label"])
            if t:
                out["displayLabel"] = t
        elif nid.startswith(("ent-", "cam-")):
            out.update(self._entity(n))
        elif nid.startswith(("ev-", "rec-")):
            out.update(self._event(n))
        return out

    def _entity(self, n: dict) -> dict:
        nid, label = n["id"], n["label"]
        p = self.dir.by_id.get(label)
        if p:
            return {"displayLabel": self.place_text(label)}
        if not nid.startswith("ent-"):
            return {}
        eid = int(nid[4:])
        etype = self.case.etype(eid)
        if etype == "person":
            readable = person_name(label)
            full = self._linked_name(eid)
            if full and full["name"].casefold() != readable.casefold():
                lbl = f"{readable} (likely {full['name']})"
                if len(lbl) <= MAX_LABEL:
                    return {"displayLabel": lbl,
                            "displaySummary": f"Named “{label}” in the records. The identity link "
                                              f"`{full['rule']}` (confidence {full['confidence']:g}) joins this name to "
                                              f"{full['name']}; the two are not merged."}
            return {"displayLabel": readable}
        if etype == "phone":
            num = phone_number(label)
            c = self.contact_name(eid)
            if c:
                name, fid = c
                lbl = f"Phone · {name}"
                summary = f"{num} is saved as “{name}” in {file_label(self.case.files[fid])}."
                if n.get("summary"):
                    summary += " " + n["summary"].replace(label, num)
                return {"displayLabel": lbl if len(lbl) <= MAX_LABEL else fit(lbl), "displaySummary": summary}
            return {"displayLabel": num}
        if etype == "account":
            svc = self.sender_service(label)
            return {"displayLabel": fit(f"{svc} sender · {label}")} if svc else {}
        return {}

    def _linked_name(self, eid: int) -> dict | None:
        rows = [link for link in self.links.get(eid, []) if self.case.etype(link["entity_b"]) == "person"]
        if len({link["entity_b"] for link in rows}) != 1:
            return None
        link = rows[0]
        target = self.case.entities[link["entity_b"]]["canonical_id"] or link["entity_b"]
        return {"name": person_name(self.case.name(target)), "rule": link["rule"], "confidence": link["confidence"]}

    def _event(self, n: dict) -> dict:
        nid = n["id"]
        it = self.items.get(n.get("key") or "")
        if nid.startswith("rec-"):
            rec = self.case.records.get(int(nid[4:]))
            if not rec:
                return {}
            return {"displayLabel": self.record_label(rec), "displaySummary": self.record_sentence(rec)}
        if it is None:
            return {}
        if it.kind == "episode":
            places = it.data.get("places") or []
            when = it.data.get("key_time")
            out = {}
            if when and self.tz:
                from .store import parse_ts
                t = f"{parse_ts(when).astimezone(self.tz):%a %d %b %H:%M}"
                where = (self.place_text(places[0], MAX_LABEL - len(t) - 4) or places[0]) if places else None
                where = short_name(where.split(" · ")[0]) if where and len(t) + 4 + len(where) > MAX_LABEL else where
                out["displayLabel"] = f"{t} at {where}" if where and len(t) + 4 + len(where) <= MAX_LABEL else t
            text = self.readable_text(it.text)
            if text != it.text:
                out["displaySummary"] = text
            return out
        if it.kind == "finding":
            m = re.match(r"^(.*) recorded in two places at once$", it.title)
            if m:
                return {"displayLabel": fit(f"{person_name(m.group(1))}: two places at once"),
                        "displaySummary": self.readable_text(it.text)}
            rids = it.data.get("record_ids") or []
            if it.title.startswith("Unusual event") and rids:
                rec = self.case.records[rids[0]]
                lbl = self.record_label(rec)
                if not lbl:
                    return {}
                summary = n.get("summary") or ""
                why = self.substitute_ids(summary[summary.find("Flagged because"):]) if "Flagged because" in summary else ""
                who = summary.split(": ", 1)[0] if ": " in summary else ""
                if who in ("", "unattributed") or self.dir.find(who) or re.search(r"\d", who):
                    who = ""  # no person: the place (a camera, a reader) already says where it was recorded
                who = person_name(who)
                sentence = self.record_sentence(rec, who)
                return {"displayLabel": lbl, "displaySummary": f"{sentence} {why}".strip() if sentence else ""}
        return {}

    # media ---------------------------------------------------------
    def label_media(self, n: dict, camera_id: str | None) -> dict:
        m = n["media"]
        f = next((f for f in self.case.files.values() if (f["external_id"] or f"FILE-{f['file_id']}") == m["evidenceId"]),
                 None)
        if m["kind"] == "video" and camera_id:
            p = self.dir.by_id.get(camera_id)
            cam = short_name(p.name) if p else camera_id
            if m.get("capturedUtc") and self.tz:
                from .store import parse_ts
                t0 = parse_ts(m["capturedUtc"]).astimezone(self.tz)
                t1 = t0 + timedelta(seconds=float(m.get("durationS") or 0))
                lbl = f"{cam} · {t0:%H:%M}–{t1:%H:%M}"
                if len(lbl) <= MAX_LABEL:
                    return {"displayLabel": lbl}
            return {"displayLabel": fit(cam)}
        title = (f or {}).get("manifest", {}).get("title") if f else None
        if not title:
            return {}
        paren = re.match(r"^(.*?)\s*\(([^()]+)\)\s*$", title)
        if paren and " from " in paren.group(1):
            src = paren.group(1).split(" from ", 1)[1]
            lbl = f"{paren.group(2)[:1].upper()}{paren.group(2)[1:]} · {src}"
        elif ": " in title:
            rest = title.split(": ", 1)[1]
            lbl = rest[:1].upper() + rest[1:]
        else:
            lbl = title
        return {"displayLabel": fit(lbl)}


def apply(case, R, nodes: dict, tz) -> None:
    """Set `displayLabel` / `displaySummary` (and `labelOrigin: "rules"`) on board nodes in place."""
    from .media import camera_of_clip
    lab = Labeller(case, R, tz)
    cameras = camera_of_clip(case)
    for n in nodes.values():
        if n.get("media"):
            path = next((f["original_path"] for f in case.files.values()
                         if (f["external_id"] or f"FILE-{f['file_id']}") == n["media"]["evidenceId"]), "")
            out = lab.label_media(n, cameras.get(posixpath.basename(path)))
        else:
            out = lab.label_node(n)
        out = {k: v for k, v in out.items() if v}
        if out.get("displaySummary"):
            out["displaySummary"] = fit(out["displaySummary"], 400)
        if out.get("displayLabel") == n["label"]:
            out.pop("displayLabel")
        if out.get("displaySummary") == n.get("summary"):
            out.pop("displaySummary")
        if out:
            n.update(out)
            n["labelOrigin"] = "rules"


def needs_label(n: dict) -> bool:
    """A card whose title is still hard to read after the rules (candidates for the optional LLM labels)."""
    if n.get("displayLabel") or n.get("displaySummary") or n.get("media"):
        return False
    label = n.get("label") or ""
    return len(label) > MAX_LABEL or bool(_RAW.search(label)) or bool(_CODE.match(label.split(" @ ")[0].strip()))
