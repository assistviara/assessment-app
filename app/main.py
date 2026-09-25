from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.db import init_db, make_engine
from app.paths import default_database_path, resource_root
from app.routers import assessments, clients, pdf


def create_app(database_url: str | None = None) -> FastAPI:
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
    application.mount("/static", StaticFiles(directory=resource_root() / "app" / "static"), name="static")
    application.include_router(clients.router)
    application.include_router(assessments.router)
    application.include_router(pdf.router)

    @application.get("/", include_in_schema=False)
    def index():
        return RedirectResponse("/clients", status_code=303)

    return application


app = create_app()
