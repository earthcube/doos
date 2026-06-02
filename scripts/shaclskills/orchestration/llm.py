"""Shared LLM client for the LLM-driven stages (1, 4, 5, 6).

Access model = OpenRouter via LangChain (PLAN.md §0a.2). OpenRouter is
OpenAI-compatible, so we use ``langchain_openai.ChatOpenAI`` pointed at the
OpenRouter base URL. Provider/model is env-driven and swappable:

    OPENROUTER_API_KEY   required to make any call
    OPENROUTER_MODEL     model slug (default below; PLAN.md §8 open item)

Stages import ``llm_available()`` and gate on it so they degrade gracefully to
deterministic behaviour when no key is configured (no network dependency for
the deterministic parts of a stage or for CI).
"""

from __future__ import annotations

import os

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
# Default model — override with $OPENROUTER_MODEL. Pin this in pyproject/docs
# once chosen (PLAN.md §8).
DEFAULT_MODEL = os.environ.get("OPENROUTER_MODEL", "anthropic/claude-3.5-sonnet")


def llm_available() -> bool:
    """True iff an OpenRouter key is configured (so a call can be made)."""
    return bool(os.environ.get("OPENROUTER_API_KEY"))


def get_chat_model(model: str | None = None, temperature: float = 0.0, **kwargs):
    """Construct a ChatOpenAI client bound to OpenRouter.

    Raises RuntimeError if no API key is set. ``langchain_openai`` is imported
    lazily so this module is importable even when the dep/key are absent.
    """
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set — cannot construct the LLM client."
        )
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=api_key,
        model=model or DEFAULT_MODEL,
        temperature=temperature,
        **kwargs,
    )


def complete(
    system: str, user: str, model: str | None = None, temperature: float = 0.0
) -> str:
    """One-shot system+user completion; returns the assistant text."""
    from langchain_core.messages import HumanMessage, SystemMessage

    chat = get_chat_model(model=model, temperature=temperature)
    resp = chat.invoke([SystemMessage(content=system), HumanMessage(content=user)])
    return resp.content if isinstance(resp.content, str) else str(resp.content)
