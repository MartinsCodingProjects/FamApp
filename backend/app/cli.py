"""Admin CLI: `python -m app.cli <command>` inside the api or worker container.

pairing-code <user name>   one-time pairing code for that user (valid 10 min)
lock-device <device id>    lock a device (revokes its tokens)
"""

from __future__ import annotations

import argparse
import sys
import uuid

from sqlalchemy import func, select

from app.clock import SystemClock
from app.config import ConfigError, get_settings
from app.db.models import Device, Notification, User
from app.db.rev import stamp
from app.db.session import make_engine, make_session_factory
from app.security.device_auth import DeviceAuth


def create_test_notification(session, user: User, clock) -> Notification:
    """A server notification shown right away (display key notif:<id>), README 10 → Tools."""
    notification = Notification(
        user_id=user.id, kind="test", message_key="notification.test.title", params={}, show_at=clock.now()
    )
    stamp(session, notification, clock)
    session.add(notification)
    return notification


def main(argv: list[str] | None = None, clock=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    code = commands.add_parser("pairing-code", help="create a one-time pairing code")
    code.add_argument("user")
    lock = commands.add_parser("lock-device", help="lock a device")
    lock.add_argument("device_id")
    test = commands.add_parser("test-notification", help="create a test notification")
    test.add_argument("user")
    args = parser.parse_args(argv)
    try:
        settings = get_settings()
    except ConfigError as exc:
        print(f"cli: {exc}", file=sys.stderr)
        return 2
    engine = make_engine(settings.database_url)
    clock = clock or SystemClock()
    try:
        with make_session_factory(engine)() as session:
            auth = DeviceAuth(session, settings.master_key_bytes, clock, ip="cli")
            if args.command in ("pairing-code", "test-notification"):
                user = session.scalars(
                    select(User).where(func.lower(User.name) == args.user.lower(), User.deleted_at.is_(None))
                ).one_or_none()
                if user is None:
                    print(f"cli: no user named {args.user!r}", file=sys.stderr)
                    return 1
            if args.command == "test-notification":
                notification = create_test_notification(session, user, clock)
                session.commit()
                print(f"created notif:{notification.id}")
            elif args.command == "pairing-code":
                value, expires = auth.create_pairing_code(user)
                session.commit()
                print(f"{value}  (valid until {expires:%H:%M} UTC)")
            else:
                device = session.get(Device, uuid.UUID(args.device_id))
                if device is None:
                    print(f"cli: no device {args.device_id}", file=sys.stderr)
                    return 1
                auth.lock(device, "admin")
                session.commit()
                print(f"locked {device.id}")
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
