import pytest
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.models import Assessment, AssessmentCheck, Client, EmergencyContact
from app.schemas import AssessmentInput, CheckInput
from app.services.assessments import create_assessment


def test_relationships_and_self_reference(session):
    client = Client(name="リレーション")
    session.add(client)
    session.commit()
    first = create_assessment(session, client.id, AssessmentInput(), CheckInput())
    second = create_assessment(session, client.id, AssessmentInput(), CheckInput(), first.id)
    session.add_all([EmergencyContact(client_id=client.id, name="連絡先1", priority=1), EmergencyContact(client_id=client.id, name="連絡先2", priority=2)])
    session.commit()
    session.expire_all()
    assert len(client.assessments) == 2 and len(client.emergency_contacts) == 2
    assert second.source_assessment.id == first.id
    assert first.reassessments[0].id == second.id
    assert first.check.assessment.id == first.id


@pytest.mark.parametrize("record", [
    lambda: EmergencyContact(client_id=999),
    lambda: Assessment(client_id=999),
    lambda: AssessmentCheck(assessment_id=999),
])
def test_database_rejects_missing_parent(session, record):
    session.add(record())
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_database_rejects_second_check(session):
    client = Client(name="一意制約")
    session.add(client)
    session.commit()
    assessment = create_assessment(session, client.id, AssessmentInput(), CheckInput())
    session.add(AssessmentCheck(assessment_id=assessment.id))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
    assert len(session.exec(select(AssessmentCheck)).all()) == 1


def test_reassessment_rejects_other_clients_source(web, session):
    owner, other = Client(name="元利用者"), Client(name="別利用者")
    session.add_all([owner, other])
    session.commit()
    source = create_assessment(session, owner.id, AssessmentInput(), CheckInput())
    assert web.post(f"/clients/{other.id}/reassessments", data={"source_assessment_id": str(source.id)}).status_code == 422
    with pytest.raises(ValueError):
        create_assessment(session, other.id, AssessmentInput(), CheckInput(), source.id)
    assert len(session.exec(select(Assessment)).all()) == 1


def test_check_failure_rolls_back_new_assessment_and_preserves_source(web, session):
    client = Client(name="一括保存")
    session.add(client)
    session.commit()
    source = create_assessment(session, client.id, AssessmentInput(family_request="元内容"), CheckInput(adl="元Check"))
    client_id, source_id = client.id, source.id

    def fail_check(_, __, statement, *args):
        if statement.startswith("INSERT INTO assessmentcheck"):
            raise RuntimeError("simulated check write failure")

    event.listen(web.app.state.engine, "before_cursor_execute", fail_check)
    try:
        with pytest.raises(RuntimeError):
            create_assessment(session, client_id, AssessmentInput(family_request="新内容"), CheckInput(), source_id)
    finally:
        event.remove(web.app.state.engine, "before_cursor_execute", fail_check)
    assert len(session.exec(select(Assessment)).all()) == 1
    assert len(session.exec(select(AssessmentCheck)).all()) == 1
    assert session.get(Assessment, source_id).family_request == "元内容"
    assert session.get(Assessment, source_id).check.adl == "元Check"
