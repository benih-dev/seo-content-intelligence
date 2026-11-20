from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from seoci.config import settings


class Base(DeclarativeBase):
    pass


def make_engine(url):
    if url.startswith("sqlite"):
        path = url.split("///", 1)[-1]
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30} if url.startswith("sqlite") else {})
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def pragmas(conn, _):
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA journal_mode=WAL")
    return engine


engine = make_engine(settings.database_url)
Session = sessionmaker(engine, expire_on_commit=False)


def init_db():
    from seoci import models  # noqa: F401
    Base.metadata.create_all(engine)
