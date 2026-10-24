"""Engine and sessions from DATABASE_URL (A7). Unset → sqlite:///./dev.db."""

from __future__ import annotations

import os

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db import dialects

DEFAULT_DATABASE_URL = "sqlite:///./dev.db"


def database_url() -> str:
    return os.environ.get("DATABASE_URL") or DEFAULT_DATABASE_URL


def make_engine(url: str | None = None) -> Engine:
    url = url or database_url()
    engine = create_engine(url, **dialects.engine_options(url))
    dialects.configure(engine)
    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)
