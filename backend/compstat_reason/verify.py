"""Verification: nothing reaches the board unless its citations resolve to unaltered source evidence.

Checks every citation against case.db and the read-only evidence copies (SHA-256), drops items that
need citations but have none left, softens accusatory wording, and keeps protected attributes out.
"""

from __future__ import annotations

import hashlib
import re

from .store import PROTECTED_KEYS

NEEDS_CITATION = {"finding", "contradiction", "hypothesis", "insight", "connection", "episode", "claim", "source_group"}
_ACCUSATORY = [
    (re.compile(r"\b(lied|is lying|liar)\b", re.I), "gave an account that conflicts with records"),
    (re.compile(r"\b(guilty|culprit|perpetrator|thief|criminal)\b", re.I), "person of interest"),
    (re.compile(r"\bproves?\b", re.I), "supports"),
]


class Verifier:
    def __init__(self, case):
        self.case = case
        self._file_ok: dict[int, bool] = {}
        self.dropped: list[dict] = []
        self.fixed_wording = 0
        self.checked = 0

    def _file_intact(self, fid: int) -> bool:
        if fid not in self._file_ok:
            f = self.case.files[fid]
            p = self.case.run_dir / f["stored_path"]
            ok = False
            if p.exists():
                h = hashlib.sha256()
                with open(p, "rb") as fh:
                    for chunk in iter(lambda: fh.read(1 << 20), b""):
                        h.update(chunk)
                ok = h.hexdigest() == f["sha256"]
            self._file_ok[fid] = ok
        return self._file_ok[fid]

    def citation_ok(self, c: dict) -> bool:
        self.checked += 1
        rec = self.case.records.get(c.get("record_id"))
        return bool(rec) and self._file_intact(rec.file_id) and bool(rec.locator or c.get("locator"))

    def check(self, results) -> dict:
        for kind, bucket in list(results.items.items()):
            keep = []
            for it in bucket:
                before = len(it.citations)
                it.citations = [c for c in it.citations if self.citation_ok(c)]
                for field in ("supporting", "contradicting"):
                    if field in it.data:
                        it.data[field] = [s for s in it.data[field]
                                          if s.get("record_id") is None or s["record_id"] in self.case.records]
                if kind in NEEDS_CITATION and not it.citations:
                    self.dropped.append({"kind": kind, "key": it.key, "title": it.title,
                                         "reason": "no resolvable citation" if before else "no citation"})
                    continue
                if kind in ("gap", "insight", "contradiction", "hypothesis"):
                    it.title, it.text = self._soften(it.title), self._soften(it.text)
                self._strip_protected(it.data)
                keep.append(it)
            results.items[kind] = keep
        return {"citations_checked": self.checked, "items_dropped": self.dropped, "wording_fixed": self.fixed_wording,
                "files_verified": sum(self._file_ok.values()), "files_failed": [self.case.files[f]["original_path"]
                                                                               for f, ok in self._file_ok.items() if not ok]}

    def _soften(self, text: str) -> str:
        for pat, repl in _ACCUSATORY:
            text, n = pat.subn(repl, text)
            self.fixed_wording += n
        return text

    def _strip_protected(self, obj) -> None:
        if isinstance(obj, dict):
            for k in [k for k in obj if isinstance(k, str) and PROTECTED_KEYS.search(k)]:
                del obj[k]
            for v in obj.values():
                self._strip_protected(v)
        elif isinstance(obj, list):
            for v in obj:
                self._strip_protected(v)
