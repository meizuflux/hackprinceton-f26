"""Optional LLM display labels (inferred, display-only; backend/LABELS.md).

For board cards whose title is still hard to read after the deterministic rules (labels.needs_label: raw key=value
text, event codes, titles over 44 characters), a cheap model (default `claude-haiku-5-5`) writes a short title and one
plain sentence from the card's own text and its cited record excerpts. The result only sets `displayLabel` /
`displaySummary` with `labelOrigin: "llm"` on that card. It never reaches claims, contradictions, explanations, gaps,
insights, the investigator, chat or the vision model, and it never replaces `label` or `summary`
(backend/tests/test_label_llm.py). Media cards are never sent (their vision descriptions stay isolated).

Cache: `llm_cache/labels-<archive sha256>.jsonl`, one JSON object per request, keyed on (card input text, prompt,
model). The default mode only replays: with no cache file the stage is skipped silently, and a card without a recorded
label keeps its rules label (or none). `make backend-label-record` (billed) records the Kestrel labels.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from types import SimpleNamespace

from .labels import MAX_LABEL, needs_label
from .vision import VisionCache

DEFAULT_MODEL = "claude-haiku-5-5"
MAX_SUMMARY = 300
PROMPT = """You write display text for one card on an evidence board used by a case reviewer. The card's data is
below. Rewrite it for a person who does not know the system's codes.

- "label": a short title, at most 44 characters, in plain words. Keep the key identifiers that a reviewer needs
  (names, tag or plate numbers, times) exactly as written.
- "summary": one plain-English sentence, at most 300 characters.
- Use only facts present in the card data. Do not add names, places, times, motives or conclusions. Do not say that
  anyone did anything wrong. If something is unclear, leave it out.
- Never mention nationality, ethnicity, religion or similar attributes.

Reply with JSON only, no other text: {"label": "...", "summary": "..."}"""


def cache_path(archive_sha256: str, root: Path | None = None) -> Path:
    from .llm_cache import CACHE_DIR
    return Path(root or CACHE_DIR) / f"labels-{archive_sha256}.jsonl"


def request_key(card_input: str, prompt: str, model: str) -> str:
    return hashlib.sha256(json.dumps([card_input, prompt, model]).encode()).hexdigest()


def card_input(n: dict, sources: dict[str, dict]) -> str:
    """The card's own text and up to three cited excerpts: everything the model sees about one card. Deterministic for
    the same analysis (no times of analysis, no IDs that change between runs, never vision output)."""
    excerpts = [{"source": cid, "file": sources[cid].get("fileLabel", ""), "text": sources[cid].get("excerpt", "")[:400]}
                for cid in n.get("citations", [])[:3] if cid in sources]
    return json.dumps({"type": n["type"], "kind": n.get("subtitle", ""), "title": n.get("label", ""),
                       "text": n.get("summary", ""), "certainty": n.get("certainty", ""), "excerpts": excerpts},
                      ensure_ascii=False, sort_keys=True)


def parse_reply(text: str, source_text: str) -> dict | None:
    """`{"label", "summary"}` from the reply, or None when unusable: missing or too long, or containing a number that
    is not in the card data (a cheap guard against invented times, counts and IDs)."""
    m = re.search(r"\{.*\}", text or "", re.S)
    try:
        obj = json.loads(m.group(0)) if m else None
    except ValueError:
        obj = None
    if not isinstance(obj, dict) or not isinstance(obj.get("label"), str):
        return None
    label = " ".join(obj["label"].split())
    summary = " ".join(str(obj.get("summary") or "").split())
    if not label or len(label) > MAX_LABEL or len(summary) > MAX_SUMMARY:
        return None
    if any(num not in source_text for num in re.findall(r"\d+", f"{label} {summary}")):
        return None
    return {"label": label, "summary": summary}


class ModelLabeler:
    """`label(text) -> (reply, usage_metadata dict)`. Tests inject an object with the same method."""

    def __init__(self, model: str):
        from .models import make_model
        self.model = make_model(model, max_tokens=400, timeout=60)

    def label(self, text: str):
        from langchain_core.messages import HumanMessage
        msg = self.model.invoke([HumanMessage(content=text)])
        reply = msg.content if isinstance(msg.content, str) else "".join(
            b.get("text", "") for b in msg.content if isinstance(b, dict))
        return reply, dict(getattr(msg, "usage_metadata", None) or {})


def run(case, board: dict, cfg: dict, trace=None, audit=None) -> dict | None:
    """Apply recorded (or, in record mode, newly requested) labels to `board` in place. Returns a summary, or None when
    the stage is skipped (replay mode without a cache file)."""
    from .llm_cache import CACHE_DIR, call_stats
    from .models import parse, resolve
    spec = parse(cfg.get("label_model") or resolve("labels"))  # MAPLETRACE_LABELS_MODEL, default claude-haiku-5-5
    model = spec.label
    mode = cfg.get("label_mode") or "replay"  # recording is explicit (make backend-label-record), never a side effect
    client = cfg.get("label_client")
    if client is None and mode == "record" and spec.live():
        client = ModelLabeler(spec)
    archive = case.info.get("source_archive_sha256", "unknown")
    path = cache_path(archive, Path(cfg.get("label_cache_dir") or cfg.get("cache_dir") or CACHE_DIR))
    if client is None and not path.exists():
        return None
    cache = VisionCache(path, "record" if client else "replay")
    sources = {s["id"]: s for s in board.get("sources", [])}
    started = trace.now_ms() if trace else 0
    applied = skipped = requests = 0
    for n in board["nodes"]:
        if not needs_label(n):
            continue
        text = card_input(n, sources)
        prompt = f"{PROMPT}\n\nCard data:\n{text}"
        key = request_key(text, PROMPT, model)
        row = cache.get(key)
        replayed = row is not None
        if row is None:
            cache.misses += 1
            if client is None:
                skipped += 1
                continue
            try:
                t0 = time.monotonic()
                reply, usage = client.label(prompt)
                latency = round((time.monotonic() - t0) * 1000)
            except Exception as exc:  # noqa: BLE001 - one failed card must not stop the analysis
                skipped += 1
                if audit:
                    audit.write("llm", "display_label_failed", {"node": n["id"], "error": str(exc)[:300]})
                continue
            result = parse_reply(reply, text)
            if result is None:
                skipped += 1
                continue
            row = {"key": key, "node": n["id"], "model": model,
                   "prompt_sha256": hashlib.sha256(PROMPT.encode()).hexdigest(), "result": result, "usage": usage,
                   "latency_ms": latency}
            cache.put(row)
        requests += 1
        if trace:
            stats = call_stats(SimpleNamespace(usage_metadata=row.get("usage") or {}), row.get("latency_ms"),
                               None if replayed else "live")
            if replayed:
                start, end = trace.replayed_call(stats["durationMs"])
                trace.llm_call("display_labels", model, stats, True, end, start)
            else:
                end = trace.now_ms()
                trace.llm_call("display_labels", model, stats, False, end, max(end - stats["durationMs"], 0))
        res = row["result"]
        n["displayLabel"] = res["label"]
        if res.get("summary"):
            n["displaySummary"] = res["summary"]
        n["labelOrigin"] = "llm"
        applied += 1
    summary = {"enabled": True, "model": model, "mode": cache.mode, "cache": cache.path.name, "labelled": applied,
               "requests": requests, "recorded": cache.recorded, "misses": cache.misses, "skipped": skipped}
    if audit:
        audit.write("llm", "display_labels", {k: v for k, v in summary.items() if k != "enabled"})
    if trace:
        trace.stage_finished("display_labels", "Display labels", {"labelled": applied, "skipped": skipped}, started)
    return summary
