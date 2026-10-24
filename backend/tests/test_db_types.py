"""UTC round-trip on SQLite and MariaDB (BUILDPLAN 1.3.10, A7)."""

from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy import Column, Integer, MetaData, Table, insert, select

from app.db.types import UTCDateTime


@pytest.fixture
def events(engine):
    metadata = MetaData()
    table = Table("test_events", metadata, Column("id", Integer, primary_key=True), Column("at", UTCDateTime))
    metadata.create_all(engine)
    yield table
    metadata.drop_all(engine)


def roundtrip(engine, table, value):
    with engine.begin() as conn:
        row_id = conn.execute(insert(table).values(at=value)).inserted_primary_key[0]
    with engine.connect() as conn:
        return conn.execute(select(table.c.at).where(table.c.id == row_id)).scalar_one()


@pytest.mark.parametrize(
    "value",
    [
        datetime(2026, 1, 15, 9, 0, 0, 123456, tzinfo=UTC),
        datetime(2026, 3, 29, 2, 30, tzinfo=timezone(timedelta(hours=2))),  # DST switch day, given in +02:00
        datetime(2026, 10, 25, 2, 30, tzinfo=timezone(timedelta(hours=1))),
        datetime(1999, 12, 31, 23, 59, 59, tzinfo=timezone(timedelta(hours=-5))),
    ],
)
def test_utc_roundtrip(engine, events, value):
    stored = roundtrip(engine, events, value)
    assert stored == value
    assert stored.tzinfo is UTC
    assert stored.microsecond == value.microsecond


def test_null_roundtrip(engine, events):
    assert roundtrip(engine, events, None) is None


def test_naive_datetime_rejected(engine, events):
    with pytest.raises(Exception, match="naive"):
        roundtrip(engine, events, datetime(2026, 1, 15, 9, 0))


def test_ordering_matches_instants(engine, events):
    plus2 = timezone(timedelta(hours=2))
    earlier = datetime(2026, 7, 1, 11, 0, tzinfo=plus2)  # 09:00 UTC
    later = datetime(2026, 7, 1, 9, 30, tzinfo=UTC)
    with engine.begin() as conn:
        conn.execute(insert(events), [{"at": later}, {"at": earlier}])
    with engine.connect() as conn:
        values = conn.execute(select(events.c.at).order_by(events.c.at)).scalars().all()
    assert values == [earlier, later]
