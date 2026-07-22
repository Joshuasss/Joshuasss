"""Tests for the minimal LLM seam (offline, no network)."""

from core.llm import DeterministicLLM, LLMProvider


def test_deterministic_llm_satisfies_protocol():
    assert isinstance(DeterministicLLM(), LLMProvider)


def test_deterministic_llm_returns_canned_reply():
    assert DeterministicLLM(reply="hello").complete("anything") == "hello"


def test_deterministic_llm_default_is_derived_and_offline():
    out = DeterministicLLM().complete("summarize this please")
    assert out.startswith("[deterministic-llm]")
