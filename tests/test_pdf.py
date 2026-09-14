from hashlib import sha256
from html.parser import HTMLParser
from io import BytesIO
from math import ceil, floor

import pypdfium2 as pdfium
import pytest
from PIL import ImageChops
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas
from sqlmodel import select
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.models import Assessment, AssessmentCheck, Client
from app.pdf import coordinates, fonts, templates
from app.pdf.coordinates import TextBox
from app.pdf.errors import PdfError, PdfInputError
from app.pdf.fonts import register_font
from app.pdf.renderer import render_assessment_pdf
from app.pdf.text import fit_text


@pytest.fixture
def pdf_assets(tmp_path, monkeypatch):
    """Synthetic test sheet; never use or overwrite the user's template."""
    template = tmp_path / "synthetic_template.pdf"
    canvas = Canvas(str(template), pagesize=A4)
    canvas.drawString(30, 800, "SYNTHETIC TEST BACKGROUND")
    canvas.rect(20 * mm, A4[1] - 50 * mm, 160 * mm, 20 * mm)
    canvas.showPage()
    canvas.save()
    box = TextBox(30, 35, 100, 10)
    monkeypatch.setattr(templates, "ASSESSMENT_TEMPLATE_PATH", template)
    monkeypatch.setitem(coordinates.FIELD_POSITIONS, "client_name", box)
    return template, box


def create_record(web, session, name="山田 太郎"):
    web.post("/clients", data={"name": name})
    client = session.exec(select(Client)).one()
    web.post(f"/clients/{client.id}/assessments", data={"family_request": "氏名以外は出力しない"})
    return session.exec(select(Assessment)).one()


def raster(data):
    with pdfium.PdfDocument(data) as pdf:
        page = pdf[0]
        bitmap = page.render(scale=2)
        result = bitmap.to_pil().convert("RGB").copy()
        bitmap.close()
        page.close()
    return result


def test_pdf_embeds_japanese_name_only_and_preserves_background(pdf_assets):
    path, box = pdf_assets
    original = path.read_bytes()
    output = render_assessment_pdf({"name": "山田 太郎", "address": "住所は出力しない"}, path, fonts.JAPANESE_FONT_PATH, box)
    assert sha256(path.read_bytes()).digest() == sha256(original).digest()
    pdf = PdfReader(BytesIO(output))
    assert len(pdf.pages) == 1
    page = pdf.pages[0]
    assert float(page.mediabox.width) == pytest.approx(A4[0], abs=0.01)
    assert float(page.mediabox.height) == pytest.approx(A4[1], abs=0.01)
    assert "山田 太郎" in page.extract_text()
    assert "SYNTHETIC TEST BACKGROUND" in page.extract_text()
    assert "住所は出力しない" not in page.extract_text()
    assert pdf.trailer["/Root"]["/ViewerPreferences"]["/PrintScaling"] == "/None"
    descriptors = [font.get_object().get("/FontDescriptor") for font in page["/Resources"]["/Font"].values()]
    assert any(descriptor and descriptor.get_object().get("/FontFile2") for descriptor in descriptors)
    difference = ImageChops.difference(raster(original), raster(output))
    changed = difference.getbbox()
    assert changed is not None
    expected = (floor(box.x_mm * mm * 2), floor(box.y_mm * mm * 2), ceil((box.x_mm + box.width_mm) * mm * 2), ceil((box.y_mm + box.height_mm) * mm * 2))
    assert changed[0] >= expected[0] and changed[1] >= expected[1]
    assert changed[2] <= expected[2] and changed[3] <= expected[3]


def test_http_uses_snapshot_and_does_not_write_db(web, session, pdf_assets):
    assessment = create_record(web, session)
    before = assessment.model_dump()
    web.post(f"/clients/{assessment.client_id}", data={"name": "現在の別氏名"})
    response = web.get(f"/assessments/{assessment.id}/pdf/assessment")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].startswith("inline;")
    assert response.headers["cache-control"] == "no-store"
    text = PdfReader(BytesIO(response.content)).pages[0].extract_text()
    assert "山田 太郎" in text and "現在の別氏名" not in text
    assert "氏名以外は出力しない" in text
    session.refresh(assessment)
    assert assessment.model_dump() == before
    assert len(session.exec(select(Assessment)).all()) == 1
    assert len(session.exec(select(AssessmentCheck)).all()) == 1
    page = web.get(f"/assessments/{assessment.id}/edit").text
    assert f'/assessments/{assessment.id}/pdf/assessment' in page
    assert 'target="_blank"' in page


def test_second_sheet_endpoint_not_implemented(web):
    assert web.get("/assessments/1/pdf/check").status_code == 404


def test_missing_assessment(web):
    response = web.get("/assessments/999/pdf/assessment")
    assert response.status_code == 404
    assert response.json()["detail"] == "対象のデータが見つかりません。"


@pytest.mark.parametrize("prefix", ["", "/care"])
def test_rendered_pdf_link_uses_registered_route_and_correct_assessment(web, session, pdf_assets, prefix):
    class PdfLinkParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.links = []

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == "a" and attrs.get("href", "").endswith("/pdf/assessment"):
                self.links.append(attrs["href"])

    client = Client(id=20, name="現在の氏名")
    session.add(client)
    session.flush()
    session.add_all([
        Assessment(id=101, client_id=client.id, client_snapshot={"name": "前回の氏名"}),
        Assessment(id=202, client_id=client.id, client_snapshot={"name": "対象の氏名"}),
    ])
    session.commit()
    # The fixture already owns this app's lifespan and DB; mounting only tests URL generation.
    if prefix:
        application = FastAPI()
        application.mount(prefix, web.app)
    else:
        application = web.app
    browser = TestClient(application)
    try:
        page = browser.get(f"{prefix}/assessments/202/edit")
        assert page.status_code == 200
        parser = PdfLinkParser()
        parser.feed(page.text)
        assert len(parser.links) == 1
        assert parser.links[0].endswith(f"{prefix}/assessments/202/pdf/assessment")
        response = browser.get(parser.links[0])
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        text = PdfReader(BytesIO(response.content)).pages[0].extract_text()
        assert "対象の氏名" in text
        assert "前回の氏名" not in text and "現在の氏名" not in text
    finally:
        browser.close()


@pytest.mark.parametrize("snapshot", [{}, {"name": ""}, {"name": None}])
def test_missing_snapshot_name_is_not_replaced_by_current_client(web, session, pdf_assets, snapshot):
    assessment = create_record(web, session)
    assessment.client_snapshot = snapshot
    session.add(assessment)
    session.commit()
    response = web.get(f"/assessments/{assessment.id}/pdf/assessment")
    assert response.status_code == 422 and "作成時氏名" in response.text


def test_missing_and_broken_template(web, session, pdf_assets, monkeypatch, tmp_path):
    assessment = create_record(web, session)
    path = tmp_path / "missing.pdf"
    monkeypatch.setattr(templates, "ASSESSMENT_TEMPLATE_PATH", path)
    assert web.get(f"/assessments/{assessment.id}/pdf/assessment").status_code == 503
    path.write_bytes(b"")
    response = web.get(f"/assessments/{assessment.id}/pdf/assessment")
    assert response.status_code == 503 and "読み込めません" in response.text
    path.write_bytes(b"not a pdf")
    assert web.get(f"/assessments/{assessment.id}/pdf/assessment").status_code == 503


def test_unconfigured_coordinate_blocks_output(web, session, pdf_assets, monkeypatch):
    assessment = create_record(web, session)
    monkeypatch.setitem(coordinates.FIELD_POSITIONS, "client_name", None)
    response = web.get(f"/assessments/{assessment.id}/pdf/assessment")
    assert response.status_code == 503 and "座標が未設定" in response.text


@pytest.mark.parametrize("kind", ["unconfigured", "missing", "broken"])
def test_font_errors_are_explicit(web, session, pdf_assets, monkeypatch, tmp_path, kind):
    assessment = create_record(web, session)
    path = tmp_path / "font.ttf"
    if kind == "broken":
        path.write_bytes(b"not a font")
    monkeypatch.setattr(fonts, "JAPANESE_FONT_PATH", None if kind == "unconfigured" else path)
    response = web.get(f"/assessments/{assessment.id}/pdf/assessment")
    assert response.status_code == 503 and "フォント" in response.text


def test_unsupported_glyph_is_not_silently_replaced(pdf_assets):
    path, box = pdf_assets
    with pytest.raises(PdfInputError, match="未対応"):
        render_assessment_pdf({"name": "山田\U0001f600"}, path, fonts.JAPANESE_FONT_PATH, box)


def test_text_wraps_shrinks_and_never_truncates(pdf_assets):
    path, _ = pdf_assets
    font = register_font(fonts.JAPANESE_FONT_PATH)
    name = "山田太郎" * 3
    layout = fit_text(name, font, TextBox(20, 20, 30, 20))
    assert len(layout.lines) > 1 and "".join(layout.lines) == name
    small = fit_text("山田太郎", font, TextBox(20, 20, 14, 4))
    assert small.font_size < 12 and "".join(small.lines) == "山田太郎"
    with pytest.raises(PdfInputError, match="収まりません"):
        render_assessment_pdf({"name": "山田" * 1000}, path, fonts.JAPANESE_FONT_PATH, TextBox(20, 20, 10, 3))


@pytest.mark.parametrize("box", [TextBox(-1, 0, 10, 10), TextBox(200, 290, 20, 20), TextBox(0, 0, 0, 10), TextBox(0, 0, 10, 10, 8, 12), TextBox(float("nan"), 0, 10, 10)])
def test_invalid_coordinates_rejected(pdf_assets, box):
    path, _ = pdf_assets
    with pytest.raises(PdfError):
        render_assessment_pdf({"name": "山田"}, path, fonts.JAPANESE_FONT_PATH, box)


@pytest.mark.parametrize("kind", ["landscape", "two_pages", "encrypted", "crop"])
def test_unsupported_template_rejected(pdf_assets, tmp_path, kind):
    path, box = pdf_assets
    writer = PdfWriter()
    if kind == "landscape":
        writer.add_blank_page(*landscape(A4))
    else:
        writer.add_page(PdfReader(path).pages[0])
        if kind == "two_pages":
            writer.add_blank_page(*A4)
        elif kind == "encrypted":
            writer.encrypt("test-password")
        elif kind == "crop":
            writer.pages[0].cropbox.upper_right = (500, 700)
    target = tmp_path / "unsupported.pdf"
    writer.write(target)
    with pytest.raises(PdfError):
        render_assessment_pdf({"name": "山田"}, target, fonts.JAPANESE_FONT_PATH, box)


def test_actual_template_and_coordinate_ready():
    box = coordinates.FIELD_POSITIONS["client_name"]
    assert box is not None
    original = templates.ASSESSMENT_TEMPLATE_PATH.read_bytes()
    output = render_assessment_pdf({"name": "山田 太郎"}, templates.ASSESSMENT_TEMPLATE_PATH, fonts.JAPANESE_FONT_PATH, box)
    assert "山田 太郎" in PdfReader(BytesIO(output)).pages[0].extract_text()
    assert templates.ASSESSMENT_TEMPLATE_PATH.read_bytes() == original
    changed = ImageChops.difference(raster(original), raster(output)).getbbox()
    assert changed is not None
    assert changed[0] >= floor(box.x_mm * mm * 2)
    assert changed[1] >= floor(box.y_mm * mm * 2)
    assert changed[2] <= ceil((box.x_mm + box.width_mm) * mm * 2)
    assert changed[3] <= ceil((box.y_mm + box.height_mm) * mm * 2)
