from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlmodel import Session

from app.db import get_session
from app.form_fields import ASSESSMENT_SECTIONS, CHECK_FIELDS, CLIENT_FIELDS
from app.models import Assessment, Client
from app.schemas import AssessmentInput, CheckInput
from app.services.assessments import create_assessment, latest_assessment, reassessment_defaults, save_check, update_assessment
from app.views import CHOICES, form_values, get_or_404, templates, validation_messages

router = APIRouter()
DB = Annotated[Session, Depends(get_session)]


def assessment_form(request, client, values, check_values=None, assessment=None, source_id=None, errors=None):
    is_new = assessment is None
    if not is_new:
        title, action = "Assessment編集", f"/assessments/{assessment.id}"
    elif source_id:
        title, action = "再アセスメント作成", f"/clients/{client.id}/reassessments"
    else:
        title, action = "Assessment新規作成", f"/clients/{client.id}/assessments"
    return templates.TemplateResponse(
        request=request, name="assessments/form.html", status_code=422 if errors else 200,
        context={
            "title": title, "action": action, "client": client,
            "values": form_values(values), "check_values": check_values or {},
            "sections": ASSESSMENT_SECTIONS, "check_fields": CHECK_FIELDS,
            "client_fields": CLIENT_FIELDS,
            "client_values": client.model_dump() if is_new else assessment.client_snapshot,
            "choices": CHOICES, "source_id": source_id, "is_new": is_new,
            "assessment_id": assessment.id if assessment else None, "errors": errors,
        },
    )


@router.get("/clients/{client_id}/assessments/new")
def new_assessment(client_id: int, request: Request, session: DB):
    client = get_or_404(session, Client, client_id)
    if latest_assessment(session, client_id):
        return RedirectResponse(f"/clients/{client_id}/reassessments/new", status_code=303)
    return assessment_form(request, client, {})


@router.get("/clients/{client_id}/reassessments/new")
def new_reassessment(client_id: int, request: Request, session: DB):
    client = get_or_404(session, Client, client_id)
    source = latest_assessment(session, client_id)
    if source is None:
        raise HTTPException(404, "参照元Assessmentがありません。初回Assessmentを作成してください。")
    values, checks = reassessment_defaults(source)
    return assessment_form(request, client, values, checks, source_id=source.id)


async def save_new(request, session, client_id, is_reassessment):
    client = get_or_404(session, Client, client_id)
    values = dict(await request.form())
    source_id = None
    if is_reassessment:
        try:
            source_id = int(values.get("source_assessment_id", ""))
        except (TypeError, ValueError):
            raise HTTPException(422, "参照元Assessmentを指定してください。")
        source = get_or_404(session, Assessment, source_id)
        if source.client_id != client_id:
            raise HTTPException(422, "参照元Assessmentの利用者が一致しません。")
    elif values.get("source_assessment_id") or latest_assessment(session, client_id):
        raise HTTPException(409, "2回目以降は利用者詳細の再アセスメント作成から入力してください。")

    try:
        data = AssessmentInput.model_validate(values)
        checks = CheckInput.model_validate(values)
    except ValidationError as error:
        return assessment_form(request, client, values, values, source_id=source_id, errors=validation_messages(error))
    assessment = create_assessment(session, client_id, data, checks, source_id)
    return RedirectResponse(f"/assessments/{assessment.id}/edit", status_code=303)


@router.post("/clients/{client_id}/assessments")
async def save_initial_assessment(client_id: int, request: Request, session: DB):
    return await save_new(request, session, client_id, False)


@router.post("/clients/{client_id}/reassessments")
async def save_reassessment(client_id: int, request: Request, session: DB):
    return await save_new(request, session, client_id, True)


@router.get("/assessments/{assessment_id}/edit")
def edit_assessment(assessment_id: int, request: Request, session: DB):
    assessment = get_or_404(session, Assessment, assessment_id)
    return assessment_form(request, assessment.client, assessment.model_dump(), assessment=assessment)


@router.post("/assessments/{assessment_id}")
async def save_existing_assessment(assessment_id: int, request: Request, session: DB):
    assessment = get_or_404(session, Assessment, assessment_id)
    values = dict(await request.form())
    try:
        data = AssessmentInput.model_validate(values)
    except ValidationError as error:
        return assessment_form(request, assessment.client, values, assessment=assessment, errors=validation_messages(error))
    update_assessment(session, assessment, data)
    return RedirectResponse(f"/assessments/{assessment.id}/edit", status_code=303)


def check_form(request, assessment, values, errors=None):
    return templates.TemplateResponse(
        request=request, name="assessments/check_form.html", status_code=422 if errors else 200,
        context={"title": "AssessmentCheck入力・編集", "assessment": assessment, "client": assessment.client,
                 "fields": CHECK_FIELDS, "values": values, "choices": CHOICES, "errors": errors},
    )


@router.get("/assessments/{assessment_id}/check/edit")
def edit_check(assessment_id: int, request: Request, session: DB):
    assessment = get_or_404(session, Assessment, assessment_id)
    return check_form(request, assessment, assessment.check.model_dump() if assessment.check else {})


@router.post("/assessments/{assessment_id}/check")
async def update_check(assessment_id: int, request: Request, session: DB):
    assessment = get_or_404(session, Assessment, assessment_id)
    values = dict(await request.form())
    try:
        data = CheckInput.model_validate(values)
    except ValidationError as error:
        return check_form(request, assessment, values, validation_messages(error))
    save_check(session, assessment, data)
    return RedirectResponse(f"/assessments/{assessment.id}/check/edit", status_code=303)
