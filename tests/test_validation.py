import pytest
from sqlmodel import select

from app.choices import SELECT_CHOICES
from app.models import Assessment, Client
from app.schemas import AssessmentInput


@pytest.mark.parametrize("values", [{}, {"name": ""}, {"name": "　 "}, {"name": "日付エラー", "birth_date": "2026-02-30"}, {"name": "日付形式", "birth_date": "20260914"}])
def test_client_invalid_input_is_not_saved(web, session, values):
    response = web.post("/clients", data=values)
    assert response.status_code == 422
    assert session.exec(select(Client)).all() == []


@pytest.mark.parametrize("invalid", [
    {"received_date": "2026-02-30"}, {"certification_date": "2026/09/14"},
    {"certification_valid_from": "2026-09-15", "certification_valid_to": "2026-09-14"},
    {"adl_independence_level": "自由入力"}, {"dementia_independence_level": "V"},
    {"care_level": "care_6"}, {"disability_certificate_present": "unknown"},
])
def test_invalid_assessment_create_and_update_do_not_write(web, session, invalid):
    web.post("/clients", data={"name": "入力検証"})
    client = session.exec(select(Client)).one()
    response = web.post(f"/clients/{client.id}/assessments", data={"family_request": "入力を保持", **invalid})
    assert response.status_code == 422 and "入力を保持" in response.text
    assert session.exec(select(Assessment)).all() == []
    web.post(f"/clients/{client.id}/assessments", data={"family_request": "保存済み"})
    assessment = session.exec(select(Assessment)).one()
    before = assessment.model_dump()
    assert web.post(f"/assessments/{assessment.id}", data=invalid).status_code == 422
    session.refresh(assessment)
    assert assessment.model_dump() == before


@pytest.mark.parametrize("value,expected", [("", None), ("true", True), ("false", False)])
def test_certificate_three_states_round_trip(web, session, value, expected):
    web.post("/clients", data={"name": "手帳テスト"})
    client = session.exec(select(Client)).one()
    web.post(f"/clients/{client.id}/assessments", data={"disability_certificate_present": value})
    assessment = session.exec(select(Assessment)).one()
    assert assessment.disability_certificate_present is expected
    html = web.get(f"/assessments/{assessment.id}/edit").text
    if value:
        assert f'value="{value}" selected' in html


def test_all_defined_choices_and_optional_dates():
    for field, choices in SELECT_CHOICES.items():
        for value in choices:
            assert getattr(AssessmentInput.model_validate({field: value}), field) == value
    assert AssessmentInput.model_validate({"certification_valid_from": "2026-09-14"}).certification_valid_to is None


@pytest.mark.parametrize("path", ["/clients/999", "/clients/999/edit", "/clients/999/assessments/new", "/assessments/999/edit", "/assessments/999/check/edit"])
def test_missing_ids_return_404(web, path):
    assert web.get(path).status_code == 404
