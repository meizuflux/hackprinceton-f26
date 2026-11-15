"""Model roles and providers (mapletrace_reason/models.py). Never calls a provider API."""

import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mapletrace_reason import models  # noqa: E402
from mapletrace_reason.models import ModelSpec, parse, resolve  # noqa: E402

KEYS = ("ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY")


@pytest.fixture
def clean_env(monkeypatch):
    for name in (*models.ENV.values(), models.LEGACY_INVESTIGATOR_ENV, *KEYS):
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def test_defaults_are_unchanged(clean_env):
    assert resolve("investigator") == ModelSpec("anthropic", "claude-sonnet-5-5")
    assert resolve("chat") == resolve("investigator")
    assert resolve("vision") == resolve("investigator")
    assert resolve("labels") == ModelSpec("anthropic", "claude-haiku-5-5")
    # the label is what cache keys, audit entries and agent:<model> labels always used
    assert resolve("investigator").label == "claude-sonnet-5-5"
    from mapletrace_reason.llm import DEFAULT_MODEL
    assert DEFAULT_MODEL == "claude-sonnet-5-5"


def test_role_settings_and_fallbacks(clean_env):
    clean_env.setenv("MAPLETRACE_LLM_MODEL", "claude-opus-5-5")  # legacy name still works
    assert resolve("investigator").name == "claude-opus-5-5" and resolve("chat").name == "claude-opus-5-5"
    clean_env.setenv("MAPLETRACE_INVESTIGATOR_MODEL", "google_genai:gemini-3-pro")
    assert resolve("investigator") == ModelSpec("google_genai", "gemini-3-pro")
    assert resolve("vision").id == "google_genai:gemini-3-pro"
    clean_env.setenv("MAPLETRACE_CHAT_MODEL", "anthropic:claude-sonnet-5-5")  # chat may differ from import
    assert resolve("chat").label == "claude-sonnet-5-5" and resolve("investigator").provider == "google_genai"
    clean_env.setenv("MAPLETRACE_LABELS_MODEL", "gemini-3-flash")
    assert resolve("labels") == ModelSpec("google_genai", "gemini-3-flash")
    # a caller default (the CLI's --model) applies only when the role's own variable is unset
    assert resolve("vision", "claude-opus-5-5").name == "claude-opus-5-5"
    clean_env.setenv("MAPLETRACE_VISION_MODEL", "openai:gpt-5")
    assert resolve("vision", "claude-opus-5-5").id == "openai:gpt-5"
    with pytest.raises(ValueError):
        resolve("summariser")


def test_parse():
    assert parse("anthropic:claude-sonnet-5-5").label == "claude-sonnet-5-5"
    assert parse("claude-sonnet-5-5") == parse("anthropic:claude-sonnet-5-5")
    assert parse(" Google_GenAI : gemini-3-pro ").id == "google_genai:gemini-3-pro"
    assert parse("google_genai:gemini-3-pro").label == "google_genai:gemini-3-pro"
    assert parse("gpt-5").provider == "openai"
    assert parse("mystery-model").provider == "anthropic"  # bare names always meant Anthropic
    for bad in ("", ":x", "anthropic:"):
        with pytest.raises(ValueError):
            parse(bad)


def test_live_depends_on_the_configured_providers_key(clean_env):
    google = parse("google_genai:gemini-3-pro")
    claude = parse("claude-sonnet-5-5")
    assert not google.live() and not claude.live()
    clean_env.setenv("ANTHROPIC_API_KEY", "sk-test")
    assert claude.live() and not google.live()
    clean_env.setenv("GEMINI_API_KEY", "g-test")
    assert google.has_key() and google.key_hint() == "GOOGLE_API_KEY or GEMINI_API_KEY"
    assert parse("mistralai:mistral-large").key_env() == ("MISTRALAI_API_KEY",)
    assert not parse("nosuchprovider:m").installed()


def _old_chat_model(model, reasoning_effort):
    """The ChatAnthropic the LLM layer built before models were configurable (replay mode, no key)."""
    from langchain_anthropic import ChatAnthropic
    return ChatAnthropic(model=model, max_tokens=16000, reasoning_effort=reasoning_effort, max_retries=3, timeout=600,
                         cache=None, api_key="replay-only")


def test_default_cache_keys_are_byte_identical(clean_env):
    """The committed caches key on LangChain's llm_string: the default models must produce exactly the old one."""
    from mapletrace_api import chat as chat_api
    from mapletrace_reason.llm import make_chat_model
    for effort in ("high", "medium"):  # investigator, verifier (chat uses medium)
        assert make_chat_model("claude-sonnet-5-5", None, effort)._get_llm_string() == \
            _old_chat_model("claude-sonnet-5-5", effort)._get_llm_string()
    importlib.reload(chat_api)
    assert chat_api.CHAT_MODEL == "claude-sonnet-5-5"
    m = make_chat_model(chat_api.CHAT_MODEL, None, chat_api.CHAT_REASONING_EFFORT)
    assert m._get_llm_string() == _old_chat_model("claude-sonnet-5-5", "medium")._get_llm_string()
    # the key holds the class and the model name, so a recorded key cannot belong to another model
    assert '"ChatAnthropic"' in m._get_llm_string() and '"claude-sonnet-5-5"' in m._get_llm_string()
    # vision keys use the plain model label, as before
    from mapletrace_reason import vision
    assert vision.request_key("ab", None, "p", resolve("vision").label) == vision.request_key("ab", None, "p",
                                                                                             "claude-sonnet-5-5")


def test_chat_cache_key_changes_with_the_chat_model(clean_env):
    from mapletrace_reason.llm import make_chat_model
    from mapletrace_reason.llm_cache import request_key
    prompt = '[{"role": "user", "content": "q"}]'
    default = request_key(prompt, make_chat_model("claude-sonnet-5-5", None, "medium")._get_llm_string())
    opus = request_key(prompt, make_chat_model("anthropic:claude-opus-5-5", None, "medium")._get_llm_string())
    assert default != opus
    pytest.importorskip("langchain_google_genai")
    gemini = make_chat_model("google_genai:gemini-3-pro", None, "medium")  # placeholder key: built, never called
    assert type(gemini).__name__ == "ChatGoogleGenerativeAI"
    assert request_key(prompt, gemini._get_llm_string()) not in (default, opus)


def test_missing_integration_package_is_reported(clean_env):
    with pytest.raises(RuntimeError, match="langchain-nosuchprovider"):
        models.make_model("nosuchprovider:m", max_tokens=10, timeout=1)


def test_health_and_chat_status_expose_models_without_keys(clean_env, tmp_path):
    from fastapi.testclient import TestClient
    clean_env.setenv("MAPLETRACE_DATA", str(tmp_path / "data"))
    clean_env.setenv("MAPLETRACE_INVESTIGATOR_MODEL", "google_genai:gemini-3-pro")
    clean_env.setenv("MAPLETRACE_CHAT_MODEL", "claude-sonnet-5-5")
    clean_env.setenv("ANTHROPIC_API_KEY", "sk-secret-test")
    import mapletrace_api.app as appmod
    import mapletrace_api.chat as chat_api
    try:
        importlib.reload(chat_api)
        importlib.reload(appmod)
        client = TestClient(appmod.app)
        h = client.get("/health").json()
        assert h["llmLive"] is False  # the investigator is Gemini and GOOGLE_API_KEY is unset
        assert h["models"]["investigator"] == {"model": "google_genai:gemini-3-pro", "live": False}
        assert h["models"]["chat"] == {"model": "anthropic:claude-sonnet-5-5", "live": True}
        assert h["models"]["labels"]["model"] == "anthropic:claude-haiku-5-5"
        assert "sk-secret-test" not in str(h)
        assert chat_api.ChatService.live() is True
        cfg = appmod._llm_config({"analysis_mode": "live", "uploads": [{"sha256": "x"}]}, Path("/tmp/case"))
        assert cfg["model"] == "google_genai:gemini-3-pro" and cfg["vision_model"] == "google_genai:gemini-3-pro"
        r = client.post("/upload", data={"analysis_mode": "live"}, files={"file": ("a.zip", b"PK", "application/zip")})
        assert r.status_code == 400 and r.json()["error"]["code"] == "needs_api_key"
        assert "GOOGLE_API_KEY" in r.json()["error"]["message"]
        clean_env.setenv("GOOGLE_API_KEY", "g-test")
        assert client.get("/health").json()["llmLive"] is True
    finally:
        for name in ("MAPLETRACE_INVESTIGATOR_MODEL", "MAPLETRACE_CHAT_MODEL", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY"):
            clean_env.delenv(name, raising=False)
        importlib.reload(chat_api)
        importlib.reload(appmod)
