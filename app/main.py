from contextlib import asynccontextmanager
from collections.abc import Awaitable, Callable
import secrets
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.db import init_db, make_engine
from app.paths import default_database_path, resource_root
from app.routers import assessments, clients, desktop, pdf


def create_app(database_url: str | None = None, *,
               desktop_shutdown: Callable[[], Awaitable[None]] | None = None,
               desktop_origin: str | None = None) -> FastAPI:
    if desktop_shutdown is not None:
        origin = urlsplit(desktop_origin or "")
        if (origin.scheme != "http" or origin.hostname != "127.0.0.1"
                or origin.port is None or not 1 <= origin.port <= 65535
                or desktop_origin != f"http://127.0.0.1:{origin.port}"):
            raise ValueError("終了機能には127.0.0.1のポート付きOriginが必要です。")
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        if database_url is None:
            db_path = default_database_path()
            db_path.parent.mkdir(parents=True, exist_ok=True)
            url = f"sqlite:///{db_path.as_posix()}"
        else:
            url = database_url
        engine = make_engine(url)
        application.state.engine = engine
        try:
            init_db(engine)
            yield
        finally:
            engine.dispose()

    application = FastAPI(title="Assessment App", lifespan=lifespan)
    application.state.desktop_shutdown = desktop_shutdown
    if desktop_shutdown is not None:
        application.state.desktop_origin = desktop_origin
        application.state.desktop_token = secrets.token_urlsafe(32)
        application.include_router(desktop.router)
    application.mount("/static", StaticFiles(directory=resource_root() / "app" / "static"), name="static")
    application.include_router(clients.router)
    application.include_router(assessments.router)
    application.include_router(pdf.router)

    @application.get("/", include_in_schema=False)
    def index():
        return RedirectResponse("/clients", status_code=303)

    return application


app = create_app()
