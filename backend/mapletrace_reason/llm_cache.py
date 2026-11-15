"""Record/replay cache for the LLM layer.

Model calls cost money, and the deterministic pipeline sends the same requests for the same evidence, so every
model response is stored by a hash of its request (the messages plus the model settings). Cache files live in
`backend/llm_cache/<archive sha256>.jsonl`, one per uploaded archive, and are committed so the demo replays them.

Modes:
- `record`: answer from the cache when possible, otherwise call the model and store the response.
- `replay`: answer only from the cache. A miss raises `CacheMiss` before any request is sent, so a replayed run
  can never be billed; the LLM layer logs the failed call and the deterministic analysis carries on.

Two fields are left out of the key: message `id`s, which LangGraph sometimes generates at random, and
`usage_metadata.total_cost`, which LangChain adds to every cached response it returns. A replayed response goes back
into the agent's history, so without this the next request would differ from the recorded one.

Timing and cost (for the run trace, backend/TRACE.md): a recorded entry may carry `latency_ms`, the wall time of the
original call, stored beside the response (never part of the key; older entries without it still load). `call_stats`
turns a response (or a chat message) into the camelCase numbers the trace and the chat `steps` show. Entries without a
latency get an estimate, flagged `durationSource: "estimated"`:

    estimated duration = 800 ms + output_tokens / 55 tokens per second

(output tokens include reasoning tokens; 55 tok/s and 0.8 s time-to-first-token are typical Sonnet-class figures, not
a measurement). Cost uses backend/LLM_COSTS.md: $2 input, $10 output, $0.20 cache read and $2.50 five-minute cache
write per million tokens.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path
from typing import Any, Literal, Optional, Sequence

from langchain_core.caches import BaseCache
from langchain_core.load import dumps, loads

CACHE_DIR = Path(__file__).resolve().parents[1] / "llm_cache"
Mode = Literal["record", "replay"]


# $ per million tokens (Sonnet 5.5, backend/LLM_COSTS.md)
PRICE_PER_MTOK = {"input": 2.0, "output": 10.0, "cache_read": 0.20, "cache_write": 2.50}
EST_BASE_MS, EST_TOKENS_PER_S = 800, 55


def _usage_of(obj) -> dict:
    """usage_metadata of a Generation, a list of them or a message; {} when there is none."""
    if isinstance(obj, (list, tuple)):
        obj = obj[0] if obj else None
    msg = getattr(obj, "message", obj)
    return dict(getattr(msg, "usage_metadata", None) or {})


def call_stats(generation_or_message, latency_ms: float | None = None, source: str | None = None) -> dict:
    """{inputTokens, outputTokens, cacheReadTokens, cacheWriteTokens, costUsd, durationMs, durationSource} for one
    model response. `inputTokens` counts only uncached input (LangChain's `input_tokens` includes cache reads and
    writes). `latency_ms` is the measured or recorded wall time; without it the duration is estimated (see the module
    docstring). `source` overrides `durationSource` (`"live"` for a call that was just made)."""
    u = _usage_of(generation_or_message)
    detail = u.get("input_token_details") or {}
    read, write = int(detail.get("cache_read") or 0), int(detail.get("cache_creation") or 0)
    out = int(u.get("output_tokens") or 0)
    fresh = max(int(u.get("input_tokens") or 0) - read - write, 0)
    cost = (fresh * PRICE_PER_MTOK["input"] + out * PRICE_PER_MTOK["output"] + read * PRICE_PER_MTOK["cache_read"]
            + write * PRICE_PER_MTOK["cache_write"]) / 1e6
    if latency_ms is None:
        duration, src = EST_BASE_MS + out / EST_TOKENS_PER_S * 1000, "estimated"
    else:
        duration, src = latency_ms, source or "recorded"
    return {"inputTokens": fresh, "outputTokens": out, "cacheReadTokens": read, "cacheWriteTokens": write,
            "costUsd": round(cost, 6), "durationMs": int(round(duration)), "durationSource": src}


class CacheMiss(RuntimeError):
    """A replay-only run asked for a response that was never recorded."""


def cache_path(archive_sha256: str, root: Path = CACHE_DIR) -> Path:
    return root / f"{archive_sha256}.jsonl"


def _strip_ids(obj: Any) -> Any:
    if isinstance(obj, dict):
        out = {k: _strip_ids(v) for k, v in obj.items() if not (k == "id" and not isinstance(v, list))}
        if "usage_metadata" in out:
            usage = {k: v for k, v in (out["usage_metadata"] or {}).items() if k != "total_cost"}
            if usage:
                out["usage_metadata"] = usage
            else:
                del out["usage_metadata"]
        return out
    if isinstance(obj, list):
        return [_strip_ids(v) for v in obj]
    return obj


def request_key(prompt: str, llm_string: str) -> str:
    try:
        prompt = json.dumps(_strip_ids(json.loads(prompt)), sort_keys=True)
    except ValueError:
        pass
    return hashlib.sha256(f"{prompt}\n---\n{llm_string}".encode()).hexdigest()


class ReplayCache(BaseCache):
    """A LangChain cache backed by an append-only JSONL file."""

    def __init__(self, path: Path, mode: Mode = "record"):
        self.path, self.mode = Path(path), mode
        self.hits = self.misses = self.recorded = 0
        self._lock = threading.Lock()
        self._entries: dict[str, str] = {}
        self._latency: dict[str, float] = {}   # key -> recorded latency_ms (absent for older entries)
        self._started: dict[tuple, float] = {}  # (thread, key) -> monotonic start of a live call
        # `listener(info)` is called for every response served or recorded: {tag, replayed, generations,
        # latency_ms (None when unknown), key}. The run trace uses it; it never changes what the cache returns.
        self.listener = None
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    row = json.loads(line)
                    self._entries[row["key"]] = row["generations"]
                    if row.get("latency_ms") is not None:
                        self._latency[row["key"]] = row["latency_ms"]

    def __len__(self) -> int:
        return len(self._entries)

    def lookup(self, prompt: str, llm_string: str, tag: str | None = None) -> Optional[Sequence]:
        key = request_key(prompt, llm_string)
        with self._lock:
            raw = self._entries.get(key)
            if raw is not None:
                self.hits += 1
                latency = self._latency.get(key)
            else:
                self.misses += 1
                self._started[(threading.get_ident(), key)] = time.monotonic()
        if raw is not None:
            gens = loads(raw)
            if self.listener:
                self.listener({"tag": tag, "replayed": True, "generations": gens, "latency_ms": latency, "key": key})
            return gens
        if self.mode == "replay":
            raise CacheMiss(f"no recorded response for request {key[:12]} in {self.path.name}")
        return None

    def update(self, prompt: str, llm_string: str, return_val: Sequence, tag: str | None = None) -> None:
        if self.mode == "replay":
            return
        key = request_key(prompt, llm_string)
        raw = dumps(list(return_val))
        with self._lock:
            started = self._started.pop((threading.get_ident(), key), None)
            latency = round((time.monotonic() - started) * 1000) if started is not None else None
            if key in self._entries:
                return
            self._entries[key] = raw
            if latency is not None:
                self._latency[key] = latency
            self.recorded += 1
            self.path.parent.mkdir(parents=True, exist_ok=True)
            row = {"key": key, "generations": raw, **({"latency_ms": latency} if latency is not None else {})}
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row) + "\n")
        if self.listener:
            self.listener({"tag": tag, "replayed": False, "generations": list(return_val), "latency_ms": latency, "key": key})

    def tagged(self, tag: str) -> "BaseCache":
        """A view of this cache that labels its calls (for example `verifier`) in listener events."""
        return _Tagged(self, tag)

    def clear(self, **kwargs: Any) -> None:
        with self._lock:
            self._entries.clear()

    def stats(self) -> dict:
        return {"file": self.path.name, "mode": self.mode, "entries": len(self._entries), "hits": self.hits,
                "misses": self.misses, "recorded": self.recorded}


class _Tagged(BaseCache):
    def __init__(self, cache: ReplayCache, tag: str):
        self.cache, self.tag = cache, tag

    def lookup(self, prompt: str, llm_string: str) -> Optional[Sequence]:
        return self.cache.lookup(prompt, llm_string, self.tag)

    def update(self, prompt: str, llm_string: str, return_val: Sequence) -> None:
        self.cache.update(prompt, llm_string, return_val, self.tag)

    def clear(self, **kwargs: Any) -> None:
        self.cache.clear(**kwargs)
