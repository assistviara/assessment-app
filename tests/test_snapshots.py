from sqlmodel import select

from app.models import Assessment, Client


def test_client_changes_do_not_rewrite_past_snapshot_and_new_assessment_captures_current(web, session):
    initial = {"name": "以前の氏名", "gender": "自由入力", "birth_date": "1940-01-02", "postal_code": "001-0000", "address": "以前の住所", "phone": "001-1111", "mobile_phone": "090-1111"}
    web.post("/clients", data=initial)
    client = session.exec(select(Client)).one()
    web.post(f"/clients/{client.id}/assessments", data={})
    old = session.exec(select(Assessment)).one()
    assert old.client_snapshot == initial
    current = {**initial, "name": "現在の氏名", "address": "現在の住所", "phone": "002-2222"}
    web.post(f"/clients/{client.id}", data=current)
    session.refresh(old)
    assert old.client_snapshot == initial
    assert "以前の住所" in web.get(f"/assessments/{old.id}/edit").text
    assert "現在の住所" in web.get(f"/clients/{client.id}/reassessments/new").text
    web.post(f"/clients/{client.id}/reassessments", data={"source_assessment_id": str(old.id)})
    new = session.exec(select(Assessment).where(Assessment.id != old.id)).one()
    assert new.client_id == old.client_id
    assert new.client_snapshot == current and old.client_snapshot == initial
    # Editing an old assessment must not refresh its snapshot from today's Client.
    web.post(f"/assessments/{old.id}", data={"family_request": "訂正"})
    session.refresh(old)
    assert old.client_snapshot == initial
