import errno
import logging
import socket
import threading
from http.client import HTTPConnection
import re
import time
from urllib.parse import urlsplit, urlencode
from types import SimpleNamespace

import pytest

import launcher


def test_socket_is_loopback_and_remains_reserved():
    with launcher.reserve_socket(0) as sock:
        assert sock.getsockname()[0] == "127.0.0.1"
        with socket.socket() as other:
            with pytest.raises(OSError):
                other.bind(sock.getsockname())


def test_busy_port_uses_another_port():
    with launcher.reserve_socket(0) as first:
        with launcher.reserve_socket(first.getsockname()[1]) as second:
            assert second.getsockname()[1] != first.getsockname()[1]


def test_permission_error_is_not_treated_as_port_conflict(monkeypatch):
    class Denied:
        closed = False
        def setsockopt(self, *args):
            pass
        def bind(self, address):
            raise PermissionError(errno.EACCES, "denied")
        def close(self):
            self.closed = True
    sock = Denied()
    monkeypatch.setattr(launcher.socket, "socket", lambda *args: sock)
    with pytest.raises(PermissionError):
        launcher.reserve_socket()
    assert sock.closed


def test_browser_waits_for_startup_and_http_200(monkeypatch):
    server = SimpleNamespace(started=False, should_exit=False)
    probes = []
    opened = []
    class Stop:
        def is_set(self):
            return False
        def wait(self, delay):
            server.started = True
    def probe(*args):
        assert server.started
        probes.append(True)
        return len(probes) == 2
    monkeypatch.setattr(launcher, "responds_ok", probe)
    monkeypatch.setattr(launcher.webbrowser, "open", lambda url: opened.append(url) or True)
    failures = []
    launcher.wait_and_open(server, 12345, Stop(), failures)
    assert opened == ["http://127.0.0.1:12345/clients"]
    assert len(probes) == 2
    assert not failures


@pytest.mark.parametrize("started", [False, True])
def test_timeout_requests_shutdown_without_browser(monkeypatch, started):
    server = SimpleNamespace(started=started, should_exit=False)
    monkeypatch.setattr(launcher.webbrowser, "open", lambda url: pytest.fail("browser opened"))
    failures = []
    launcher.wait_and_open(server, 1, threading.Event(), failures, timeout=0)
    assert server.should_exit
    assert len(failures) == 1


def test_browser_failure_requests_shutdown(monkeypatch):
    server = SimpleNamespace(started=True, should_exit=False)
    monkeypatch.setattr(launcher, "responds_ok", lambda *args: True)
    monkeypatch.setattr(launcher.webbrowser, "open", lambda url: False)
    failures = []
    launcher.wait_and_open(server, 1, threading.Event(), failures)
    assert server.should_exit and failures


def test_stop_does_not_open_browser(monkeypatch):
    stopped = threading.Event()
    stopped.set()
    monkeypatch.setattr(launcher.webbrowser, "open", lambda url: pytest.fail("browser opened"))
    failures = []
    launcher.wait_and_open(SimpleNamespace(started=True, should_exit=False), 1, stopped, failures)
    assert not failures


def test_log_redacts_uvicorn_exception_content(tmp_path):
    path = tmp_path / "logs" / "app.log"
    handler, saved = launcher.configure_logging(path)
    try:
        try:
            raise ValueError("private database record")
        except ValueError:
            logging.getLogger("uvicorn.error").exception("private form contents")
        launcher.logger.info("Launcher starting")
    finally:
        for target, handlers, level, propagate in saved:
            target.handlers, target.level, target.propagate = handlers, level, propagate
        handler.close()
    content = path.read_text(encoding="utf-8")
    assert "private" not in content
    assert "Launcher starting" in content
    assert handler.maxBytes == 2 * 1024 * 1024 and handler.backupCount == 3


def test_real_server_creates_local_database_and_opens_once(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    original = launcher.reserve_socket
    monkeypatch.setattr(launcher, "reserve_socket", lambda: original(0))
    servers = []
    factory = launcher.uvicorn.Server
    def make_server(config):
        assert config.workers == 1 and not config.reload
        assert config.access_log is False and config.log_config is None
        server = factory(config)
        servers.append(server)
        return server
    monkeypatch.setattr(launcher.uvicorn, "Server", make_server)
    opened = []
    def open_browser(url):
        assert servers[0].started
        assert (tmp_path / "AssessmentApp/data/assessment.sqlite3").is_file()
        opened.append(url)
        servers[0].should_exit = True
        return True
    monkeypatch.setattr(launcher.webbrowser, "open", open_browser)
    monkeypatch.setattr(launcher, "show_error", lambda message: pytest.fail(message))
    assert launcher.main() == 0
    assert len(opened) == 1 and opened[0].endswith("/clients")
    assert (tmp_path / "AssessmentApp/logs/app.log").is_file()


def test_setup_failure_notifies_without_browser(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    (tmp_path / "AssessmentApp").write_text("blocked")
    messages = []
    monkeypatch.setattr(launcher, "show_error", messages.append)
    monkeypatch.setattr(launcher.webbrowser, "open", lambda url: pytest.fail("browser opened"))
    assert launcher.main() == 1
    assert len(messages) == 1


def test_keyboard_interrupt_is_normal_exit(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    original = launcher.reserve_socket
    monkeypatch.setattr(launcher, "reserve_socket", lambda: original(0))
    def interrupt(self, sockets):
        raise KeyboardInterrupt
    monkeypatch.setattr(launcher.uvicorn.Server, "run", interrupt)
    monkeypatch.setattr(launcher, "show_error", lambda message: pytest.fail(message))
    assert launcher.main() == 0


@pytest.mark.parametrize("status, expected", [(200, True), (303, False), (500, False)])
def test_probe_requires_exact_http_200(monkeypatch, status, expected):
    class Connection:
        closed = False
        def request(self, method, path):
            assert (method, path) == ("GET", "/clients")
        def getresponse(self):
            return SimpleNamespace(status=status)
        def close(self):
            self.closed = True
    connection = Connection()
    monkeypatch.setattr(launcher, "HTTPConnection", lambda *args, **kwargs: connection)
    assert launcher.responds_ok(12345, 1) is expected
    assert connection.closed


def test_invalid_database_stops_without_browser(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    database = tmp_path / "AssessmentApp/data/assessment.sqlite3"
    database.parent.mkdir(parents=True)
    database.write_bytes(b"invalid database - private data")
    original = launcher.reserve_socket
    monkeypatch.setattr(launcher, "reserve_socket", lambda: original(0))
    monkeypatch.setattr(launcher.webbrowser, "open", lambda url: pytest.fail("browser opened"))
    messages = []
    monkeypatch.setattr(launcher, "show_error", messages.append)
    assert launcher.main() == 1
    assert len(messages) == 1
    assert database.read_bytes() == b"invalid database - private data"
    assert "private data" not in (tmp_path / "AssessmentApp/logs/app.log").read_text(encoding="utf-8")


def test_shutdown_post_stops_real_server_and_disposes_engine(tmp_path, monkeypatch):
    from sqlalchemy import event
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    original = launcher.reserve_socket
    sockets = []
    def reserve():
        sock = original(0)
        sockets.append(sock)
        return sock
    monkeypatch.setattr(launcher, "reserve_socket", reserve)
    servers = []
    factory = launcher.uvicorn.Server
    def make_server(config):
        server = factory(config)
        servers.append(server)
        return server
    monkeypatch.setattr(launcher.uvicorn, "Server", make_server)
    disposed = []
    responses = []
    tokens = []
    requested = []
    def open_browser(url):
        server = servers[-1]
        event.listen(server.config.app.state.engine, "engine_disposed",
                     lambda engine: disposed.append(True))
        parsed = urlsplit(url)
        connection = HTTPConnection(parsed.hostname, parsed.port, timeout=5)
        try:
            connection.request("GET", "/clients")
            page = connection.getresponse().read().decode()
            token = re.search(r'name="shutdown_token" value="([^"]+)"', page).group(1)
            tokens.append(token)
            connection.request("POST", "/desktop/shutdown",
                               body=urlencode({"shutdown_token": token}),
                               headers={"Origin": f"http://{parsed.netloc}",
                                        "Content-Type": "application/x-www-form-urlencoded"})
            response = connection.getresponse()
            responses.append((response.status, response.read().decode()))
            deadline = time.monotonic() + 2
            while not server.should_exit and time.monotonic() < deadline:
                time.sleep(0.01)
            requested.append(server.should_exit)
        finally:
            connection.close()
            # Prevent a failed assertion/probe from leaving a test server running.
            server.should_exit = True
        return True
    monkeypatch.setattr(launcher.webbrowser, "open", open_browser)
    monkeypatch.setattr(launcher, "show_error", lambda message: pytest.fail(message))
    for _ in range(2):
        assert launcher.main() == 0
    assert len(responses) == 2
    assert all(status == 200 and "このタブを閉じてください。" in body for status, body in responses)
    assert disposed == [True, True]
    assert requested == [True, True]
    assert all(sock.fileno() == -1 for sock in sockets)
    assert tokens[0] != tokens[1]
    log = (tmp_path / "AssessmentApp/logs/app.log").read_text(encoding="utf-8")
    assert "Shutdown requested from application" in log
    assert all(token not in log for token in tokens)
