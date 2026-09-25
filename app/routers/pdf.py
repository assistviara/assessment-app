from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlmodel import Session

from app.db import get_session
from app.models import Assessment
from app.pdf import coordinates, fonts
from app.pdf import templates as pdf_templates
from app.pdf.errors import PdfError
from app.pdf.renderer import render_assessment_pdf, render_checksheet_pdf
from app.pdf.mapping import assessment_fields, assessment_check_fields
from app.views import get_or_404, templates

router = APIRouter()


@router.get("/assessments/{assessment_id}/pdf/assessment", name="assessment_pdf")
def assessment_pdf(assessment_id: int, request: Request, session: Annotated[Session, Depends(get_session)]):
    assessment = get_or_404(session, Assessment, assessment_id)
    try:
        fields = assessment_fields(assessment)
        content = render_assessment_pdf(
            assessment.client_snapshot, pdf_templates.ASSESSMENT_TEMPLATE_PATH,
            fonts.JAPANESE_FONT_PATH, coordinates.FIELD_POSITIONS["client_name"],
            fields=fields,
        )
    except PdfError as error:
        return templates.TemplateResponse(
            request=request, name="assessments/pdf_error.html", status_code=error.status_code,
            context={"title": "PDFを生成できません", "message": str(error), "assessment_id": assessment_id},
            headers={"Cache-Control": "no-store"},
        )
    return Response(content, media_type="application/pdf", headers={
        "Content-Disposition": f'inline; filename="assessment_{assessment_id}.pdf"',
        "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
    })


@router.get("/assessments/{assessment_id}/pdf/check", name="assessment_check_pdf")
def assessment_check_pdf(assessment_id: int, request: Request, session: Annotated[Session, Depends(get_session)]):
    assessment = get_or_404(session, Assessment, assessment_id)
    try:
        content = render_checksheet_pdf(
            assessment_check_fields(assessment), pdf_templates.CHECKSHEET_TEMPLATE_PATH,
            fonts.JAPANESE_FONT_PATH,
        )
    except PdfError as error:
        return templates.TemplateResponse(
            request=request, name="assessments/pdf_error.html", status_code=error.status_code,
            context={"title": "PDFを生成できません", "message": str(error), "assessment_id": assessment_id},
            headers={"Cache-Control": "no-store"},
        )
    return Response(content, media_type="application/pdf", headers={
        "Content-Disposition": f'inline; filename="assessment_check_{assessment_id}.pdf"',
        "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
    })
