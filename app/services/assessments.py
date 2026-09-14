from datetime import date

from sqlmodel import Session, select

from app.models import Assessment, AssessmentCheck, Client, ClientFields, now_local
from app.schemas import AssessmentInput, CheckInput


def latest_assessment(session: Session, client_id: int) -> Assessment | None:
    # The primary ordering is created_at; id makes identical timestamps deterministic.
    return session.exec(
        select(Assessment)
        .where(Assessment.client_id == client_id)
        .order_by(Assessment.created_at.desc(), Assessment.id.desc())
    ).first()


def reassessment_defaults(source: Assessment) -> tuple[dict, dict]:
    """Read-only projection; never attach a draft or modify the source."""
    values = {name: getattr(source, name) for name in AssessmentInput.model_fields}
    values["received_date"] = date.today()
    check_values = {
        name: getattr(source.check, name) if source.check else None
        for name in CheckInput.model_fields
    }
    return values, check_values


def create_assessment(
    session: Session,
    client_id: int,
    data: AssessmentInput,
    check_data: CheckInput,
    source_id: int | None = None,
) -> Assessment:
    if source_id is not None:
        source = session.get(Assessment, source_id)
        if source is None or source.client_id != client_id:
            raise ValueError("参照元Assessmentが存在しないか、利用者が一致しません。")

    timestamp = now_local()
    client = session.get(Client, client_id)
    if client is None:
        raise ValueError("利用者が存在しません。")
    snapshot = ClientFields.model_validate(client).model_dump(mode="json")
    assessment = Assessment(
        **data.model_dump(), client_id=client_id,
        client_snapshot=snapshot,
        source_assessment_id=source_id, created_at=timestamp, updated_at=timestamp,
    )
    try:
        session.add(assessment)
        session.flush()
        session.add(AssessmentCheck(**check_data.model_dump(), assessment_id=assessment.id))
        session.commit()
    except Exception:
        session.rollback()
        raise
    session.refresh(assessment)
    return assessment


def update_assessment(session: Session, assessment: Assessment, data: AssessmentInput):
    for name, value in data.model_dump().items():
        setattr(assessment, name, value)
    assessment.updated_at = now_local()
    session.add(assessment)
    session.commit()


def save_check(session: Session, assessment: Assessment, data: CheckInput):
    check = assessment.check
    if check is None:
        check = AssessmentCheck(assessment_id=assessment.id)
    for name, value in data.model_dump().items():
        setattr(check, name, value)
    session.add(check)
    session.commit()
