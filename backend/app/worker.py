"""Worker: `python -m app.worker` (spec-backend-skeleton.md, decisions section 10).

Migrates under the DB lock (skips if the schema is newer than the code), then runs the
scheduler until SIGTERM/SIGINT. Exactly one worker instance runs in production.
"""

from __future__ import annotations

import logging
import signal
import sys
import threading

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import ConfigError, Settings, get_settings
from app.db import migrations
from app.db.session import make_engine
from app.log import setup_logging

log = logging.getLogger("app.worker")


def make_scheduler() -> BackgroundScheduler:
    # Jobs are registered by later packages (watchdog, series, calendar, heartbeat).
    return BackgroundScheduler(timezone="UTC")


def run(settings: Settings, stop: threading.Event) -> int:
    engine = make_engine(settings.database_url)
    try:
        state = migrations.upgrade(engine)
        log.info("schema ready", extra={"schema": state.value})
        scheduler = make_scheduler()
        scheduler.start()
        log.info("worker started")
        stop.wait()
        scheduler.shutdown(wait=True)
        log.info("worker stopped")
        return 0
    finally:
        engine.dispose()


def main() -> int:
    try:
        settings = get_settings()
    except ConfigError as exc:
        print(f"worker: {exc}", file=sys.stderr)
        return 2
    setup_logging(settings.log_level)
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    return run(settings, stop)


if __name__ == "__main__":
    sys.exit(main())
