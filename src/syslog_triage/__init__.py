"""Ask Jev about journal events, then act on the answer only when it is confident."""

from syslog_triage.config import Config, ConfigError, load_config

__version__ = "0.1.0"

__all__ = ["Config", "ConfigError", "__version__", "load_config"]
