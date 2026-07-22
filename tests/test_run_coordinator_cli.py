"""Lightweight tests for the coordinator CLI runner path."""

import json

import pytest

from core.enums import AgentGroup, Status
from core.schemas import CoordinatorResult
from scripts.run_coordinator import main, run_coordinator


def test_run_coordinator_helper_returns_result():
    result = run_coordinator("short_term", "UPTREND")
    assert isinstance(result, CoordinatorResult)
    assert result.group is AgentGroup.SHORT_TERM
    assert result.status is Status.SUCCESS


def test_run_coordinator_unknown_group_raises():
    with pytest.raises(ValueError):
        run_coordinator("does_not_exist", "AAPL")


def test_main_prints_valid_json_and_exits_zero(capsys):
    code = main(["--group", "short_term", "--ticker", "AAPL"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["group"] == "SHORT_TERM"
    assert "signal" in payload and "member_outputs" in payload


def test_main_surfaces_agent_failure_inside_result(capsys):
    # Unknown ticker fails the agent, but the coordinator captures it in the
    # result (status FAILED) rather than raising -> CLI still exits 0.
    code = main(["--group", "short_term", "--ticker", "ZZZ"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "FAILED"
    assert payload["errors"] and payload["errors"][0]["code"] == "AGENT_FAILED"
