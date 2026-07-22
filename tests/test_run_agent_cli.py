"""Lightweight tests for the CLI runner path."""

import json
from datetime import datetime, timezone

import pytest

from core.enums import AgentName, Signal
from core.schemas import AgentOutput
from scripts.run_agent import main, run_agent


def test_run_agent_helper_returns_output():
    out = run_agent("momentum", "UPTREND")
    assert isinstance(out, AgentOutput)
    assert out.agent_name is AgentName.MOMENTUM_AGENT
    assert out.signal in (Signal.BUY, Signal.STRONG_BUY)


def test_run_agent_unknown_agent_raises():
    with pytest.raises(ValueError):
        run_agent("nope", "AAPL")


def test_main_prints_valid_json_and_exits_zero(capsys):
    code = main(["--agent", "momentum", "--ticker", "AAPL"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["agent_name"] == "momentum_agent"
    assert payload["ticker"] == "AAPL"
    assert "signal" in payload and "confidence" in payload


def test_main_reports_unknown_ticker_as_error(capsys):
    code = main(["--agent", "momentum", "--ticker", "ZZZ"])
    assert code == 1
    assert "error:" in capsys.readouterr().err


def test_main_respects_as_of(capsys):
    # An early cutoff yields limited history -> PARTIAL status in the JSON.
    code = main(["--agent", "momentum", "--ticker", "UPTREND", "--as-of", "2025-12-04"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "PARTIAL"
