"""Updates and investigator overrides.

* Versions: each analysis run is a numbered version. When new evidence arrives, the case is re-ingested
  and re-analysed with `previous=`; every gap, explanation, contradiction and insight is matched by its
  stable key, and the change log records what changed and why. Gaps are marked resolved, partially
  resolved or still open.
* Overrides: investigator corrections live in `overrides.jsonl` next to the case. They are applied on
  every run, never deleted, and the original machine result is kept alongside the override.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .model import plural

ACTIONS = {"dismiss", "confirm", "set_status", "set_label", "note", "reject_link"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


# --------------------------------------------------------------------------- overrides
def load_overrides(path: Path | None) -> list[dict]:
    if not path or not Path(path).exists():
        return []
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def append_override(path: Path, target_key: str, action: str, value=None, note: str = "", investigator: str = "investigator") -> dict:
    if action not in ACTIONS:
        raise ValueError(f"action must be one of {sorted(ACTIONS)}")
    entry = {"id": str(uuid.uuid4()), "time": now(), "investigator": investigator, "target_key": target_key,
             "action": action, "value": value, "note": note}
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")
    return entry


def apply_overrides(results, overrides: list[dict]) -> list[dict]:
    """Annotate items; never remove them. Returns the overrides that matched an item."""
    by_key = {it.key: it for bucket in results.items.values() for it in bucket}
    applied = []
    for o in overrides:
        it = by_key.get(o["target_key"])
        if not it:
            o = {**o, "matched": False}
            applied.append(o)
            continue
        it.data.setdefault("overrides", []).append(o)
        it.data.setdefault("machine_status", it.status)
        if o["action"] == "dismiss":
            it.status = "dismissed"
        elif o["action"] == "confirm":
            it.status = "confirmed"
        elif o["action"] == "set_status" and o.get("value"):
            it.status = str(o["value"])
        elif o["action"] == "set_label" and o.get("value"):
            it.data.setdefault("machine_label", it.data.get("label"))
            it.data["label"] = str(o["value"])
        elif o["action"] == "reject_link":
            it.status = "rejected"
        applied.append({**o, "matched": True, "item": it.title})
    return applied


# --------------------------------------------------------------------------- versions
def next_version_dir(analysis_root: Path) -> tuple[int, Path]:
    analysis_root.mkdir(parents=True, exist_ok=True)
    nums = [int(p.name[1:]) for p in analysis_root.glob("v*") if p.name[1:].isdigit()]
    n = max(nums, default=0) + 1
    d = analysis_root / f"v{n}"
    d.mkdir()
    return n, d


def load_previous(path: Path | None) -> dict | None:
    if not path:
        return None
    p = Path(path)
    if p.is_dir():
        latest = p / "LATEST"
        if latest.exists():
            p = p / latest.read_text().strip() / "analysis.json"
        elif (p / "analysis.json").exists():
            p = p / "analysis.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def compare(prev: dict | None, results, evidence: dict) -> list[dict]:
    """What changed since the previous version, and why."""
    if not prev:
        return []
    changes = []
    prev_files = {f["sha256"]: f["path"] for f in prev.get("evidence", {}).get("files", [])}
    cur_files = {f["sha256"]: f["path"] for f in evidence.get("files", [])}
    added = [cur_files[h] for h in cur_files if h not in prev_files]
    removed = [prev_files[h] for h in prev_files if h not in cur_files]
    if added or removed:
        changes.append({"kind": "evidence", "change": "evidence updated", "title": "Evidence set changed",
                        "detail": f"{len(added)} file(s) added, {len(removed)} removed", "added": added, "removed": removed})
    prev_items = {i["key"]: i for kind in ("gap", "hypothesis", "contradiction", "insight") for i in prev.get(plural(kind), [])}
    cur_items = {it.key: it for kind in ("gap", "hypothesis", "contradiction", "insight") for it in results.get(kind)}
    for key, p in prev_items.items():
        c = cur_items.get(key)
        if p["kind"] == "gap":
            if c is None:
                changes.append({"kind": "gap", "key": key, "change": "resolved", "title": p["title"],
                                "detail": "the question no longer arises or is now answered by the evidence"})
            elif c.status != p.get("status"):
                change = {"partially_resolved": "partially resolved", "resolved": "resolved", "open": "reopened"}.get(c.status, c.status)
                changes.append({"kind": "gap", "key": key, "change": change, "title": c.title,
                                "detail": f"status {p.get('status')} → {c.status}" + (f"; {c.data.get('answer')}" if c.data.get("answer") else "")})
            elif c.data.get("gap_type") != p["data"].get("gap_type"):
                changes.append({"kind": "gap", "key": key, "change": "changed type", "title": c.title,
                                "detail": f"{p['data'].get('gap_type')} → {c.data.get('gap_type')}"})
            if c is not None:
                c.data["previous_status"] = p.get("status")
        elif p["kind"] == "hypothesis" and c is not None and c.data.get("label") != p["data"].get("label"):
            changes.append({"kind": "hypothesis", "key": key, "change": "re-ranked", "title": c.title,
                            "detail": f"{p['data'].get('label')} → {c.data.get('label')} (score {p['data'].get('points')} → "
                                      f"{c.data.get('points')}); new supporting or contradicting evidence"})
        elif p["kind"] in ("contradiction", "insight"):
            if c is None:
                changes.append({"kind": p["kind"], "key": key, "change": "no longer supported", "title": p["title"],
                                "detail": "re-evaluation with the current evidence did not reproduce it"})
            elif p["kind"] == "insight" and c.data.get("confidence") != p["data"].get("confidence"):
                changes.append({"kind": "insight", "key": key, "change": "confidence changed", "title": c.title,
                                "detail": f"{p['data'].get('confidence')} → {c.data.get('confidence')}"})
    for key, c in cur_items.items():
        if key not in prev_items:
            changes.append({"kind": c.kind, "key": key, "change": "new", "title": c.title, "detail": "appeared in this version"})
    for g in results.get("gap"):
        g.data.setdefault("previous_status", None)
    return changes
