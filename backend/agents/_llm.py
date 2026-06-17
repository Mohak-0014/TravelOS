"""Shared LLM factory — returns a ChatGroq instance sized for the task."""

from __future__ import annotations

from langchain_groq import ChatGroq

from backend.core.config import settings

_LARGE_MODEL = "llama-3.3-70b-versatile"
_SMALL_MODEL = "llama-3.1-8b-instant"
# Fine-tuned on function-calling datasets — more reliable tool invocation than versatile
_TOOL_USE_MODEL = "llama3-groq-70b-8192-tool-use-preview"


def build_llm(size: str = "large", temperature: float = 0.0) -> ChatGroq:
    """Return a ChatGroq client.

    size="large"  → llama-3.3-70b-versatile  (complex reasoning, tool-calling)
    size="small"  → llama-3.1-8b-instant     (fast classification / ranking)
    size="tools"  → llama3-groq-70b-8192-tool-use-preview  (tool-use fine-tuned)
    """
    if size == "tools":
        model = _TOOL_USE_MODEL
    elif size == "large":
        model = _LARGE_MODEL
    else:
        model = _SMALL_MODEL
    return ChatGroq(
        api_key=settings.GROQ_API_KEY,  # type: ignore[arg-type]
        model=model,
        temperature=temperature,
    )
