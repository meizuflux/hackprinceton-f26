"""Which chat model each LLM role uses, and how to build it.

Roles and their settings (each a provider-qualified string, `provider:model`, as LangChain's `init_chat_model` takes):

    investigator  MAPLETRACE_INVESTIGATOR_MODEL (legacy: MAPLETRACE_LLM_MODEL)  default anthropic:claude-sonnet-5-5
                  import-time claim extraction, the deep-agent investigator and its verifier
    chat          MAPLETRACE_CHAT_MODEL     default: the investigator's model
    vision        MAPLETRACE_VISION_MODEL   default: the investigator's model
    labels        MAPLETRACE_LABELS_MODEL   default anthropic:claude-haiku-5-5

A bare name gets its provider from its prefix (`gemini-...` Google, `gpt-...` OpenAI) and is otherwise an Anthropic
model, as bare names always were. The provider decides which API key enables live calls (`KEY_ENV`) and which
LangChain integration package must be installed (`PACKAGES`): `langchain-anthropic` and `langchain-google-genai` ship
by default; see backend/README.md, "Choosing models".

Cache keys: LangChain's record/replay key (`llm_cache.py`) already contains the model class and name, so a different
model never replays another model's answers. `ModelSpec.label` is the plain model name for Anthropic models (exactly
the string used before providers were configurable, so committed caches, audit entries and `agent:<model>` labels stay
byte-identical) and `provider:model` for every other provider.
"""

from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass

ROLES = ("investigator", "chat", "vision", "labels")
DEFAULT_INVESTIGATOR = "anthropic:claude-sonnet-5-5"
DEFAULT_LABELS = "anthropic:claude-haiku-5-5"
ENV = {"investigator": "MAPLETRACE_INVESTIGATOR_MODEL", "chat": "MAPLETRACE_CHAT_MODEL",
       "vision": "MAPLETRACE_VISION_MODEL", "labels": "MAPLETRACE_LABELS_MODEL"}
LEGACY_INVESTIGATOR_ENV = "MAPLETRACE_LLM_MODEL"

# provider -> environment variables that hold its key (any one is enough). Unlisted providers use <PROVIDER>_API_KEY.
KEY_ENV = {"anthropic": ("ANTHROPIC_API_KEY",), "google_genai": ("GOOGLE_API_KEY", "GEMINI_API_KEY"),
           "openai": ("OPENAI_API_KEY",)}
# provider -> LangChain integration module (as init_chat_model imports it)
PACKAGES = {"anthropic": "langchain_anthropic", "google_genai": "langchain_google_genai", "openai": "langchain_openai"}
_PREFIXES = (("claude", "anthropic"), ("gemini", "google_genai"), ("gpt-", "openai"), ("o1", "openai"),
             ("o3", "openai"), ("o4", "openai"))


@dataclass(frozen=True)
class ModelSpec:
    provider: str
    name: str

    @property
    def id(self) -> str:
        """`provider:model`, as shown in /health and the run trace context."""
        return f"{self.provider}:{self.name}"

    @property
    def label(self) -> str:
        """The string recorded in cache keys, audit entries and trace events (see the module docstring)."""
        return self.name if self.provider == "anthropic" else self.id

    def key_env(self) -> tuple[str, ...]:
        return KEY_ENV.get(self.provider, (f"{self.provider.upper()}_API_KEY",))

    def has_key(self) -> bool:
        return any(os.environ.get(k) for k in self.key_env())

    def installed(self) -> bool:
        mod = PACKAGES.get(self.provider, f"langchain_{self.provider}")
        return importlib.util.find_spec(mod) is not None

    def live(self) -> bool:
        """A live (billed) call can be made: the provider's key is set and its integration is installed."""
        return self.has_key() and self.installed()

    def key_hint(self) -> str:
        return " or ".join(self.key_env())


def parse(value: "str | ModelSpec") -> ModelSpec:
    """`provider:model`, or a bare model name (provider from its prefix, else Anthropic)."""
    if isinstance(value, ModelSpec):
        return value
    s = (value or "").strip()
    if not s:
        raise ValueError("empty model setting")
    if ":" in s:
        provider, name = s.split(":", 1)
        if provider.strip() and name.strip():
            return ModelSpec(provider.strip().lower(), name.strip())
        raise ValueError(f"bad model setting {value!r}: use provider:model")
    for prefix, provider in _PREFIXES:
        if s.lower().startswith(prefix):
            return ModelSpec(provider, s)
    return ModelSpec("anthropic", s)  # bare names always meant Anthropic models


def _env(name: str) -> str | None:
    v = (os.environ.get(name) or "").strip()
    return v or None


def resolve(role: str, default: "str | None" = None) -> ModelSpec:
    """The model configured for `role`. `default` replaces the built-in default for this call (for example the CLI's
    `--model` as the vision default); the role's own environment variable still wins."""
    if role not in ROLES:
        raise ValueError(f"unknown model role {role!r}; roles are {', '.join(ROLES)}")
    if role == "investigator":
        return parse(_env(ENV[role]) or _env(LEGACY_INVESTIGATOR_ENV) or default or DEFAULT_INVESTIGATOR)
    if role == "labels":
        return parse(_env(ENV[role]) or default or DEFAULT_LABELS)
    return parse(_env(ENV[role]) or default or resolve("investigator"))  # chat and vision follow the investigator


def summary() -> dict:
    """{role: {"model": provider:model, "live": bool}} for /health. Never includes keys."""
    out = {}
    for role in ROLES:
        try:
            spec = resolve(role)
            out[role] = {"model": spec.id, "live": spec.live()}
        except ValueError as exc:
            out[role] = {"model": None, "live": False, "error": str(exc)}
    return out


def make_model(model: "str | ModelSpec", *, max_tokens: int, timeout: float, max_retries: int = 3,
               reasoning_effort: str | None = None, cache=None):
    """A LangChain chat model for `model` via `init_chat_model`. Every argument is part of the recorded request key
    (`llm_cache.py`), so keep them stable: for Anthropic the arguments are exactly those the LLM layer always passed.

    `reasoning_effort` goes to providers that take that parameter (Anthropic, OpenAI); others use their default.
    Without the provider's key the model is built with a placeholder key, so only cached responses work: a replay
    cache raises on a miss before anything is sent."""
    from langchain.chat_models import init_chat_model
    spec = parse(model)
    kw: dict = {"max_tokens": max_tokens}
    if reasoning_effort and spec.provider in ("anthropic", "openai"):
        kw["reasoning_effort"] = reasoning_effort
    kw.update(max_retries=max_retries, timeout=timeout)
    if cache is not None:
        kw["cache"] = cache
    if not spec.has_key():
        kw["api_key"] = "replay-only"
    if not spec.installed():
        mod = PACKAGES.get(spec.provider, f"langchain_{spec.provider}")
        raise RuntimeError(f"model {spec.id} needs the {mod.replace('_', '-')} package; see backend/README.md, "
                           "\"Choosing models\"")
    return init_chat_model(spec.name, model_provider=spec.provider, **kw)
