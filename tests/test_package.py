"""Smoke tests for the package surface."""

from __future__ import annotations

import subprocess
import sys

import syslog_triage


def test_package_exposes_a_version_and_the_config_entry_points() -> None:
    assert syslog_triage.__version__ == "0.1.0"
    assert set(syslog_triage.__all__) == {"Config", "ConfigError", "__version__", "load_config"}


def test_module_entry_point_prints_usage() -> None:
    """``python -m syslog_triage --help`` works without credentials."""
    result = subprocess.run(
        [sys.executable, "-m", "syslog_triage", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout.startswith("usage: syslog-triage")


def test_docstring_examples_still_hold() -> None:
    """Doc examples are part of the contract, so run them rather than trust them."""
    import doctest

    from syslog_triage import cli, config

    for module in (cli, config):
        results = doctest.testmod(module, verbose=False)
        assert results.failed == 0, f"{module.__name__}: {results.failed} doctest failure(s)"
