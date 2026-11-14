"""Shared helpers: deterministic RNG, time handling, file output, and the label registry.

Everything the generator writes goes through `Out`, and every record it emits is
labelled through `Registry`, so the same seed always yields byte-identical files.
"""
from __future__ import annotations

import csv
import io
import json
import os
import random
import re
from datetime import datetime, timedelta, timezone

DEFAULT_SEED = "kestrel-v1"
SEED = DEFAULT_SEED  # build() sets this before generating

# Every date in this case (Jun-Oct 2026) falls inside US daylight time, so a fixed
# UTC-07:00 offset is exact and avoids depending on the OS time-zone database.
PDT = timezone(timedelta(hours=-7))
UTC = timezone.utc


def rng(name: str) -> random.Random:
    """Independent, reproducible random stream per generator module."""
    return random.Random(f"{SEED}:{name}")


def lt(s: str) -> datetime:
    """Parse a Pacific wall-clock time 'YYYY-MM-DD HH:MM[:SS]' into an aware datetime."""
    fmt = "%Y-%m-%d %H:%M:%S" if s.count(":") == 2 else "%Y-%m-%d %H:%M"
    return datetime.strptime(s, fmt).replace(tzinfo=PDT)


def iso_utc(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def iso_local(dt: datetime) -> str:
    return dt.astimezone(PDT).isoformat()


def local_str(dt: datetime, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    return dt.astimezone(PDT).strftime(fmt)


def epoch_ms(dt: datetime) -> int:
    return int(round(dt.timestamp() * 1000))


def daterange(start: datetime, end: datetime):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


class Out:
    """Writes files under a root directory with stable bytes (UTF-8, LF line endings)."""

    def __init__(self, root: str):
        self.root = os.path.abspath(root)
        self.written: list[str] = []

    def path(self, rel: str) -> str:
        p = os.path.join(self.root, *rel.split("/"))
        if os.name == "nt" and not p.startswith("\\\\?\\"):
            p = "\\\\?\\" + p  # lift the 260-character MAX_PATH limit on Windows
        return p

    def _ensure(self, rel: str) -> str:
        p = self.path(rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        if rel not in self.written:
            self.written.append(rel)
        return p

    def text(self, rel: str, s: str) -> None:
        if not s.endswith("\n"):
            s += "\n"
        with open(self._ensure(rel), "w", encoding="utf-8", newline="\n") as f:
            f.write(s)

    def raw(self, rel: str, b: bytes) -> None:
        with open(self._ensure(rel), "wb") as f:
            f.write(b)

    def csv(self, rel: str, header: list[str], rows: list[list]) -> None:
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        w.writerow(header)
        for r in rows:
            w.writerow(["" if v is None else v for v in r])
        self.text(rel, buf.getvalue())

    def json(self, rel: str, obj) -> None:
        self.text(rel, json.dumps(obj, indent=2, ensure_ascii=False))

    def jsonl(self, rel: str, rows: list[dict]) -> None:
        self.text(rel, "\n".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) for r in rows))


RELEVANCE = ("key", "supporting", "context", "red_herring", "background", "noise")


class Registry:
    """Collects record-level labels and named 'key' locators that ground-truth files cite."""

    def __init__(self):
        self.keys: dict[str, dict] = {}
        self.records: list[dict] = []

    def key(self, tag: str, evidence_id: str, locator: str, note: str = "") -> None:
        if tag in self.keys:
            raise ValueError(f"duplicate key tag {tag}")
        self.keys[tag] = {"evidence_id": evidence_id, "locator": locator, "note": note}

    def rec(self, evidence_id: str, locator: str, relevance: str, noise_type: str = "",
            tags: tuple | list = (), note: str = "") -> None:
        if relevance not in RELEVANCE:
            raise ValueError(relevance)
        self.records.append({
            "evidence_id": evidence_id,
            "locator": locator,
            "relevance": relevance,
            "noise_type": noise_type,
            "key_tags": ";".join(tags),
            "note": note,
        })

    def cite(self, *tags: str) -> list[dict]:
        out = []
        for t in tags:
            if t not in self.keys:
                raise KeyError(f"unknown key tag {t}")
            k = self.keys[t]
            out.append({"tag": t, "evidence_id": k["evidence_id"], "locator": k["locator"]})
        return out


MARK = re.compile(r"\s*\{\{([A-Z0-9_]+)\}\}")


def render_marked_text(text: str, evidence_id: str, reg: Registry, numbered: bool = False,
                       relevance_by_tag: dict | None = None) -> str:
    """Strip {{TAG}} markers from a document and register each as `line=N` in the final file.

    With numbered=True every non-blank line gets a [NNNN] prefix (interview transcripts).
    """
    lines = text.strip("\n").split("\n")
    out = []
    n_counter = 0
    for line in lines:
        tags = MARK.findall(line)
        clean = MARK.sub("", line).rstrip()
        if numbered and clean.strip():
            n_counter += 1
            clean = f"[{n_counter:04d}] {clean}"
        out.append(clean)
        lineno = len(out)
        for t in tags:
            reg.key(t, evidence_id, f"line={lineno}")
    return "\n".join(out) + "\n"
