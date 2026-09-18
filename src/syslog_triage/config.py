"""Configuration for the triage daemon.

Settings come from two places, in increasing order of precedence:

1. A TOML file — ``config.toml`` in the working directory by default.
2. Environment variables.

The Jev API key is the one setting that is *only* ever read from the
environment (``TYPESAFE_API_KEY``), so a checked-in ``config.toml`` can never
leak a credential. Every other key has an ``SYSLOG_TRIAGE_<SECTION>_<KEY>``
environment override; see :data:`ENV_OVERRIDES`.

Unknown keys are an error rather than a silent no-op, so a typo in
``config.toml`` fails loudly instead of quietly running with a default.

>>> cfg = load_config(path=None, env={"TYPESAFE_API_KEY": "sk-test"})
>>> cfg.jev.api_key
'sk-test'
>>> cfg.thresholds.min_confidence
0.75
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "API_KEY_ENV_VAR",
    "DEFAULT_CONFIG_PATH",
    "ENV_OVERRIDES",
    "Config",
    "ConfigError",
    "JevConfig",
    "JournalConfig",
    "SinksConfig",
    "SlackSinkConfig",
    "SqliteSinkConfig",
    "StdoutSinkConfig",
    "ThresholdsConfig",
    "load_config",
]

#: Where the daemon looks for its TOML file when ``--config`` is not given.
DEFAULT_CONFIG_PATH = Path("config.toml")

#: The environment variable holding the Jev API key. Never read from TOML.
API_KEY_ENV_VAR = "TYPESAFE_API_KEY"

#: Environment variable -> dotted config path. Values arrive as strings and are
#: coerced by the same parsers that handle TOML-native values.
ENV_OVERRIDES: Mapping[str, str] = {
    API_KEY_ENV_VAR: "jev.api_key",
    "SYSLOG_TRIAGE_JEV_TIMEOUT_SECONDS": "jev.timeout_seconds",
    "SYSLOG_TRIAGE_JEV_MAX_RETRIES": "jev.max_retries",
    "SYSLOG_TRIAGE_JEV_MAX_CONCURRENCY": "jev.max_concurrency",
    "SYSLOG_TRIAGE_JOURNAL_UNITS": "journal.units",
    "SYSLOG_TRIAGE_JOURNAL_MAX_PRIORITY": "journal.max_priority",
    "SYSLOG_TRIAGE_JOURNAL_SINCE": "journal.since",
    "SYSLOG_TRIAGE_JOURNAL_CURSOR_PATH": "journal.cursor_path",
    "SYSLOG_TRIAGE_THRESHOLDS_MIN_CONFIDENCE": "thresholds.min_confidence",
    "SYSLOG_TRIAGE_THRESHOLDS_NOISE_CONFIDENCE": "thresholds.noise_confidence",
    "SYSLOG_TRIAGE_THRESHOLDS_ALERT_SEVERITY": "thresholds.alert_severity",
    "SYSLOG_TRIAGE_SINKS_STDOUT_ENABLED": "sinks.stdout.enabled",
    "SYSLOG_TRIAGE_SINKS_SLACK_ENABLED": "sinks.slack.enabled",
    "SYSLOG_TRIAGE_SINKS_SLACK_WEBHOOK_URL": "sinks.slack.webhook_url",
    "SYSLOG_TRIAGE_SINKS_SQLITE_ENABLED": "sinks.sqlite.enabled",
    "SYSLOG_TRIAGE_SINKS_SQLITE_PATH": "sinks.sqlite.path",
}


class ConfigError(Exception):
    """Raised when configuration is missing, malformed, or out of range."""


@dataclass(frozen=True, slots=True)
class JevConfig:
    """How the daemon talks to Jev.

    ``api_key`` is ``None`` until :data:`API_KEY_ENV_VAR` is exported; loading a
    config without it succeeds so that ``--help`` and config inspection work on
    a machine with no credentials.
    """

    api_key: str | None = None
    timeout_seconds: float = 10.0
    max_retries: int = 3
    #: Ceiling on in-flight requests, so a log burst cannot fan out without bound.
    max_concurrency: int = 8


@dataclass(frozen=True, slots=True)
class JournalConfig:
    """Which journal entries are worth asking about.

    Filtering here rather than after the model call is deliberate: an entry that
    never matches is an entry never paid for.
    """

    #: Systemd units to follow. Empty means every unit.
    units: tuple[str, ...] = ()
    #: Highest syslog priority to keep, 0 (emerg) through 7 (debug).
    max_priority: int = 6
    #: Optional journalctl-style start point, e.g. ``"-1h"``. ``None`` tails.
    since: str | None = None
    #: Where the journal cursor is persisted so a restart resumes in place.
    cursor_path: Path = Path("var/cursor")


@dataclass(frozen=True, slots=True)
class ThresholdsConfig:
    """Confidence gates.

    The answer says *what* an event is; confidence says whether to act on it.
    Defaults are deliberately cautious — the daemon would rather wake a human
    than drop something it half-understood.
    """

    #: Any question answered below this confidence escalates, whatever it said.
    min_confidence: float = 0.75
    #: Confidence required before an event is dropped as routine noise.
    noise_confidence: float = 0.90
    #: Severity score at or above which an event alerts rather than records.
    alert_severity: float = 0.60


@dataclass(frozen=True, slots=True)
class StdoutSinkConfig:
    """JSON-per-line to stdout. On by default so the daemon is never silent."""

    enabled: bool = True


@dataclass(frozen=True, slots=True)
class SlackSinkConfig:
    """Slack webhook for events that alert or escalate."""

    enabled: bool = False
    webhook_url: str | None = None


@dataclass(frozen=True, slots=True)
class SqliteSinkConfig:
    """Every event and decision, kept for later review."""

    enabled: bool = False
    path: Path = Path("var/decisions.db")


@dataclass(frozen=True, slots=True)
class SinksConfig:
    """Where decisions go."""

    stdout: StdoutSinkConfig = field(default_factory=StdoutSinkConfig)
    slack: SlackSinkConfig = field(default_factory=SlackSinkConfig)
    sqlite: SqliteSinkConfig = field(default_factory=SqliteSinkConfig)


@dataclass(frozen=True, slots=True)
class Config:
    """The resolved configuration for one run of the daemon."""

    jev: JevConfig = field(default_factory=JevConfig)
    journal: JournalConfig = field(default_factory=JournalConfig)
    thresholds: ThresholdsConfig = field(default_factory=ThresholdsConfig)
    sinks: SinksConfig = field(default_factory=SinksConfig)

    def to_redacted_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable view with the API key replaced by a flag.

        >>> load_config(path=None, env={}).to_redacted_dict()["jev"]["api_key_set"]
        False
        """
        return {
            "jev": {
                "api_key_set": self.jev.api_key is not None,
                "timeout_seconds": self.jev.timeout_seconds,
                "max_retries": self.jev.max_retries,
                "max_concurrency": self.jev.max_concurrency,
            },
            "journal": {
                "units": list(self.journal.units),
                "max_priority": self.journal.max_priority,
                "since": self.journal.since,
                "cursor_path": str(self.journal.cursor_path),
            },
            "thresholds": {
                "min_confidence": self.thresholds.min_confidence,
                "noise_confidence": self.thresholds.noise_confidence,
                "alert_severity": self.thresholds.alert_severity,
            },
            "sinks": {
                "stdout": {"enabled": self.sinks.stdout.enabled},
                "slack": {
                    "enabled": self.sinks.slack.enabled,
                    "webhook_url_set": self.sinks.slack.webhook_url is not None,
                },
                "sqlite": {
                    "enabled": self.sinks.sqlite.enabled,
                    "path": str(self.sinks.sqlite.path),
                },
            },
        }


def _as_bool(raw: object, where: str) -> bool:
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        lowered = raw.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    raise ConfigError(f"{where}: expected a boolean, got {raw!r}")


def _as_int(raw: object, where: str) -> int:
    if isinstance(raw, bool):  # bool is an int subclass; reject it explicitly.
        raise ConfigError(f"{where}: expected an integer, got {raw!r}")
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str):
        try:
            return int(raw.strip())
        except ValueError as exc:
            raise ConfigError(f"{where}: expected an integer, got {raw!r}") from exc
    raise ConfigError(f"{where}: expected an integer, got {raw!r}")


def _as_float(raw: object, where: str) -> float:
    if isinstance(raw, bool):
        raise ConfigError(f"{where}: expected a number, got {raw!r}")
    if isinstance(raw, int | float):
        return float(raw)
    if isinstance(raw, str):
        try:
            return float(raw.strip())
        except ValueError as exc:
            raise ConfigError(f"{where}: expected a number, got {raw!r}") from exc
    raise ConfigError(f"{where}: expected a number, got {raw!r}")


def _as_str(raw: object, where: str) -> str:
    if isinstance(raw, str):
        return raw
    raise ConfigError(f"{where}: expected a string, got {raw!r}")


def _as_str_tuple(raw: object, where: str) -> tuple[str, ...]:
    """Accept a TOML array or a comma-separated string (how env vars arrive)."""
    if isinstance(raw, str):
        return tuple(item.strip() for item in raw.split(",") if item.strip())
    if isinstance(raw, list):
        return tuple(_as_str(item, where) for item in raw)
    raise ConfigError(f"{where}: expected a list of strings, got {raw!r}")


def _as_path(raw: object, where: str) -> Path:
    if isinstance(raw, Path):
        return raw
    return Path(_as_str(raw, where))


def _section(data: dict[str, Any], name: str) -> dict[str, Any]:
    """Pop a table from ``data``, erroring if the key holds a scalar instead."""
    value = data.pop(name, {})
    if not isinstance(value, dict):
        raise ConfigError(f"[{name}]: expected a table, got {value!r}")
    return value


def _reject_unknown(section: dict[str, Any], where: str) -> None:
    if section:
        unknown = ", ".join(sorted(section))
        raise ConfigError(f"{where}: unknown key(s): {unknown}")


def _in_unit_range(value: float, where: str) -> float:
    if not 0.0 <= value <= 1.0:
        raise ConfigError(f"{where}: expected a value between 0 and 1, got {value}")
    return value


def _assign(data: dict[str, Any], dotted: str, value: str) -> None:
    """Write ``value`` into the nested ``data`` at a dotted path."""
    *parents, leaf = dotted.split(".")
    cursor = data
    for part in parents:
        child = cursor.setdefault(part, {})
        if not isinstance(child, dict):
            raise ConfigError(f"[{part}]: expected a table, got {child!r}")
        cursor = child
    cursor[leaf] = value


def _apply_env(data: dict[str, Any], env: Mapping[str, str]) -> None:
    for var, dotted in ENV_OVERRIDES.items():
        value = env.get(var)
        if value is not None:
            _assign(data, dotted, value)


def _build_jev(data: dict[str, Any]) -> JevConfig:
    defaults = JevConfig()
    api_key = data.pop("api_key", None)
    timeout = data.pop("timeout_seconds", defaults.timeout_seconds)
    retries = data.pop("max_retries", defaults.max_retries)
    concurrency = data.pop("max_concurrency", defaults.max_concurrency)
    _reject_unknown(data, "[jev]")

    timeout_seconds = _as_float(timeout, "[jev].timeout_seconds")
    if timeout_seconds <= 0:
        raise ConfigError(
            f"[jev].timeout_seconds: expected a positive number, got {timeout_seconds}"
        )
    max_retries = _as_int(retries, "[jev].max_retries")
    if max_retries < 0:
        raise ConfigError(f"[jev].max_retries: expected zero or more, got {max_retries}")
    max_concurrency = _as_int(concurrency, "[jev].max_concurrency")
    if max_concurrency < 1:
        raise ConfigError(f"[jev].max_concurrency: expected one or more, got {max_concurrency}")

    return JevConfig(
        api_key=None if api_key is None else _as_str(api_key, f"${API_KEY_ENV_VAR}"),
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        max_concurrency=max_concurrency,
    )


def _build_journal(data: dict[str, Any]) -> JournalConfig:
    defaults = JournalConfig()
    units = data.pop("units", list(defaults.units))
    max_priority = data.pop("max_priority", defaults.max_priority)
    since = data.pop("since", defaults.since)
    cursor_path = data.pop("cursor_path", defaults.cursor_path)
    _reject_unknown(data, "[journal]")

    priority = _as_int(max_priority, "[journal].max_priority")
    if not 0 <= priority <= 7:
        raise ConfigError(f"[journal].max_priority: expected 0-7, got {priority}")

    return JournalConfig(
        units=_as_str_tuple(units, "[journal].units"),
        max_priority=priority,
        since=None if since is None else _as_str(since, "[journal].since") or None,
        cursor_path=_as_path(cursor_path, "[journal].cursor_path"),
    )


def _build_thresholds(data: dict[str, Any]) -> ThresholdsConfig:
    defaults = ThresholdsConfig()
    min_confidence = data.pop("min_confidence", defaults.min_confidence)
    noise_confidence = data.pop("noise_confidence", defaults.noise_confidence)
    alert_severity = data.pop("alert_severity", defaults.alert_severity)
    _reject_unknown(data, "[thresholds]")

    return ThresholdsConfig(
        min_confidence=_in_unit_range(
            _as_float(min_confidence, "[thresholds].min_confidence"),
            "[thresholds].min_confidence",
        ),
        noise_confidence=_in_unit_range(
            _as_float(noise_confidence, "[thresholds].noise_confidence"),
            "[thresholds].noise_confidence",
        ),
        alert_severity=_in_unit_range(
            _as_float(alert_severity, "[thresholds].alert_severity"),
            "[thresholds].alert_severity",
        ),
    )


def _build_sinks(data: dict[str, Any]) -> SinksConfig:
    stdout_data = _section(data, "stdout")
    slack_data = _section(data, "slack")
    sqlite_data = _section(data, "sqlite")
    _reject_unknown(data, "[sinks]")

    stdout_defaults = StdoutSinkConfig()
    stdout_enabled = stdout_data.pop("enabled", stdout_defaults.enabled)
    _reject_unknown(stdout_data, "[sinks.stdout]")

    slack_defaults = SlackSinkConfig()
    slack_enabled = slack_data.pop("enabled", slack_defaults.enabled)
    webhook_url = slack_data.pop("webhook_url", slack_defaults.webhook_url)
    _reject_unknown(slack_data, "[sinks.slack]")

    sqlite_defaults = SqliteSinkConfig()
    sqlite_enabled = sqlite_data.pop("enabled", sqlite_defaults.enabled)
    sqlite_path = sqlite_data.pop("path", sqlite_defaults.path)
    _reject_unknown(sqlite_data, "[sinks.sqlite]")

    slack = SlackSinkConfig(
        enabled=_as_bool(slack_enabled, "[sinks.slack].enabled"),
        webhook_url=(
            None
            if webhook_url is None
            else _as_str(webhook_url, "[sinks.slack].webhook_url") or None
        ),
    )
    if slack.enabled and slack.webhook_url is None:
        raise ConfigError("[sinks.slack]: webhook_url is required when the sink is enabled")

    return SinksConfig(
        stdout=StdoutSinkConfig(enabled=_as_bool(stdout_enabled, "[sinks.stdout].enabled")),
        slack=slack,
        sqlite=SqliteSinkConfig(
            enabled=_as_bool(sqlite_enabled, "[sinks.sqlite].enabled"),
            path=_as_path(sqlite_path, "[sinks.sqlite].path"),
        ),
    )


def load_config(
    path: Path | None = DEFAULT_CONFIG_PATH,
    *,
    env: Mapping[str, str] | None = None,
    required: bool = False,
) -> Config:
    """Load configuration from ``path``, then apply environment overrides.

    Args:
        path: TOML file to read. ``None`` skips the file entirely and uses
            defaults plus the environment.
        env: Environment mapping to read overrides from. Defaults to
            ``os.environ``.
        required: When true, a missing ``path`` is an error. The default is
            false so the daemon runs on defaults alone.

    Raises:
        ConfigError: the file is missing and ``required``, is not valid TOML,
            contains an unknown key, or holds a value of the wrong type or
            outside its permitted range.

    >>> load_config(path=None, env={"SYSLOG_TRIAGE_JOURNAL_UNITS": "sshd,nginx"}).journal.units
    ('sshd', 'nginx')
    """
    if env is None:
        import os

        env = os.environ

    data: dict[str, Any] = {}
    if path is not None:
        try:
            with path.open("rb") as handle:
                data = tomllib.load(handle)
        except FileNotFoundError:
            if required:
                raise ConfigError(f"config file not found: {path}") from None
        except tomllib.TOMLDecodeError as exc:
            raise ConfigError(f"{path}: invalid TOML: {exc}") from exc
        except OSError as exc:
            raise ConfigError(f"{path}: cannot be read: {exc}") from exc

    if "jev" in data and isinstance(data["jev"], dict) and "api_key" in data["jev"]:
        raise ConfigError(
            f"[jev].api_key: the API key is read from ${API_KEY_ENV_VAR} only, "
            "never from the config file"
        )

    _apply_env(data, env)

    jev = _build_jev(_section(data, "jev"))
    journal = _build_journal(_section(data, "journal"))
    thresholds = _build_thresholds(_section(data, "thresholds"))
    sinks = _build_sinks(_section(data, "sinks"))
    _reject_unknown(data, "config")

    return Config(jev=jev, journal=journal, thresholds=thresholds, sinks=sinks)
