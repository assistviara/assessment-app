"""Local Windows launcher. Run with the project's Python environment."""

import errno
from http.client import HTTPConnection, HTTPException
import logging
from logging.handlers import RotatingFileHandler
import socket
import threading
import time
import webbrowser

import uvicorn

from app.paths import user_data_dir

HOST = "127.0.0.1"
STARTUP_TIMEOUT = 30.0
logger = logging.getLogger("assessment_launcher")


class PrivateFormatter(logging.Formatter):
    """Never persist exception text (SQL errors can contain record values)."""

    def format(self, record):
        if record.name.startswith("uvicorn"):
            return f"{self.formatTime(record)} {record.levelname} Uvicorn event"
        return super().format(record)


def configure_logging(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(path, maxBytes=2 * 1024 * 1024,
                                  backupCount=3, encoding="utf-8")
    handler.setFormatter(PrivateFormatter("%(asctime)s %(levelname)s %(message)s"))
    saved = []
    for name in ("assessment_launcher", "uvicorn", "uvicorn.error", "uvicorn.access"):
        target = logging.getLogger(name)
        saved.append((target, target.handlers[:], target.level, target.propagate))
        target.handlers = [handler]
        target.setLevel(logging.INFO)
        target.propagate = False
    return handler, saved


def reserve_socket(port=8000):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            sock.bind((HOST, port))
        except OSError as error:
            if error.errno != errno.EADDRINUSE and getattr(error, "winerror", None) != 10048:
                raise
            sock.bind((HOST, 0))
        sock.listen(socket.SOMAXCONN)
        sock.setblocking(False)
        return sock
    except BaseException:
        sock.close()
        raise


def responds_ok(port, timeout):
    connection = HTTPConnection(HOST, port, timeout=timeout)
    try:
        connection.request("GET", "/clients")
        return connection.getresponse().status == 200
    except (OSError, HTTPException):
        return False
    finally:
        connection.close()


def wait_and_open(server, port, stopped, failures, timeout=STARTUP_TIMEOUT):
    deadline = time.monotonic() + timeout
    try:
        while not stopped.is_set() and not server.should_exit:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("起動確認が30秒以内に完了しませんでした。")
            if server.started and responds_ok(port, min(1.0, remaining)):
                if stopped.is_set() or server.should_exit:
                    return
                if time.monotonic() >= deadline:
                    continue
                logger.info("Application ready; opening browser")
                if not webbrowser.open(f"http://{HOST}:{port}/clients"):
                    raise RuntimeError("既定ブラウザを開けませんでした。")
                return
            stopped.wait(min(0.1, remaining))
    except Exception as error:
        # Store only controlled messages, never HTTP bodies or database errors.
        message = ("起動確認が制限時間内に完了しませんでした。" if isinstance(error, TimeoutError)
                   else "起動確認またはブラウザ起動に失敗しました。")
        failures.append(message)
        logger.error("Startup monitor failed (%s)", type(error).__name__)
        server.should_exit = True


def show_error(message):
    from tkinter import Tk, messagebox
    root = Tk()
    root.withdraw()
    try:
        messagebox.showerror("アセスメント 起動エラー", message, parent=root)
    finally:
        root.destroy()


def main():
    handler = None
    saved = []
    sock = None
    monitor = None
    server = None
    stopped = threading.Event()
    failures = []
    log_path = None
    try:
        directory = user_data_dir()
        candidate = directory / "logs" / "app.log"
        handler, saved = configure_logging(candidate)
        log_path = candidate
        logger.info("Launcher starting")
        database = directory / "data" / "assessment.sqlite3"
        database.parent.mkdir(parents=True, exist_ok=True)
        sock = reserve_socket()
        port = sock.getsockname()[1]
        logger.info("Listening on loopback port %s", port)
        from app.main import create_app
        async def request_shutdown():
            logger.info("Shutdown requested from application")
            server.should_exit = True

        application = create_app(database_url=f"sqlite:///{database.as_posix()}",
                                 desktop_shutdown=request_shutdown,
                                 desktop_origin=f"http://{HOST}:{port}")
        config = uvicorn.Config(application, host=HOST, port=port, workers=1,
                                reload=False, loop="asyncio", http="h11", ws="none",
                                lifespan="on", log_config=None, access_log=False)
        server = uvicorn.Server(config)
        monitor = threading.Thread(target=wait_and_open,
                                   args=(server, port, stopped, failures), daemon=True)
        monitor.start()
        server.run(sockets=[sock])
        if not server.started and not failures:
            failures.append("サーバーの起動が完了しませんでした。")
    except KeyboardInterrupt:
        logger.info("Stopped by Ctrl+C")
    except (Exception, SystemExit) as error:
        logger.error("Launcher failed (%s)", type(error).__name__)
        failures.append("アプリを起動できませんでした。保存先や実行環境を確認してください。")
    finally:
        stopped.set()
        if server is not None:
            server.should_exit = True
        if monitor is not None:
            monitor.join(timeout=2)
        if sock is not None:
            sock.close()
        logger.info("Launcher stopped")
        if handler is not None:
            for target, handlers, level, propagate in saved:
                target.handlers = handlers
                target.setLevel(level)
                target.propagate = propagate
            handler.close()
    if failures:
        location = f"\nログ: {log_path}" if log_path else "\nログ保存先を準備できませんでした。"
        show_error(failures[0] + location)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
