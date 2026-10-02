"""Tests for configuration loading, overriding, and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from syslog_triage.config import (
    API_KEY_ENV_VAR,
    ENV_OVERRIDES,
    ConfigError,
    load_config,
)


def write_config(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "config.toml"
    path.write_text(body, encoding="utf-8")
    return path


def test_defaults_without_file_or_env() -> None:
    config = load_config(path=None, env={})

    assert config.jev.api_key is None
    assert config.jev.timeout_seconds == 10.0
    assert config.jev.max_retries == 3
    assert config.jev.max_concurrency == 8
    assert config.journal.units == ()
    assert config.journal.max_priority == 6
    assert config.journal.since is None
    assert config.thresholds.min_confidence == 0.75
    assert config.thresholds.noise_confidence == 0.90
    assert config.thresholds.alert_severity == 0.60
    assert config.sinks.stdout.enabled is True
    assert config.sinks.slack.enabled is False
    assert config.sinks.sqlite.enabled is False


def test_missing_file_is_tolerated_unless_required(tmp_path: Path) -> None:
    missing = tmp_path / "absent.toml"

    assert load_config(missing, env={}).journal.max_priority == 6

    with pytest.raises(ConfigError, match="config file not found"):
        load_config(missing, env={}, required=True)


def test_reference_config_matches_the_built_in_defaults() -> None:
    """The committed config.toml documents defaults; it must not drift from them."""
    reference = load_config(Path(__file__).parent.parent / "config.toml", env={})

    assert reference == load_config(path=None, env={})


def test_file_values_are_read(tmp_path: Path) -> None:
    path = write_config(
        tmp_path,
        """
        [jev]
        timeout_seconds = 2.5
        max_concurrency = 1

        [journal]
        units = ["sshd.service", "nginx.service"]
        max_priority = 4
        since = "-1h"
        cursor_path = "state/cursor"

        [thresholds]
        min_confidence = 0.5

        [sinks.sqlite]
        enabled = true
        path = "out/decisions.db"
        """,
    )

    config = load_config(path, env={})

    assert config.jev.timeout_seconds == 2.5
    assert config.jev.max_concurrency == 1
    assert config.journal.units == ("sshd.service", "nginx.service")
    assert config.journal.max_priority == 4
    assert config.journal.since == "-1h"
    assert config.journal.cursor_path == Path("state/cursor")
    assert config.thresholds.min_confidence == 0.5
    assert config.sinks.sqlite.enabled is True
    assert config.sinks.sqlite.path == Path("out/decisions.db")


def test_env_overrides_beat_the_file(tmp_path: Path) -> None:
    path = write_config(
        tmp_path,
        """
        [journal]
        units = ["from-file.service"]
        max_priority = 4
        """,
    )

    config = load_config(
        path,
        env={
            "SYSLOG_TRIAGE_JOURNAL_UNITS": "from-env.service, other.service",
            "SYSLOG_TRIAGE_JOURNAL_MAX_PRIORITY": "3",
        },
    )

    assert config.journal.units == ("from-env.service", "other.service")
    assert config.journal.max_priority == 3


@pytest.mark.parametrize(
    ("variable", "raw", "dotted", "expected"),
    [
        (API_KEY_ENV_VAR, "sk-test", "jev.api_key", "sk-test"),
        ("SYSLOG_TRIAGE_JEV_TIMEOUT_SECONDS", "1.5", "jev.timeout_seconds", 1.5),
        ("SYSLOG_TRIAGE_JEV_MAX_RETRIES", "7", "jev.max_retries", 7),
        ("SYSLOG_TRIAGE_JEV_MAX_CONCURRENCY", "2", "jev.max_concurrency", 2),
        ("SYSLOG_TRIAGE_JOURNAL_UNITS", "a.service", "journal.units", ("a.service",)),
        ("SYSLOG_TRIAGE_JOURNAL_MAX_PRIORITY", "3", "journal.max_priority", 3),
        ("SYSLOG_TRIAGE_JOURNAL_SINCE", "-30m", "journal.since", "-30m"),
        (
            "SYSLOG_TRIAGE_JOURNAL_CURSOR_PATH",
            "run/cursor",
            "journal.cursor_path",
            Path("run/cursor"),
        ),
        ("SYSLOG_TRIAGE_THRESHOLDS_MIN_CONFIDENCE", "0.9", "thresholds.min_confidence", 0.9),
        ("SYSLOG_TRIAGE_THRESHOLDS_NOISE_CONFIDENCE", "0.95", "thresholds.noise_confidence", 0.95),
        ("SYSLOG_TRIAGE_THRESHOLDS_ALERT_SEVERITY", "0.4", "thresholds.alert_severity", 0.4),
        ("SYSLOG_TRIAGE_SINKS_STDOUT_ENABLED", "false", "sinks.stdout.enabled", False),
        (
            "SYSLOG_TRIAGE_SINKS_SLACK_WEBHOOK_URL",
            "https://h.example",
            "sinks.slack.webhook_url",
            "https://h.example",
        ),
        ("SYSLOG_TRIAGE_SINKS_SQLITE_ENABLED", "yes", "sinks.sqlite.enabled", True),
        ("SYSLOG_TRIAGE_SINKS_SQLITE_PATH", "out.db", "sinks.sqlite.path", Path("out.db")),
    ],
)
def test_every_env_override_reaches_its_field(
    variable: str, raw: str, dotted: str, expected: object
) -> None:
    """Each entry in ENV_OVERRIDES must actually land on the field it names."""
    config = load_config(path=None, env={variable: raw})

    value: object = config
    for part in dotted.split("."):
        value = getattr(value, part)
    assert value == expected


def test_env_override_table_covers_every_documented_variable() -> None:
    assert set(ENV_OVERRIDES) == {
        API_KEY_ENV_VAR,
        "SYSLOG_TRIAGE_JEV_TIMEOUT_SECONDS",
        "SYSLOG_TRIAGE_JEV_MAX_RETRIES",
        "SYSLOG_TRIAGE_JEV_MAX_CONCURRENCY",
        "SYSLOG_TRIAGE_JOURNAL_UNITS",
        "SYSLOG_TRIAGE_JOURNAL_MAX_PRIORITY",
        "SYSLOG_TRIAGE_JOURNAL_SINCE",
        "SYSLOG_TRIAGE_JOURNAL_CURSOR_PATH",
        "SYSLOG_TRIAGE_THRESHOLDS_MIN_CONFIDENCE",
        "SYSLOG_TRIAGE_THRESHOLDS_NOISE_CONFIDENCE",
        "SYSLOG_TRIAGE_THRESHOLDS_ALERT_SEVERITY",
        "SYSLOG_TRIAGE_SINKS_STDOUT_ENABLED",
        "SYSLOG_TRIAGE_SINKS_SLACK_ENABLED",
        "SYSLOG_TRIAGE_SINKS_SLACK_WEBHOOK_URL",
        "SYSLOG_TRIAGE_SINKS_SQLITE_ENABLED",
        "SYSLOG_TRIAGE_SINKS_SQLITE_PATH",
    }


def test_api_key_comes_from_the_environment_only(tmp_path: Path) -> None:
    path = write_config(tmp_path, '[jev]\napi_key = "sk-leaked"\n')

    with pytest.raises(ConfigError, match=f"read from \\${API_KEY_ENV_VAR} only"):
        load_config(path, env={})

    assert load_config(path=None, env={API_KEY_ENV_VAR: "sk-env"}).jev.api_key == "sk-env"


def test_slack_sink_requires_a_webhook_when_enabled() -> None:
    with pytest.raises(ConfigError, match="webhook_url is required"):
        load_config(path=None, env={"SYSLOG_TRIAGE_SINKS_SLACK_ENABLED": "true"})

    config = load_config(
        path=None,
        env={
            "SYSLOG_TRIAGE_SINKS_SLACK_ENABLED": "true",
            "SYSLOG_TRIAGE_SINKS_SLACK_WEBHOOK_URL": "https://hooks.example/abc",
        },
    )
    assert config.sinks.slack.webhook_url == "https://hooks.example/abc"


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("[jev]\ntimeout_secondss = 1\n", "unknown key"),
        ('[journal]\nunit = ["a"]\n', "unknown key"),
        ('[sinks.slack]\nurl = "x"\n', "unknown key"),
        ("[typo]\nkey = 1\n", "unknown key"),
        ("[jev]\ntimeout_seconds = 0\n", "positive number"),
        ("[jev]\nmax_retries = -1\n", "zero or more"),
        ("[jev]\nmax_concurrency = 0\n", "one or more"),
        ("[journal]\nmax_priority = 9\n", "expected 0-7"),
        ("[thresholds]\nmin_confidence = 1.5\n", "between 0 and 1"),
        ('[thresholds]\nmin_confidence = "high"\n', "expected a number"),
        ("[journal]\nmax_priority = true\n", "expected an integer"),
        ('[sinks.stdout]\nenabled = "sometimes"\n', "expected a boolean"),
        ('jev = "not-a-table"\n', "expected a table"),
        ("[jev\n", "invalid TOML"),
    ],
)
def test_bad_configuration_is_rejected_with_a_pointed_message(
    tmp_path: Path, body: str, message: str
) -> None:
    path = write_config(tmp_path, body)

    with pytest.raises(ConfigError, match=message):
        load_config(path, env={})


def test_redacted_dict_never_contains_the_key() -> None:
    config = load_config(path=None, env={API_KEY_ENV_VAR: "sk-secret"})

    redacted = config.to_redacted_dict()

    assert redacted["jev"]["api_key_set"] is True
    assert "sk-secret" not in repr(redacted)
