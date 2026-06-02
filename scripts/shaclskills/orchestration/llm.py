"""Shared LLM client for the LLM-driven stages (1, 4, 5, 6).

Access model = **any OpenAI-compatible chat API** via LangChain's
``langchain_openai.ChatOpenAI``. The provider is chosen entirely by three
environment variables, so swapping OpenRouter for native OpenAI, a hosted
provider (Together, Fireworks, Groq, ...), a corporate gateway, or a local
server (vLLM / Ollama / LM Studio) is config-only — no code change:

    LLM_API_KEY    required to make any call
    LLM_BASE_URL   OpenAI-compatible endpoint (default: OpenRouter)
    LLM_MODEL      model slug (provider-specific; default below)

Backward compatibility: the legacy ``OPENROUTER_*`` variables are still
honoured as fallbacks, so existing setups keep working unchanged.

Stages import ``llm_available()`` and gate on it so they degrade gracefully to
deterministic behaviour when no key is configured (no network dependency for
the deterministic parts of a stage or for CI).
"""

from __future__ import annotations

import os
import re

# Default endpoint when LLM_BASE_URL / OPENROUTER_BASE_URL are unset. OpenRouter
# is OpenAI-compatible; point LLM_BASE_URL elsewhere for any other provider.
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
# Default model — override with $LLM_MODEL. Slug format is provider-specific
# (OpenRouter: "vendor/model"; native OpenAI: "gpt-4o"; local: whatever you serve).
DEFAULT_MODEL = "anthropic/claude-3.5-sonnet"
# Per-request timeout (seconds) and retry cap. A bounded call can never hang the
# pipeline — critical for reasoning models (e.g. qwen3) that emit long <think>
# traces. Override with $LLM_TIMEOUT / $LLM_MAX_RETRIES / $LLM_MAX_TOKENS.
DEFAULT_TIMEOUT = 120.0
DEFAULT_MAX_RETRIES = 1

# Strips inline reasoning traces some models (qwen3, deepseek-r1, …) prepend to
# the answer, so downstream JSON parsing sees only the real content.
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def _api_key() -> str | None:
    """The configured API key (generic var first, legacy OpenRouter fallback)."""
    return os.environ.get("LLM_API_KEY") or os.environ.get("OPENROUTER_API_KEY")


def _base_url() -> str:
    """The OpenAI-compatible endpoint (generic var first, legacy fallback)."""
    return (
        os.environ.get("LLM_BASE_URL")
        or os.environ.get("OPENROUTER_BASE_URL")
        or DEFAULT_BASE_URL
    )


def _model() -> str:
    """The model slug (generic var first, legacy fallback, then default)."""
    return (
        os.environ.get("LLM_MODEL")
        or os.environ.get("OPENROUTER_MODEL")
        or DEFAULT_MODEL
    )


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.environ[name])
    except (KeyError, ValueError):
        return default


def _int_env(name: str, default: int | None) -> int | None:
    try:
        return int(os.environ[name])
    except (KeyError, ValueError):
        return default


def _bool_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _thinking_extra_body() -> dict:
    """Request body to disable a reasoning model's <think> phase, when asked.

    Set ``LLM_DISABLE_THINKING=1`` for models like qwen3 / deepseek-r1 that
    otherwise burn the whole timeout on reasoning (qwen3: ~40s vs ~1.5s for a
    one-word reply). Uses the vLLM/SGLang convention
    ``chat_template_kwargs.enable_thinking=False``; harmless on providers that
    ignore unknown body keys.
    """
    if not _bool_env("LLM_DISABLE_THINKING"):
        return {}
    return {"chat_template_kwargs": {"enable_thinking": False}}


def llm_available() -> bool:
    """True iff an API key is configured (so a call can be made)."""
    return bool(_api_key())


def get_chat_model(model: str | None = None, temperature: float = 0.0, **kwargs):
    """Construct a ChatOpenAI client bound to the configured endpoint.

    Raises RuntimeError if no API key is set. ``langchain_openai`` is imported
    lazily so this module is importable even when the dep/key are absent.
    """
    api_key = _api_key()
    if not api_key:
        raise RuntimeError(
            "No LLM API key set (LLM_API_KEY or OPENROUTER_API_KEY) — "
            "cannot construct the LLM client."
        )
    from langchain_openai import ChatOpenAI

    # A bounded request (timeout + capped retries) can never hang the pipeline;
    # explicit kwargs from callers (e.g. the cheap check_llm probe) still win.
    params: dict = {
        "base_url": _base_url(),
        "api_key": api_key,
        "model": model or _model(),
        "temperature": temperature,
        "timeout": _float_env("LLM_TIMEOUT", DEFAULT_TIMEOUT),
        "max_retries": _int_env("LLM_MAX_RETRIES", DEFAULT_MAX_RETRIES),
    }
    max_tokens = _int_env("LLM_MAX_TOKENS", None)
    if max_tokens is not None:
        params["max_tokens"] = max_tokens
    extra_body = _thinking_extra_body()
    if extra_body:
        params["extra_body"] = extra_body
    params.update(kwargs)
    return ChatOpenAI(**params)


def strip_reasoning(text: str) -> str:
    """Remove inline <think>…</think> reasoning traces and surrounding blanks."""
    return _THINK_RE.sub("", text).strip()


def complete(
    system: str, user: str, model: str | None = None, temperature: float = 0.0
) -> str:
    """One-shot system+user completion; returns the assistant text.

    The call is bounded by ``LLM_TIMEOUT`` (default 120s) so a slow/looping
    model raises instead of hanging. Inline ``<think>`` reasoning traces are
    stripped so callers that parse JSON see only the answer.
    """
    from langchain_core.messages import HumanMessage, SystemMessage

    chat = get_chat_model(model=model, temperature=temperature)
    resp = chat.invoke([SystemMessage(content=system), HumanMessage(content=user)])
    content = resp.content if isinstance(resp.content, str) else str(resp.content)
    return strip_reasoning(content)


def describe_config() -> str:
    """Human-readable summary of the active LLM target (no secrets)."""
    return f"{_model()} @ {_base_url()}"


def check_llm() -> tuple[bool, str]:
    """Probe the configured LLM with a tiny real completion.

    Returns ``(ok, detail)``. Unlike ``llm_available()`` (which only checks that
    a key string is set), this makes one cheap round-trip that actually exercises
    the key, base URL, model slug, and network — so misconfiguration surfaces
    instead of being silently swallowed by the per-stage fallbacks.

    - ``(False, "no API key set")``     — nothing configured (intended off).
    - ``(True,  "<model> @ <url>")``    — a call succeeded; LLM is usable.
    - ``(False, "<error> ...")``        — configured but the call failed
                                          (bad key, unreachable URL, bad model).
    """
    if not llm_available():
        return False, "no API key set (LLM_API_KEY / OPENROUTER_API_KEY)"
    target = describe_config()
    try:
        # Cheap + fast: cap tokens, short timeout, no retries so a dead endpoint
        # fails the probe in seconds rather than the full request timeout.
        probe_timeout = _float_env("LLM_PROBE_TIMEOUT", 20.0)
        chat = get_chat_model(max_tokens=1, timeout=probe_timeout, max_retries=0)
        chat.invoke("ping")
        return True, target
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {e} (target: {target})"
