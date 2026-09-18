"""Tests for the command line interface."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import syslog_triage
from syslog_triage.cli import EXIT_CONFIG_ERROR, EXIT_NOT_IMPLEMENTED, build_parser, main


def test_help_exits_zero_with_no_api_key_set(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The acceptance criterion for the scaffold: usage without credentials."""
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)

    with pytest.raises(SystemExit) as exit_info:
        main(["--help"])

    assert exit_info.value.code == 0
    out = capsys.readouterr().out
    assert out.startswith("usage: syslog-triage")
    assert "--config" in out
    assert "config" in out
    assert "run" in out


def test_version_is_reported(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])

    assert exit_info.value.code == 0
    assert syslog_triage.__version__ in capsys.readouterr().out


def test_no_command_prints_usage_and_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    assert capsys.readouterr().out.startswith("usage: syslog-triage")


def test_config_command_prints_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    config_file = tmp_path / "config.toml"
    config_file.write_text('[journal]\nunits = ["sshd.service"]\n', encoding="utf-8")

    assert main(["--config", str(config_file), "config"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["journal"]["units"] == ["sshd.service"]
    assert payload["jev"]["api_key_set"] is False


def test_config_command_redacts_the_api_key(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("TYPESAFE_API_KEY", "sk-secret")

    assert main(["--config", str(tmp_path / "absent.toml"), "config"]) == 0

    out = capsys.readouterr().out
    assert "sk-secret" not in out
    assert json.loads(out)["jev"]["api_key_set"] is True


def test_invalid_config_reports_the_problem_and_exits_two(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text("[journal]\nmax_priority = 99\n", encoding="utf-8")

    assert main(["--config", str(config_file), "config"]) == EXIT_CONFIG_ERROR

    assert "max_priority" in capsys.readouterr().err


def test_run_without_an_api_key_stops_before_doing_work(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)

    assert main(["--config", str(tmp_path / "absent.toml"), "run"]) == EXIT_CONFIG_ERROR

    assert "TYPESAFE_API_KEY" in capsys.readouterr().err


def test_run_with_an_api_key_reports_the_pipeline_is_not_wired_up(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TYPESAFE_API_KEY", "sk-test")

    assert main(["--config", str(tmp_path / "absent.toml"), "run"]) == EXIT_NOT_IMPLEMENTED

    assert "not implemented yet" in capsys.readouterr().err


def test_parser_rejects_an_unknown_command() -> None:
    with pytest.raises(SystemExit) as exit_info:
        build_parser().parse_args(["nonsense"])

    assert exit_info.value.code != 0
