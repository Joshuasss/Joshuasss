"""Minimal LLM provider seam.

Defines the single interface agents will use when they need model reasoning,
plus an offline deterministic implementation for tests and local runs. This is
intentionally tiny: no Anthropic client is constructed here yet and no network
call is made. `momentum_agent` v1 does not use an LLM at all — its analysis is
deterministic math — but the seam is defined so later agents plug in one way.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    """The contract any LLM backend must satisfy."""

    def complete(self, prompt: str, *, system: str | None = None) -> str: ...


class DeterministicLLM:
    """Offline, no-network provider that echoes a canned/derived response.

    Used so code paths that expect an `LLMProvider` can be exercised in tests
    without external calls. Not a real model — it performs no reasoning.
    """

    def __init__(self, reply: str = "") -> None:
        self._reply = reply

    def complete(self, prompt: str, *, system: str | None = None) -> str:
        return self._reply or f"[deterministic-llm] {prompt.strip()[:80]}"
