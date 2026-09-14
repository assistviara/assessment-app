from datetime import date, datetime
from html.parser import HTMLParser

import pytest
from sqlalchemy import event
from sqlmodel import select

from app.models import Assessment, AssessmentCheck, Client
from app.schemas import CheckInput


class FormValues(HTMLParser):
    """Read actual successful controls, including the 14 textarea values."""

    def __init__(self, html):
        super().__init__()
        self.values = {}
        self.textarea = None
        self.select = None
        self.feed(html)

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == "input" and attrs.get("name"):
            self.values[attrs["name"]] = attrs.get("value", "")
        elif tag == "textarea":
            self.textarea = attrs["name"]
            self.values[self.textarea] = ""
        elif tag == "select":
            self.select = attrs["name"]
            self.values[self.select] = ""
        elif tag == "option" and self.select and "selected" in attrs:
            self.values[self.select] = attrs["value"]

    def handle_data(self, value):
        if self.textarea:
            self.values[self.textarea] += value

    def handle_endtag(self, tag):
        if tag == "textarea":
            self.textarea = None
        elif tag == "select":
            self.select = None


def seed_source(session):
    client = Client(name="再評価テスト", address="現在の住所")
    session.add(client)
    session.flush()
    source = Assessment(
        client_id=client.id, received_date=date(2020, 1, 1),
        created_at=datetime(2020, 1, 1, 12), updated_at=datetime(2020, 1, 2, 12),
        family_request="前回の要望", medical_history="前回の病歴",
        certification_date=date(2019, 12, 1),
        certification_valid_from=date(2020, 1, 1),
        certification_valid_to=date(2030, 12, 31),
    )
    session.add(source)
    session.flush()
    check = AssessmentCheck(
        assessment_id=source.id,
        **{name: f"前回の{name}" for name in CheckInput.model_fields},
    )
    session.add(check)
    session.commit()
    for record in (client, source, check):
        session.refresh(record)
    return client, source, check


def test_reassessment_is_read_only_until_save_and_preserves_source(web, session):
    client, source, check = seed_source(session)
    before_source, before_check = source.model_dump(), check.model_dump()
    before_client = client.model_dump()
    page = web.get(f"/clients/{client.id}/reassessments/new")
    assert page.status_code == 200
    values = FormValues(page.text).values
    assert len(session.exec(select(Assessment)).all()) == 1
    assert len(session.exec(select(AssessmentCheck)).all()) == 1
    assert values["received_date"] == date.today().isoformat()
    assert values["source_assessment_id"] == str(source.id)
    assert values["certification_date"] == "2019-12-01"
    assert values["certification_valid_from"] == "2020-01-01"
    assert values["certification_valid_to"] == "2030-12-31"
    assert "created_at" not in values and "updated_at" not in values
    for name in CheckInput.model_fields:
        assert values[name] == f"前回の{name}"
    values.update(family_request="変更した要望", medical_history="", adl="前回のadl\n追記", skin="", received_date="2026-08-01")
    writes = []

    def capture(_, __, statement, *args):
        if statement.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")):
            writes.append(statement)

    event.listen(web.app.state.engine, "before_cursor_execute", capture)
    try:
        result = web.post(f"/clients/{client.id}/reassessments", data=values, follow_redirects=False)
    finally:
        event.remove(web.app.state.engine, "before_cursor_execute", capture)
    assert result.status_code == 303
    assert len(writes) == 2
    assert all(statement.lstrip().upper().startswith("INSERT") for statement in writes)
    session.expire_all()
    records = session.exec(select(Assessment).order_by(Assessment.id)).all()
    assert len(records) == 2
    new = records[-1]
    assert new.source_assessment_id == source.id
    assert new.client_id == client.id
    assert new.created_at > source.created_at
    assert new.updated_at == new.created_at
    assert new.received_date == date(2026, 8, 1)
    assert new.family_request == "変更した要望"
    assert new.medical_history is None
    assert new.check.id != check.id and new.check.assessment_id == new.id
    assert new.check.adl == "前回のadl\n追記" and new.check.skin is None
    assert source.model_dump() == before_source
    assert check.model_dump() == before_check
    assert client.model_dump() == before_client
    for name in CheckInput.model_fields.keys() - {"adl", "skin"}:
        assert getattr(new.check, name) == getattr(check, name)


def test_latest_uses_created_at_not_received_date_and_forms_keep_their_source(web, session):
    client, source, _ = seed_source(session)
    source.received_date = date(2099, 1, 1)
    session.add(source)
    later = Assessment(client_id=client.id, created_at=datetime(2021, 1, 1), family_request="最新")
    session.add(later)
    other = Client(name="別利用者")
    session.add(other)
    session.flush()
    session.add(Assessment(client_id=other.id, created_at=datetime(2099, 1, 1)))
    session.commit()
    page = web.get(f"/clients/{client.id}/reassessments/new")
    values = FormValues(page.text).values
    assert values["source_assessment_id"] == str(later.id)
    assert values["family_request"] == "最新"
    # Another assessment saved after the form was displayed must not replace its source.
    session.add(Assessment(client_id=client.id, created_at=datetime(2022, 1, 1)))
    session.commit()
    response = web.post(f"/clients/{client.id}/reassessments", data=values, follow_redirects=False)
    assert response.status_code == 303
    saved_id = int(response.headers["location"].split("/")[2])
    assert session.get(Assessment, saved_id).source_assessment_id == later.id


def test_third_reassessment_points_to_second(web, session):
    client, first, _ = seed_source(session)
    ids = [first.id]
    for _ in range(2):
        values = FormValues(web.get(f"/clients/{client.id}/reassessments/new").text).values
        assert int(values["source_assessment_id"]) == ids[-1]
        response = web.post(f"/clients/{client.id}/reassessments", data=values, follow_redirects=False)
        assert response.status_code == 303
        ids.append(int(response.headers["location"].split("/")[2]))
    session.expire_all()
    assert session.get(Assessment, ids[0]).source_assessment_id is None
    assert session.get(Assessment, ids[1]).source_assessment_id == ids[0]
    assert session.get(Assessment, ids[2]).source_assessment_id == ids[1]


@pytest.mark.parametrize("source_id", ["", "bad", "999999"])
def test_invalid_source_does_not_insert(web, session, source_id):
    client, _, _ = seed_source(session)
    response = web.post(f"/clients/{client.id}/reassessments", data={"source_assessment_id": source_id})
    assert response.status_code in (404, 422)
    assert len(session.exec(select(Assessment)).all()) == 1
