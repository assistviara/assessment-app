from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlalchemy import func
from sqlmodel import Session, select

from app.db import get_session
from app.form_fields import CLIENT_FIELDS
from app.models import Assessment, Client, now_local
from app.schemas import ClientInput
from app.views import CHOICES, get_or_404, templates, validation_messages

router = APIRouter()
DB = Annotated[Session, Depends(get_session)]


@router.get("/clients")
def client_list(request: Request, session: DB, q: str = ""):
    query = select(Client, func.max(Assessment.created_at)).outerjoin(Assessment).group_by(Client.id)
    if q.strip():
        query = query.where(Client.name.contains(q.strip(), autoescape=True))
    rows = [(client, latest.date() if latest else None) for client, latest in session.exec(query.order_by(Client.id.desc())).all()]
    return templates.TemplateResponse(request=request, name="clients/list.html", context={"title": "利用者一覧", "rows": rows, "q": q})


def client_form(request, values, client_id=None, errors=None):
    return templates.TemplateResponse(
        request=request, name="clients/form.html", status_code=422 if errors else 200,
        context={
            "title": "利用者編集" if client_id else "利用者登録", "values": values,
            "fields": CLIENT_FIELDS, "choices": CHOICES, "errors": errors,
            "action": f"/clients/{client_id}" if client_id else "/clients",
            "cancel_url": f"/clients/{client_id}" if client_id else "/clients",
        },
    )


@router.get("/clients/new")
def new_client(request: Request):
    return client_form(request, {})


@router.post("/clients")
async def create_client(request: Request, session: DB):
    values = dict(await request.form())
    try:
        data = ClientInput.model_validate(values)
    except ValidationError as error:
        return client_form(request, values, errors=validation_messages(error))
    timestamp = now_local()
    client = Client(**data.model_dump(), created_at=timestamp, updated_at=timestamp)
    session.add(client)
    session.commit()
    session.refresh(client)
    return RedirectResponse(f"/clients/{client.id}", status_code=303)


@router.get("/clients/{client_id}")
def client_detail(client_id: int, request: Request, session: DB):
    client = get_or_404(session, Client, client_id)
    history = session.exec(select(Assessment).where(Assessment.client_id == client_id).order_by(Assessment.created_at.desc(), Assessment.id.desc())).all()
    return templates.TemplateResponse(request=request, name="clients/detail.html", context={
        "title": "利用者詳細", "client": client, "values": client.model_dump(), "fields": CLIENT_FIELDS, "history": history,
    })


@router.get("/clients/{client_id}/edit")
def edit_client(client_id: int, request: Request, session: DB):
    client = get_or_404(session, Client, client_id)
    return client_form(request, client.model_dump(), client_id)


@router.post("/clients/{client_id}")
async def update_client(client_id: int, request: Request, session: DB):
    client = get_or_404(session, Client, client_id)
    values = dict(await request.form())
    try:
        data = ClientInput.model_validate(values)
    except ValidationError as error:
        return client_form(request, values, client_id, validation_messages(error))
    for name, value in data.model_dump().items():
        setattr(client, name, value)
    client.updated_at = now_local()
    session.add(client)
    session.commit()
    return RedirectResponse(f"/clients/{client_id}", status_code=303)
