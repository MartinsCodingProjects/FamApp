from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all tables; Alembic (1.4.4) reads Base.metadata."""
