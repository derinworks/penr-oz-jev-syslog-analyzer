# penr-oz-jev-syslog-analyzer

An asyncio daemon that tails journald or syslog and asks Jev, for each event, which subsystem it belongs to, how severe it is, and whether it's noise. Plain code then ignores the event, alerts on it, or escalates it to a human when confidence is low.

> **Status: scaffold.** Packaging, configuration, linting, typing, tests, and CI
> are in place. The pipeline stages — journal reader, Jev client, question set,
> routing, and sinks — land in the [open issues](https://github.com/derinworks/penr-oz-jev-syslog-analyzer/issues).
> `syslog-triage run` validates its configuration and then tells you as much.

## Requirements

- Python 3.11 or newer
- [uv](https://docs.astral.sh/uv/)

## Quick start

```sh
uv sync                       # create the environment
uv run syslog-triage --help   # usage; works with no API key set
uv run syslog-triage config   # print the resolved configuration as JSON
```

`config` is the quickest way to see what a machine will actually run with — it
resolves `config.toml` and every environment override, then prints the result.
The API key is reported as a boolean and never echoed.

## Configuration

Settings come from two places, in increasing order of precedence:

1. A TOML file — `config.toml` in the working directory, or `--config PATH`.
   A missing file is not an error; the built-in defaults are used.
2. Environment variables, which always win over the file.

[`config.toml`](config.toml) is the reference: every key it contains is
commented and set to its built-in default, so it parses to exactly the same
configuration as an empty file. A test enforces that, so the two cannot drift.

The Jev API key is the one setting that is **only** ever read from the
environment. Putting `api_key` in the TOML file is rejected with an error
rather than honoured, so the file stays safe to commit.

| Variable | Setting | Default |
| --- | --- | --- |
| `TYPESAFE_API_KEY` | Jev API key (environment only) | unset |
| `SYSLOG_TRIAGE_JEV_TIMEOUT_SECONDS` | Per-request timeout | `10.0` |
| `SYSLOG_TRIAGE_JEV_MAX_RETRIES` | Retries after the first attempt | `3` |
| `SYSLOG_TRIAGE_JEV_MAX_CONCURRENCY` | Ceiling on in-flight requests | `8` |
| `SYSLOG_TRIAGE_JOURNAL_UNITS` | Units to follow, comma separated; empty means all | *(all)* |
| `SYSLOG_TRIAGE_JOURNAL_MAX_PRIORITY` | Highest syslog priority kept, 0–7 | `6` |
| `SYSLOG_TRIAGE_JOURNAL_SINCE` | journalctl-style start point, e.g. `-1h` | *(tail)* |
| `SYSLOG_TRIAGE_JOURNAL_CURSOR_PATH` | Where the journal cursor is persisted | `var/cursor` |
| `SYSLOG_TRIAGE_THRESHOLDS_MIN_CONFIDENCE` | Below this, a question escalates | `0.75` |
| `SYSLOG_TRIAGE_THRESHOLDS_NOISE_CONFIDENCE` | Confidence required to drop as noise | `0.90` |
| `SYSLOG_TRIAGE_THRESHOLDS_ALERT_SEVERITY` | Severity at or above which to alert | `0.60` |
| `SYSLOG_TRIAGE_SINKS_STDOUT_ENABLED` | JSON-per-line to stdout | `true` |
| `SYSLOG_TRIAGE_SINKS_SLACK_ENABLED` | Slack webhook for alerts and escalations | `false` |
| `SYSLOG_TRIAGE_SINKS_SLACK_WEBHOOK_URL` | Slack webhook URL | unset |
| `SYSLOG_TRIAGE_SINKS_SQLITE_ENABLED` | Record every event and decision | `false` |
| `SYSLOG_TRIAGE_SINKS_SQLITE_PATH` | SQLite database path | `var/decisions.db` |

Thresholds default to the cautious end on purpose: the daemon would rather wake
a human than drop something it half-understood. `noise_confidence` sits above
`min_confidence` because dropping is the one decision nobody reviews later.

Unknown keys are an error rather than a silent no-op, so a typo in
`config.toml` fails loudly instead of quietly running on a default.

## Development

```sh
uv run ruff check .          # lint
uv run ruff format .         # format
uv run mypy                  # type check (strict)
uv run pytest                # tests
uv run pre-commit install    # run all of the above on commit
```

CI runs lint, format check, type check, and tests on Python 3.11, 3.12, and
3.13 for every push to `main` and every pull request.

## Layout

| Path | Contents |
| --- | --- |
| `src/syslog_triage/cli.py` | `syslog-triage` entry point: `config` and `run` |
| `src/syslog_triage/config.py` | Config dataclasses, TOML loading, env overrides, validation |
| `config.toml` | Commented reference configuration |
| `tests/` | One file per module |

## License

MIT — see [LICENSE](LICENSE).
