import asyncio

from fastapi.testclient import TestClient
import pytest

from app.main import app, create_app

ORIGIN = "http://127.0.0.1:8123"


@pytest.fixture
def desktop(tmp_path):
    calls = []
    async def stop():
        calls.append("shutdown")
    application = create_app(f"sqlite:///{(tmp_path / 'desktop.sqlite3').as_posix()}",
                             desktop_shutdown=stop, desktop_origin=ORIGIN)
    with TestClient(application, base_url=ORIGIN) as client:
        yield client, calls


def test_development_has_no_shutdown(web):
    assert "アプリを終了する" not in web.get("/clients").text
    assert web.get("/desktop/shutdown").status_code == 404
    assert web.post("/desktop/shutdown").status_code == 404
    client = TestClient(app)
    assert client.get("/desktop/shutdown").status_code == 404
    assert client.post("/desktop/shutdown").status_code == 404


def test_launcher_ui_and_valid_post(desktop):
    client, calls = desktop
    token = client.app.state.desktop_token
    page = client.get("/clients").text
    assert 'action="/desktop/shutdown"' in page
    assert 'method="post"' in page and 'window.confirm(' in page
    assert "未保存の入力内容は保存されません。他のタブでもこのアプリを利用できなくなります。" in page
    assert f'value="{token}"' in page
    assert not calls
    response = client.post("/desktop/shutdown", headers={"Origin": ORIGIN},
                           data={"shutdown_token": token})
    assert response.status_code == 200
    assert calls == ["shutdown"]
    assert "アプリの終了を受け付けました。" in response.text
    assert "このタブを閉じてください。" in response.text
    assert "<link" not in response.text and "<img" not in response.text
    assert token not in response.text and token not in str(response.url)
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("method", ["GET", "HEAD", "PUT", "DELETE"])
def test_other_methods_never_shutdown(desktop, method):
    client, calls = desktop
    assert client.request(method, "/desktop/shutdown").status_code == 405
    assert not calls


@pytest.mark.parametrize("token", [None, "wrong", "日本語"])
def test_invalid_token_rejected(desktop, token):
    client, calls = desktop
    data = {} if token is None else {"shutdown_token": token}
    assert client.post("/desktop/shutdown", headers={"Origin": ORIGIN}, data=data).status_code == 403
    assert not calls


@pytest.mark.parametrize("origin,host", [
    (None, "127.0.0.1:8123"), ("null", "127.0.0.1:8123"),
    ("http://evil.example", "127.0.0.1:8123"),
    ("http://127.0.0.1:8124", "127.0.0.1:8123"),
    (ORIGIN, "localhost:8123"), (ORIGIN, "127.0.0.1:8124"), (ORIGIN, ""),
])
def test_invalid_origin_or_host_rejected(desktop, origin, host):
    client, calls = desktop
    headers = {"Host": host}
    if origin is not None:
        headers["Origin"] = origin
    response = client.post("/desktop/shutdown", headers=headers,
                           data={"shutdown_token": client.app.state.desktop_token})
    assert response.status_code == 403
    assert not calls


def test_token_is_unique_and_not_shared(desktop):
    client, calls = desktop
    async def stop():
        pass
    other = create_app(desktop_shutdown=stop, desktop_origin=ORIGIN)
    assert other.state.desktop_token != client.app.state.desktop_token
    assert app.state.desktop_shutdown is None
    assert client.post("/desktop/shutdown", headers={"Origin": ORIGIN},
                       data={"shutdown_token": other.state.desktop_token}).status_code == 403
    assert not calls


def test_background_callback_runs_after_response_body(desktop):
    client, calls = desktop
    sent = []
    body = f"shutdown_token={client.app.state.desktop_token}".encode()
    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}
    async def send(message):
        assert not calls
        sent.append(message)
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
             "method": "POST", "scheme": "http", "path": "/desktop/shutdown",
             "raw_path": b"/desktop/shutdown", "query_string": b"", "root_path": "",
             "headers": [(b"host", b"127.0.0.1:8123"), (b"origin", ORIGIN.encode()),
                         (b"content-type", b"application/x-www-form-urlencoded")],
             "client": ("127.0.0.1", 12345), "server": ("127.0.0.1", 8123)}
    asyncio.run(client.app(scope, receive, send))
    assert sent[-1]["type"] == "http.response.body"
    assert not sent[-1].get("more_body", False)
    assert calls == ["shutdown"]


@pytest.mark.parametrize("origin", [None, "http://localhost:8000", "http://0.0.0.0:8000",
                                   "https://127.0.0.1:8000", "http://127.0.0.1:8000/path"])
def test_desktop_configuration_requires_loopback_origin(origin):
    async def stop():
        pass
    with pytest.raises(ValueError):
        create_app(desktop_shutdown=stop, desktop_origin=origin)
