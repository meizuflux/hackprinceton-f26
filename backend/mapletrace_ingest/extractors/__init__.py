"""Per-evidence-type extractors. Each turns one file into records with provenance."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Outcome:
    status: str               # parsed | partial | failed | unsupported
    parser: str
    notes: list[str] = field(default_factory=list)
