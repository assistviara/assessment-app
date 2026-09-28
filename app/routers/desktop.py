"""Launcher-only shutdown; no server object is exposed to the application."""

import secrets

from fastapi import APIRouter, HTTPException, Request
from starlette.background import BackgroundTask

from app.views import templates

router = APIRouter()


@router.post("/desktop/shutdown", include_in_schema=False)
async def shutdown(request: Request):
    state = request.app.state
    expected_host = state.desktop_origin.removeprefix("http://")
    if (request.headers.getlist("origin") != [state.desktop_origin]
            or request.headers.getlist("host") != [expected_host]):
        raise HTTPException(status_code=403, detail="終了要求を確認できません。")
    form = await request.form()
    tokens = form.getlist("shutdown_token")
    if (len(tokens) != 1 or not isinstance(tokens[0], str)
            or not secrets.compare_digest(tokens[0].encode("utf-8"), state.desktop_token.encode("ascii"))):
        raise HTTPException(status_code=403, detail="終了要求を確認できません。")
    return templates.TemplateResponse(
        request=request, name="desktop/closed.html", context={},
        headers={"Cache-Control": "no-store"},
        background=BackgroundTask(state.desktop_shutdown),
    )
