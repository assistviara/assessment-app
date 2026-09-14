from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.main import create_app


def pytest_configure(config):
    if config.option.basetemp is None:
        root = Path(__file__).resolve().parent.parent
        (root / ".test-tmp").mkdir(exist_ok=True)
        config.option.basetemp = str(root / ".test-tmp" / uuid4().hex)


@pytest.fixture
def web(tmp_path):
    application = create_app(f"sqlite:///{(tmp_path / 'test.sqlite3').as_posix()}")
    with TestClient(application) as client:
        yield client


@pytest.fixture
def session(web):
    with Session(web.app.state.engine) as db_session:
        yield db_session
