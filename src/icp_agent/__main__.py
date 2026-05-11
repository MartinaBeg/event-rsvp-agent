"""Entry point: `python -m icp_agent` runs one full pass."""

from __future__ import annotations

import sys

from .config import load_settings
from .log import configure_logging, get_logger
from .pipeline import run


def main() -> int:
    settings = load_settings()
    configure_logging(level=settings.log_level, fmt=settings.log_format)
    log = get_logger("icp_agent")
    try:
        run(settings=settings)
    except Exception as e:
        log.error("pipeline.failed", error=str(e), exc_info=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
