"""Image description (optional, isolated): a neutral, literal description of each photo and a few video frames.

Runs only with the LLM layer. Output is attached to the media card (`media.vision`, origin `llm`, certainty
`inferred`) and goes nowhere else: it is never fed to claims, contradictions, explanations, gaps, insights or the
investigator, so the recorded investigator and chat caches stay valid (backend/tests/test_vision.py).

Cache: `llm_cache/vision-<archive sha256>.jsonl`, one JSON object per request, keyed on
(evidence sha256, frame time, prompt text, model). The key does not involve decoded pixels, so a replay never opens
an image or decodes video. Recording needs Pillow and, for video, PyAV (`av`) or an `ffmpeg` binary.

Modes follow the LLM layer: `record` answers from the cache and otherwise calls the model (billed); `replay`, or
`record` without ANTHROPIC_API_KEY, only reads the cache. A miss skips that image and is counted in the summary; it
never fails the run.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

from .media import media_rows

FRAMES = (0.1, 0.5, 0.9)   # video frames at these fractions of the duration
MAX_SIDE = 1024
JPEG_QUALITY = 85
PROMPT = """You are describing one image from an evidence file for a case reviewer. Describe only what is visible,
neutrally and literally.

- List the visible objects, vehicles, signs, screens and the setting.
- Transcribe any legible text exactly as it appears (licence plates, labels, signs, timestamps or camera names burned
  into the frame). Write [illegible] where it cannot be read.
- Describe people only by visible clothing, actions and objects they carry. Do not identify anyone, do not name
  anyone, and do not state or guess age, ethnicity, nationality, religion, health or other personal attributes.
- Do not guess intent, motive or what happened before or after.

Reply with JSON only, no other text: {"text": "<two or three sentences>", "observations": ["<one short literal
observation>", ...]} with at most 8 observations."""


def cache_path(archive_sha256: str, root: Path | None = None) -> Path:
    from .llm_cache import CACHE_DIR
    return Path(root or CACHE_DIR) / f"vision-{archive_sha256}.jsonl"


def request_key(evidence_sha256: str, frame_s: float | None, prompt: str, model: str) -> str:
    return hashlib.sha256(json.dumps([evidence_sha256, frame_s, prompt, model]).encode()).hexdigest()


class VisionCache:
    def __init__(self, path: Path, mode: str):
        self.path, self.mode = Path(path), mode
        self.hits = self.misses = self.recorded = 0
        self.entries: dict[str, dict] = {}
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    row = json.loads(line)
                    self.entries[row["key"]] = row

    def get(self, key: str) -> dict | None:
        row = self.entries.get(key)
        self.hits += row is not None
        return row

    def put(self, row: dict) -> None:
        if self.mode == "replay" or row["key"] in self.entries:
            return
        self.entries[row["key"]] = row
        self.recorded += 1
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------- decoding (recording only)
def to_jpeg(raw: bytes) -> bytes:
    """Downscale to at most MAX_SIDE px and re-encode as JPEG with fixed settings (EXIF dropped)."""
    from PIL import Image
    with Image.open(io.BytesIO(raw)) as im:
        im = im.convert("RGB")
        im.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
        out = io.BytesIO()
        im.save(out, "JPEG", quality=JPEG_QUALITY, optimize=False)
        return out.getvalue()


def video_frame(path: Path, t: float) -> bytes:
    """The first frame at or after `t` seconds, as JPEG: PyAV, else an ffmpeg binary."""
    try:
        import av
        with av.open(str(path)) as c:
            stream = c.streams.video[0]
            c.seek(int(t * 1_000_000))
            last = None
            for frame in c.decode(stream):
                last = frame
                if frame.time is None or frame.time >= t - 1e-3:
                    break
            if last is not None:
                buf = io.BytesIO()
                last.to_image().save(buf, "PNG")
                return to_jpeg(buf.getvalue())
    except Exception:  # noqa: BLE001 - fall through to ffmpeg
        pass
    ff = shutil.which("ffmpeg")
    if not ff:
        raise RuntimeError("frame extraction needs PyAV (av) or an ffmpeg binary")
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "f.png"
        subprocess.run([ff, "-v", "error", "-ss", f"{t:.3f}", "-i", str(path), "-frames:v", "1", str(out)], check=True,
                       timeout=120)
        return to_jpeg(out.read_bytes())


# ---------------------------------------------------------------- model
class AnthropicVision:
    """`describe(jpeg, prompt) -> (reply text, usage_metadata dict)`. Tests inject an object with the same method."""

    def __init__(self, model: str):
        from langchain_anthropic import ChatAnthropic
        self.model = ChatAnthropic(model=model, max_tokens=1500, max_retries=3, timeout=180)

    def describe(self, jpeg: bytes, prompt: str):
        from langchain_core.messages import HumanMessage
        url = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()
        msg = self.model.invoke([HumanMessage(content=[{"type": "image_url", "image_url": {"url": url}},
                                                       {"type": "text", "text": prompt}])])
        text = msg.content if isinstance(msg.content, str) else "".join(
            b.get("text", "") for b in msg.content if isinstance(b, dict))
        return text, dict(getattr(msg, "usage_metadata", None) or {})


def parse_reply(text: str) -> dict | None:
    """`{"text", "observations": [str]}` from the model reply (tolerates code fences); None when unusable."""
    m = re.search(r"\{.*\}", text or "", re.S)
    try:
        obj = json.loads(m.group(0)) if m else None
    except ValueError:
        obj = None
    if not isinstance(obj, dict) or not isinstance(obj.get("text"), str) or not obj["text"].strip():
        return None
    obs = [str(o).strip() for o in obj.get("observations") or [] if isinstance(o, (str, int, float)) and str(o).strip()]
    return {"text": obj["text"].strip(), "observations": obs[:8]}


def frame_times(m: dict) -> list[float | None]:
    if m["media_kind"] == "photo":
        return [None]
    d = float(m["duration_s"] or 0)
    return [round(d * f, 1) for f in FRAMES] if d > 0 else []


def prompt_for(frame_s: float | None) -> str:
    return PROMPT if frame_s is None else f"{PROMPT}\n\nThis image is a frame taken {frame_s:g} s into a video clip."


def run(case, cfg: dict, trace=None, audit=None) -> tuple[dict, dict]:
    """Describe every photo and video. Returns ({evidence_id: vision}, summary)."""
    from .llm_cache import CACHE_DIR, call_stats
    model = cfg.get("model") or "claude-sonnet-5-5"
    mode = cfg.get("vision_mode") or cfg.get("cache_mode", "record")  # vision_mode: record only the vision cache
    client = cfg.get("vision_client")
    if client is None and mode == "record" and os.environ.get("ANTHROPIC_API_KEY"):
        client = AnthropicVision(model)
    archive = case.info.get("source_archive_sha256", "unknown")
    cache = VisionCache(cache_path(archive, Path(cfg.get("vision_cache_dir") or cfg.get("cache_dir") or CACHE_DIR)),
                        "record" if client else "replay")
    started = trace.now_ms() if trace else 0
    out: dict[str, dict] = {}
    requests = skipped = 0

    def log(m, frame_s, key, reply):
        if audit:
            audit.write("llm", "media_vision", {"evidence_id": m["evidence_id"], "frameS": frame_s, "model": model,
                                                "input_sha256": key,
                                                "output_sha256": hashlib.sha256(json.dumps(reply, sort_keys=True).encode()).hexdigest()})

    for m in media_rows(case):
        obs, texts = [], []
        for t in frame_times(m):
            prompt = prompt_for(t)
            key = request_key(m["sha256"], t, prompt, model)
            row = cache.get(key)
            replayed = row is not None
            if row is None:
                cache.misses += 1
                if client is None:
                    skipped += 1
                    continue
                try:
                    path = case.run_dir / case.files[m["file_id"]]["stored_path"]
                    jpeg = to_jpeg(path.read_bytes()) if t is None else video_frame(path, t)
                    t0 = time.monotonic()
                    reply, usage = client.describe(jpeg, prompt)
                    latency = round((time.monotonic() - t0) * 1000)
                except Exception as exc:  # noqa: BLE001 - one failed image must not stop the analysis
                    skipped += 1
                    if audit:
                        audit.write("llm", "media_vision_failed", {"evidence_id": m["evidence_id"], "frameS": t,
                                                                   "error": str(exc)[:300]})
                    continue
                result = parse_reply(reply)
                if result is None:
                    skipped += 1
                    continue
                row = {"key": key, "evidence_id": m["evidence_id"], "evidence_sha256": m["sha256"], "frameS": t,
                       "model": model, "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(), "result": result,
                       "usage": usage, "latency_ms": latency}
                cache.put(row)
            requests += 1
            log(m, t, key, row["result"])
            if trace:
                stats = call_stats(SimpleNamespace(usage_metadata=row.get("usage") or {}), row.get("latency_ms"),
                                   None if replayed else "live")
                if replayed:
                    start, end = trace.replayed_call(stats["durationMs"])
                    trace.llm_call("media_vision", model, stats, True, end, start)
                else:
                    end = trace.now_ms()
                    trace.llm_call("media_vision", model, stats, False, end, max(end - stats["durationMs"], 0))
            res = row["result"]
            texts.append(res["text"] if t is None else f"At {t:g} s: {res['text']}")
            obs += [{"text": o, "frameS": t} for o in res["observations"]]
            if t is None and not res["observations"]:
                obs.append({"text": res["text"], "frameS": None})
        if texts:
            out[m["evidence_id"]] = {"text": " ".join(texts), "observations": obs, "model": model, "origin": "llm",
                                     "certainty": "inferred"}
    summary = {"enabled": True, "model": model, "mode": cache.mode, "cache": cache.path.name, "files": len(out),
               "requests": requests, "recorded": cache.recorded, "misses": cache.misses, "skipped": skipped}
    if trace:
        trace.stage_finished("media_vision", "Image descriptions", {"described": len(out), "skipped": skipped}, started)
    return out, summary
