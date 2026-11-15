"""Case chat service behind `GET /chat/status` and `POST /cases/{caseId}/chat` (see `mapletrace_reason/chat.py`).

Cost control:
- Every model response is stored in `backend/llm_cache/chat-<archive sha256>.jsonl`, keyed by the full request, so
  the same question in the same thread state replays for free.
- Suggested questions are always answered without the thread's history, so their recorded answers replay in any
  thread. `python -m mapletrace_api.chat record` (make backend-chat-record) records them for the Kestrel demo; billed.
- With the chat model provider's API key (ANTHROPIC_API_KEY for the default) the cache records (a miss calls the
  model, billed). Without it the cache only replays: a miss raises before any request is sent and the API answers
  `needs_api_key`.
- The chat model is its own role (`MAPLETRACE_CHAT_MODEL`, see `mapletrace_reason/models.py`) and may differ from
  the model that analysed the case. The cache key contains the model class and name, so answers recorded with one
  model never replay as another's.

Conversation memory is per thread in server memory, bounded (`MAX_THREADS`, `HISTORY_TURNS`), and lost on restart.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from mapletrace_reason.chat import HISTORY_TURNS, CaseChat
from mapletrace_reason import models
from mapletrace_reason.llm_cache import CACHE_DIR, CacheMiss, ReplayCache

CHAT = models.resolve("chat")  # MAPLETRACE_CHAT_MODEL, else the investigator's model
CHAT_MODEL = CHAT.label         # "claude-sonnet-5-5" by default
CHAT_REASONING_EFFORT = "medium"
MAX_THREADS = 200
MAX_MESSAGE = 1000


class ChatError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


def chat_cache_path(archive_sha256: str, root: Path | None = None) -> Path:
    return Path(root or CACHE_DIR) / f"chat-{archive_sha256}.jsonl"


def _norm(q: str) -> str:
    return " ".join(q.split()).casefold()


@dataclass
class Thread:
    case_id: str
    history: list[tuple[str, str]] = field(default_factory=list)
    record_ids: set[int] = field(default_factory=set)
    lock: threading.Lock = field(default_factory=threading.Lock)


class ChatService:
    def __init__(self, cache_dir: Path | None = None, model_factory: Optional[Callable] = None):
        self.cache_dir = cache_dir
        self.model_factory = model_factory  # tests inject a fake: factory(cache) -> chat model
        self._chats: dict[tuple[str, str], CaseChat] = {}
        self._threads: OrderedDict[str, Thread] = OrderedDict()
        self._caches: dict[Path, ReplayCache] = {}
        self._probes: dict[tuple[str, str], tuple[int, bool]] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ setup
    @staticmethod
    def live() -> bool:
        return CHAT.live()

    def case_chat(self, case_id: str, ingest_dir: Path, analysis_dir: Path) -> CaseChat:
        key = (case_id, str(analysis_dir))
        with self._lock:
            chat = self._chats.get(key)
            if chat is None:
                for k in [k for k in self._chats if k[0] == case_id]:
                    del self._chats[k]  # an older analysis version of this case
                chat = self._chats[key] = CaseChat(ingest_dir, analysis_dir)
        return chat

    def forget(self, case_id: str) -> None:
        """Drop the loaded analysis of a case whose files were replaced in place (a reinstalled demo)."""
        with self._lock:
            for k in [k for k in self._chats if k[0] == case_id]:
                del self._chats[k]

    def cache(self, sha: str) -> ReplayCache:
        """The shared cache for answering: records with a key, replays without one."""
        path = chat_cache_path(sha, self.cache_dir)
        mode = "record" if self.live() else "replay"
        with self._lock:
            c = self._caches.get(path)
            if c is None or c.mode != mode:
                c = self._caches[path] = ReplayCache(path, mode)
        return c

    def model(self, cache: ReplayCache):
        if self.model_factory is not None:
            return self.model_factory(cache)
        from mapletrace_reason.llm import make_chat_model
        return make_chat_model(CHAT_MODEL, cache, CHAT_REASONING_EFFORT)

    # ------------------------------------------------------------------ status
    def recorded(self, chat: CaseChat, question: str) -> bool:
        """Whether a suggested question replays completely from the cache. Checked by replaying it (no API call,
        replay-only cache); remembered until the cache file changes."""
        path = chat_cache_path(chat.archive_sha256, self.cache_dir)
        if not path.exists():
            return False
        size = path.stat().st_size
        memo = self._probes.get((str(path), question))
        if memo and memo[0] == size:
            return memo[1]
        try:
            chat.answer(question, [], self.model(ReplayCache(path, "replay")))
            ok = True
        except CacheMiss:
            ok = False
        except Exception:  # noqa: BLE001 - a broken recording counts as not recorded
            ok = False
        self._probes[(str(path), question)] = (size, ok)
        return ok

    def status(self, case_id: str, chat: CaseChat) -> dict:
        live = self.live()
        suggestions = [{"question": q, "recorded": self.recorded(chat, q)} for q in chat.suggestions]
        out = {"available": True, "authoritative": True, "case_id": case_id, "live": live,
               "mode": "live" if live else "replay", "model": CHAT_MODEL, "modelId": CHAT.id,
               "suggestions": suggestions}
        if not live:
            out["reason"] = (f"Live questions need an API key ({CHAT.key_hint()}) for {CHAT.id} on the server. "
                             "Recorded answers to suggested questions still replay.")
        return out

    # ------------------------------------------------------------------ answering
    def _thread(self, case_id: str, thread_id: Optional[str]) -> tuple[str, Thread]:
        with self._lock:
            t = self._threads.get(thread_id or "")
            if t is None or t.case_id != case_id:
                thread_id, t = uuid.uuid4().hex, Thread(case_id)
                self._threads[thread_id] = t
                while len(self._threads) > MAX_THREADS:
                    self._threads.popitem(last=False)
            self._threads.move_to_end(thread_id)
        return thread_id, t

    def ask(self, case_id: str, chat: CaseChat, message: str, thread_id: Optional[str] = None) -> dict:
        question = " ".join((message or "").split())
        if not question:
            raise ChatError(400, "empty_message", "Type a question.")
        if len(question) > MAX_MESSAGE:
            raise ChatError(400, "message_too_long", f"Keep questions under {MAX_MESSAGE} characters.")
        suggested = next((q for q in chat.suggestions if _norm(q) == _norm(question)), None)
        thread_id, t = self._thread(case_id, thread_id)
        cache = self.cache(chat.archive_sha256)
        with t.lock:
            before = cache.misses
            try:
                if suggested:  # standalone, so the recorded answer replays in any thread
                    ans = chat.answer(suggested, [], self.model(cache))
                else:
                    ans = chat.answer(question, t.history, self.model(cache), t.record_ids)
            except CacheMiss:
                raise ChatError(503, "needs_api_key",
                                f"This answer has not been recorded, and live questions need an API key "
                                f"({CHAT.key_hint()}) on the server. Suggested questions replay once their answers "
                                "are recorded.") from None
            except ChatError:
                raise
            except Exception as exc:  # noqa: BLE001 - report model and network failures without a stack trace
                raise ChatError(502, "model_error", f"The model call failed ({type(exc).__name__}). Try again.") from None
            t.history = (t.history + [(question, ans.content)])[-HISTORY_TURNS:]
            t.record_ids |= set(ans.record_ids)
        return {"thread_id": thread_id, "message": ans.message(), "suggested": bool(suggested),
                "replayed": cache.misses == before, "model_calls": ans.model_calls,
                "steps": ans.steps}


# ---------------------------------------------------------------------- recording
def record(argv=None) -> int:
    """Record answers to the Kestrel demo's suggested questions (billed: needs the chat model's API key)."""
    p = argparse.ArgumentParser(prog="mapletrace_api.chat")
    p.add_argument("command", choices=["record", "suggestions"])
    args = p.parse_args(argv)
    if args.command == "record" and not CHAT.live():
        raise SystemExit(f"recording calls the API: set {CHAT.key_hint()} for {CHAT.id} (billed)")
    import shutil
    import tempfile
    data = tempfile.mkdtemp(prefix="mapletrace-chat-")
    os.environ["MAPLETRACE_DATA"] = data
    try:
        return _record(args.command)
    finally:
        shutil.rmtree(data, ignore_errors=True)


def _record(command: str) -> int:
    from mapletrace_api import app as api  # imported after MAPLETRACE_DATA is set

    from fastapi import BackgroundTasks
    case_id = api.open_demo(BackgroundTasks())["caseId"]  # a fresh data dir: a clean install, no re-analysis job
    ingest_dir, analysis_dir = api._latest_dirs(case_id)
    service = ChatService()
    chat = service.case_chat(case_id, ingest_dir, analysis_dir)
    if command == "suggestions":
        print(json.dumps(service.status(case_id, chat), indent=1))
        return 0
    for q in chat.suggestions:
        try:
            out = service.ask(case_id, chat, q)
        except ChatError as exc:
            print(f"- {q}\n  failed: {exc.message}")
            continue
        m = out["message"]
        print(f"- {q}\n  {m['evidence_status']}, {len(m['citations'])} citations, {out['model_calls']} model calls, "
              f"{'replayed' if out['replayed'] else 'recorded'}")
    stats = service.cache(chat.archive_sha256).stats()
    print(f"Recorded {stats['recorded']} responses into backend/llm_cache/{stats['file']}")
    return 0


if __name__ == "__main__":
    sys.exit(record())
