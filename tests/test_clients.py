from datetime import datetime

from sqlmodel import select

from app.models import Assessment, Client


def test_client_create_update_and_search(web, session):
    result = web.post("/clients", data={"name": "山田 太郎", "phone": "001-2345", "birth_date": "1940-01-02"}, follow_redirects=False)
    assert result.status_code == 303
    client = session.exec(select(Client)).one()
    created = client.created_at
    assert client.phone == "001-2345"
    assert "山田 太郎" in web.get(result.headers["location"]).text
    assert 'value="001-2345"' in web.get(f"/clients/{client.id}/edit").text
    result = web.post(f"/clients/{client.id}", data={"name": "山田 花子", "phone": ""}, follow_redirects=False)
    assert result.status_code == 303
    session.refresh(client)
    assert client.name == "山田 花子" and client.phone is None
    assert client.created_at == created and client.updated_at >= created
    assert "山田 花子" in web.get("/clients", params={"q": "山田"}).text
    assert "山田 花子" not in web.get("/clients", params={"q": "存在しない"}).text
    assert "山田 花子" not in web.get("/clients", params={"q": "%"}).text


def test_latest_display_and_history_are_per_client_and_use_creation_time(web, session):
    client, other = Client(name="対象利用者"), Client(name="別利用者")
    session.add_all([client, other])
    session.flush()
    session.add_all([
        Assessment(client_id=client.id, created_at=datetime(2020, 1, 1), received_date=datetime(2099, 1, 1).date(), assessment_reason="古い理由"),
        Assessment(client_id=client.id, created_at=datetime(2021, 3, 10), updated_at=datetime(2099, 1, 1), assessment_reason="新しい理由"),
        Assessment(client_id=other.id, created_at=datetime(2025, 1, 1), assessment_reason="別利用者の理由"),
    ])
    session.commit()
    html = web.get("/clients", params={"q": "対象利用者"}).text
    assert "2021-03-10" in html and "2099-01-01" not in html
    detail = web.get(f"/clients/{client.id}").text
    assert detail.index("新しい理由") < detail.index("古い理由")
    assert "別利用者の理由" not in detail


def test_html_escapes_user_content(web):
    web.post("/clients", data={"name": '<script>alert("test")</script>'})
    html = web.get("/clients").text
    assert "<script>" not in html and "&lt;script&gt;" in html
