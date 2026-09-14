from pathlib import Path

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine
from starlette.requests import Request

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "assessment.sqlite3"


def make_engine(database_url: str):
    engine = create_engine(database_url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    return engine


def init_db(engine):
    from app import models  # noqa: F401 -- register every table before create_all

    SQLModel.metadata.create_all(engine)


def get_session(request: Request):
    with Session(request.app.state.engine) as session:
        yield session
