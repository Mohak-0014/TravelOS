"""Shared LLM factory — returns a ChatGroq instance sized for the task."""

from __future__ import annotations

from langchain_groq import ChatGroq

from backend.core.config import settings

_LARGE_MODEL = "llama-3.3-70b-versatile"
_SMALL_MODEL = "llama-3.1-8b-instant"
# Fine-tuned on function-calling datasets — more reliable tool invocation than versatile
_TOOL_USE_MODEL = "llama3-groq-70b-8192-tool-use-preview"


def build_llm(
    size: str = "large",
    temperature: float = 0.0,
    max_tokens: int | None = None,
) -> ChatGroq:
    """Return a ChatGroq client.

    size="large"  → llama-3.3-70b-versatile  (complex reasoning, tool-calling)
    size="small"  → llama-3.1-8b-instant     (fast classification / ranking)
    size="tools"  → llama3-groq-70b-8192-tool-use-preview  (tool-use fine-tuned)

    max_tokens caps the completion length. Set it on agents that expect a
    bounded structured (JSON) response so the model can't run away and emit a
    truncated, unparseable payload.
    """
    if size == "tools":
        model = _TOOL_USE_MODEL
    elif size == "large":
        model = _LARGE_MODEL
    else:
        model = _SMALL_MODEL
    return ChatGroq(  # type: ignore[call-arg]
        api_key=settings.GROQ_API_KEY,  # type: ignore[arg-type]
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )
