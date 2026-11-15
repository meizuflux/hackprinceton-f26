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
"""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from typing import Any, Literal, Optional, Sequence

from langchain_core.caches import BaseCache
from langchain_core.load import dumps, loads

CACHE_DIR = Path(__file__).resolve().parents[1] / "llm_cache"
Mode = Literal["record", "replay"]


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
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    row = json.loads(line)
                    self._entries[row["key"]] = row["generations"]

    def __len__(self) -> int:
        return len(self._entries)

    def lookup(self, prompt: str, llm_string: str) -> Optional[Sequence]:
        key = request_key(prompt, llm_string)
        with self._lock:
            raw = self._entries.get(key)
            if raw is not None:
                self.hits += 1
                return loads(raw)
            self.misses += 1
        if self.mode == "replay":
            raise CacheMiss(f"no recorded response for request {key[:12]} in {self.path.name}")
        return None

    def update(self, prompt: str, llm_string: str, return_val: Sequence) -> None:
        if self.mode == "replay":
            return
        key = request_key(prompt, llm_string)
        raw = dumps(list(return_val))
        with self._lock:
            if key in self._entries:
                return
            self._entries[key] = raw
            self.recorded += 1
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"key": key, "generations": raw}) + "\n")

    def clear(self, **kwargs: Any) -> None:
        with self._lock:
            self._entries.clear()

    def stats(self) -> dict:
        return {"file": self.path.name, "mode": self.mode, "entries": len(self._entries), "hits": self.hits,
                "misses": self.misses, "recorded": self.recorded}
