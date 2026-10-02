"""Command line interface for the triage daemon.

Two commands exist today:

``config``
    Resolve the configuration and print it, with the API key redacted. Useful
    for confirming what a machine will actually run with.

``run``
    Start the daemon. The pipeline stages it drives — journal reader, Jev
    client, routing, sinks — arrive in later issues, so for now it validates
    configuration and reports what is still missing.

Parsing never touches configuration, so ``--help`` and ``--version`` work on a
machine with no API key and no ``config.toml``.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from syslog_triage import __version__
from syslog_triage.config import API_KEY_ENV_VAR, DEFAULT_CONFIG_PATH, ConfigError, load_config

__all__ = ["build_parser", "main"]

_LOG_LEVELS = ("debug", "info", "warning", "error", "critical")

#: Exit status for a configuration that could not be loaded.
EXIT_CONFIG_ERROR = 2
#: Exit status for a command whose implementation has not landed yet.
EXIT_NOT_IMPLEMENTED = 1

_LOGGER = logging.getLogger("syslog_triage")


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser.

    >>> build_parser().prog
    'syslog-triage'
    """
    parser = argparse.ArgumentParser(
        prog="syslog-triage",
        description=(
            "Tail the journal, ask Jev what each event is, and drop, record, "
            "alert on, or escalate it based on how confident the answer is."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        metavar="PATH",
        help=(
            f"TOML configuration file (default: {DEFAULT_CONFIG_PATH}). "
            "Missing files are tolerated; built-in defaults are used instead."
        ),
    )
    parser.add_argument(
        "--log-level",
        choices=_LOG_LEVELS,
        default="info",
        help="Logging verbosity (default: info).",
    )

    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    subparsers.add_parser(
        "config",
        help="Print the resolved configuration as JSON and exit.",
        description=(
            "Resolve the configuration file and environment overrides, then "
            f"print the result as JSON. ${API_KEY_ENV_VAR} is reported as a "
            "boolean, never echoed."
        ),
    )
    subparsers.add_parser(
        "run",
        help="Run the triage daemon.",
        description="Validate configuration and start the triage daemon.",
    )
    return parser


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stderr,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit status.

    ``--help`` and ``--version`` are handled by argparse, which exits 0 before
    any configuration is read.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    _configure_logging(args.log_level)

    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(f"syslog-triage: {exc}", file=sys.stderr)
        return EXIT_CONFIG_ERROR

    if args.command == "config":
        json.dump(config.to_redacted_dict(), sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 0

    # args.command == "run"
    if config.jev.api_key is None:
        print(
            f"syslog-triage: ${API_KEY_ENV_VAR} is not set; export it to reach Jev.",
            file=sys.stderr,
        )
        return EXIT_CONFIG_ERROR

    _LOGGER.info("configuration loaded; the triage pipeline is not wired up yet")
    print(
        "syslog-triage: configuration is valid, but the pipeline is not implemented yet.\n"
        "Journal reader, Jev client, routing, and sinks land in later issues; "
        "run 'syslog-triage config' to inspect what is configured so far.",
        file=sys.stderr,
    )
    return EXIT_NOT_IMPLEMENTED
