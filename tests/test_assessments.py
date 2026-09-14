from sqlmodel import select

from app.models import Assessment, AssessmentCheck, Client


def test_initial_create_and_edit_preserve_identity_and_check(web, session):
    web.post("/clients", data={"name": "初回テスト"})
    client = session.exec(select(Client)).one()
    assert web.get(f"/clients/{client.id}/assessments/new").status_code == 200
    result = web.post(f"/clients/{client.id}/assessments", data={"family_request": "初回要望", "health_status": "初回Check"}, follow_redirects=False)
    assert result.status_code == 303
    assessment = session.exec(select(Assessment)).one()
    assert assessment.source_assessment_id is None
    assert assessment.check.health_status == "初回Check"
    assert len(session.exec(select(AssessmentCheck)).all()) == 1
    created, snapshot = assessment.created_at, dict(assessment.client_snapshot)
    result = web.post(f"/assessments/{assessment.id}", data={"family_request": "訂正", "created_at": "1900-01-01", "source_assessment_id": "999", "client_id": "999", "client_snapshot": "invalid"}, follow_redirects=False)
    assert result.status_code == 303
    session.refresh(assessment)
    assert assessment.family_request == "訂正"
    assert assessment.created_at == created and assessment.updated_at >= created
    assert assessment.source_assessment_id is None and assessment.client_id == client.id
    assert assessment.client_snapshot == snapshot
    assert assessment.check.health_status == "初回Check"
    assert len(session.exec(select(Assessment)).all()) == 1


def test_empty_initial_assessment_has_exactly_one_empty_check(web, session):
    web.post("/clients", data={"name": "任意入力"})
    client = session.exec(select(Client)).one()
    assert web.post(f"/clients/{client.id}/assessments", data={}, follow_redirects=False).status_code == 303
    assessment = session.exec(select(Assessment)).one()
    assert assessment.check is not None and assessment.check.health_status is None
    assert len(session.exec(select(AssessmentCheck)).all()) == 1


def test_second_assessment_must_use_reassessment_flow(web, session):
    web.post("/clients", data={"name": "初回のみ"})
    client = session.exec(select(Client)).one()
    web.post(f"/clients/{client.id}/assessments", data={})
    response = web.get(f"/clients/{client.id}/assessments/new", follow_redirects=False)
    assert response.status_code == 303 and response.headers["location"].endswith("/reassessments/new")
    assert web.post(f"/clients/{client.id}/assessments", data={}).status_code == 409
    assert len(session.exec(select(Assessment)).all()) == 1
