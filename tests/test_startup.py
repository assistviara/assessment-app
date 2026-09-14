from fastapi.testclient import TestClient
from sqlalchemy import inspect

from app.main import create_app


def test_startup_initializes_tables_and_serves_pages(web):
    assert {"client", "emergencycontact", "assessment", "assessmentcheck"} <= set(
        inspect(web.app.state.engine).get_table_names()
    )
    assert web.get("/", follow_redirects=False).headers["location"] == "/clients"
    assert web.get("/clients").status_code == 200
    assert web.get("/static/style.css").status_code == 200


def test_database_persists_across_restarts(tmp_path):
    url = f"sqlite:///{(tmp_path / 'persistent.sqlite3').as_posix()}"
    with TestClient(create_app(url)) as browser:
        assert browser.post("/clients", data={"name": "保持確認"}, follow_redirects=False).status_code == 303
    with TestClient(create_app(url)) as browser:
        assert "保持確認" in browser.get("/clients").text
