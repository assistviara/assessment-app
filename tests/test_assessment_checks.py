from sqlmodel import select

from app.models import Assessment, AssessmentCheck, Client
from app.schemas import CheckInput


def test_check_all_fields_save_edit_clear_and_remain_one_to_one(web, session):
    web.post("/clients", data={"name": "Checkテスト"})
    client = session.exec(select(Client)).one()
    web.post(f"/clients/{client.id}/assessments", data={})
    assessment = session.exec(select(Assessment)).one()
    check_id = assessment.check.id
    values = {name: f"{name}の内容\n2行目" for name in CheckInput.model_fields}
    result = web.post(f"/assessments/{assessment.id}/check", data=values, follow_redirects=False)
    assert result.status_code == 303
    session.expire_all()
    assert assessment.check.id == check_id
    for name, value in values.items():
        assert getattr(assessment.check, name) == value
    page = web.get(f"/assessments/{assessment.id}/check/edit")
    assert page.text.count("<textarea") == 14
    assert "health_statusの内容" in page.text
    web.post(f"/assessments/{assessment.id}/check", data={name: "" for name in CheckInput.model_fields})
    session.expire_all()
    assert all(getattr(assessment.check, name) is None for name in CheckInput.model_fields)
    assert len(session.exec(select(AssessmentCheck)).all()) == 1
