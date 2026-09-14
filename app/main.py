from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.db import DEFAULT_DB_PATH, init_db, make_engine
from app.routers import assessments, clients, pdf


def create_app(database_url: str | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        if database_url is None:
            DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        engine = make_engine(database_url or f"sqlite:///{DEFAULT_DB_PATH.as_posix()}")
        application.state.engine = engine
        try:
            init_db(engine)
            yield
        finally:
            engine.dispose()

    application = FastAPI(title="Assessment App", lifespan=lifespan)
    application.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
    application.include_router(clients.router)
    application.include_router(assessments.router)
    application.include_router(pdf.router)

    @application.get("/", include_in_schema=False)
    def index():
        return RedirectResponse("/clients", status_code=303)

    return application


app = create_app()
