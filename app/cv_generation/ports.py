"""Ports (interfaces) for the CV generation domain."""

from typing import Protocol

from app.infrastructure.llm.client import LLMResult


class LLMPort(Protocol):
    """Abstract interface for LLM text generation."""

    async def generate(self, prompt: str) -> LLMResult:
        """Send a prompt and return the response with usage metadata."""
        ...
