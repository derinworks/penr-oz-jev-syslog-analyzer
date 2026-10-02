"""Entry point for ``python -m syslog_triage``."""

import sys

from syslog_triage.cli import main

if __name__ == "__main__":
    sys.exit(main())
