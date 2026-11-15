"""Source independence: recognise when several records repeat the same original information.

Corroboration counts independent origins, not records. Three ways records share an origin:
  * the same data exported twice (ingestion's `duplicate_of`)
  * the same text appearing in several files (a forwarded email, a pasted message)
  * a report repeating a statement (an incident report summarising a witness)
Records from the same custodian/system also share an origin (see Case.origin_of).
"""

from __future__ import annotations

import difflib
import re
from collections import defaultdict

from .model import Item, stable_key
from .store import Case

_TEXT_TYPES = {"message", "email", "statement_claim", "interview_turn", "document_chunk", "lab_finding", "lab_note"}
_PRIMARY = {"statement_claim": 0, "interview_turn": 0, "message": 1, "email": 1, "lab_finding": 1, "lab_note": 1,
            "document_chunk": 2}


def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", t.lower())).strip()


def _shingles(t: str, n: int = 5) -> set[tuple]:
    w = t.split()
    return {tuple(w[i:i + n]) for i in range(max(len(w) - n + 1, 0))}


class Independence:
    def __init__(self, case: Case):
        self.case = case
        self.origin: dict[int, str] = {}
        self.items: list[Item] = []
        self._build()

    def _group(self, members: list[int], reason: str) -> None:
        def order(r):
            rec = self.case.records[r]
            t = rec.ts or rec.start
            return (_PRIMARY.get(rec.type, 3), t.timestamp() if t else float("inf"), r)
        members = sorted(set(members), key=order)
        root = members[0]
        key = f"group:{root}"
        for m in members:
            self.origin.setdefault(m, key)
        c = self.case
        files = sorted({c.files[c.records[m].file_id]["original_path"] for m in members})
        self.items.append(Item(
            "source_group", stable_key("sg", reason, root, len(members)),
            f"{len(members)} records repeat one original ({reason})",
            f"The same information appears in {len(files)} file(s): {', '.join(f.rsplit('/', 1)[-1] for f in files[:4])}. "
            f"It counts as one source when weighing corroboration; the earliest or primary record is the origin.",
            certainty="observed", score=0.3, citations=[c.cite(m) for m in members[:6]],
            data={"origin_record": root, "members": members, "reason": reason}))

    def _build(self) -> None:
        c = self.case
        # 1. exports of the same data
        dup = defaultdict(list)
        for r in c.records.values():
            if r.duplicate_of:
                dup[r.duplicate_of].append(r.id)
        for root, ms in dup.items():
            self._group([root, *ms], "same record exported twice")
        # 2. identical or near-identical text in different files
        texts = {r.id: _norm(r.content) for r in c.records.values() if r.type in _TEXT_TYPES and len(r.content) >= 30}
        buckets = defaultdict(list)
        for rid, t in texts.items():
            buckets[t[:24]].append(rid)
        parent = {}

        def find(x):
            while parent.get(x, x) != x:
                x = parent[x]
            return x
        for ids in buckets.values():
            if len(ids) < 2:
                continue
            for i, a in enumerate(ids):
                for b in ids[i + 1:]:
                    if c.records[a].file_id == c.records[b].file_id:
                        continue
                    if difflib.SequenceMatcher(None, texts[a], texts[b]).ratio() >= 0.9:
                        parent[find(b)] = find(a)
        groups = defaultdict(list)
        for x in parent:
            groups[find(x)].append(x)
        for root, ms in groups.items():
            self._group([root, *ms], "same text in several files")
        # 3. reports repeating statements
        stmts = [(r.id, _shingles(texts[r.id])) for r in c.records.values()
                 if r.type in ("statement_claim", "interview_turn") and r.id in texts and len(texts[r.id].split()) >= 8]
        for r in c.records.values():
            if r.type != "document_chunk" or r.id not in texts:
                continue
            sh = _shingles(texts[r.id])
            if not sh:
                continue
            for sid, ssh in stmts:
                if ssh and len(ssh & sh) / len(ssh) >= 0.6:
                    self._group([sid, r.id], "report repeats a statement")

    def origin_of(self, rid: int) -> str:
        return self.origin.get(rid) or self.case.origin_of(rid)

    def independent(self, rids) -> int:
        return len({self.origin_of(r) for r in rids})
