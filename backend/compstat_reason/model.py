"""Shared result types. Every item is cited, labelled observed/inferred, and has a stable key so
results can be compared across analysis versions (new evidence) and overridden by investigators."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any


PLURAL = {"hypothesis": "hypotheses", "missing_period": "missing_periods", "uncertain_time": "uncertain_times"}


def plural(kind: str) -> str:
    return PLURAL.get(kind, kind + "s")


def stable_key(*parts: Any) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()[:16]


@dataclass
class Item:
    kind: str                      # finding | claim | contradiction | hypothesis | gap | suggestion | insight | link | ...
    key: str                       # stable across runs
    title: str
    text: str
    certainty: str = "inferred"    # observed | inferred | unknown
    score: float = 0.0
    citations: list[dict] = field(default_factory=list)
    data: dict = field(default_factory=dict)
    status: str = "open"
    id: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class Results:
    """Accumulates items by kind and assigns short display IDs (F-01, G-03, ...)."""
    PREFIX = {"finding": "F", "claim": "C", "contradiction": "X", "hypothesis": "H", "gap": "G",
              "suggestion": "S", "insight": "I", "connection": "E", "source_group": "SG", "missing_period": "M",
              "uncertain_time": "U", "episode": "K"}

    def __init__(self):
        self.items: dict[str, list[Item]] = {}

    def add(self, item: Item) -> Item:
        bucket = self.items.setdefault(item.kind, [])
        existing = next((i for i in bucket if i.key == item.key), None)
        if existing:
            return existing
        item.id = f"{self.PREFIX.get(item.kind, item.kind[:2].upper())}-{len(bucket) + 1:02d}"
        bucket.append(item)
        return item

    def get(self, kind: str) -> list[Item]:
        return self.items.get(kind, [])

    def by_id(self, item_id: str) -> Item | None:
        for bucket in self.items.values():
            for i in bucket:
                if i.id == item_id:
                    return i
        return None

    def renumber(self, kind: str, sort_key) -> None:
        bucket = sorted(self.items.get(kind, []), key=sort_key)
        for n, i in enumerate(bucket, 1):
            i.id = f"{self.PREFIX.get(kind, kind[:2].upper())}-{n:02d}"
        self.items[kind] = bucket
