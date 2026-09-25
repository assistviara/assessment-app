from io import BytesIO

import pytest
import pypdfium2 as pdfium
from PIL import ImageChops
from pypdf import PdfReader
from sqlalchemy import event

from app.models import Assessment, AssessmentCheck, Client
from app.pdf import coordinates, fonts, templates
from app.pdf.fonts import register_font
from app.pdf.renderer import render_checksheet_pdf
from app.pdf.text import fit_text
from app.pdf.mapping import CHECK_FIELD_LABELS


@pytest.fixture
def record(session):
    client = Client(name="現在の利用者")
    session.add(client)
    session.flush()
    assessment = Assessment(client_id=client.id, client_snapshot={"name": "保存時の氏名"})
    session.add(assessment)
    session.flush()
    check = AssessmentCheck(assessment_id=assessment.id, health_status="血圧は安定。\n通院を継続している。")
    session.add(check)
    session.commit()
    session.refresh(assessment)
    return assessment


def raster(data):
    with pdfium.PdfDocument(data) as doc:
        page = doc[0]
        bitmap = page.render(scale=2)
        result = bitmap.to_pil().convert("RGB")
        bitmap.close()
        page.close()
        return result


def extract(response):
    assert response.status_code == 200
    return PdfReader(BytesIO(response.content)).pages[0].extract_text().replace("\n", "")


def test_saved_health_only_inline_read_only_and_history(web, session, record):
    other = Assessment(client_id=record.client_id, client_snapshot={"name": "別の履歴"})
    session.add(other)
    session.flush()
    session.add(AssessmentCheck(assessment_id=other.id, health_status="別の評価内容"))
    session.commit()
    session.refresh(record)
    before = record.model_dump(), record.check.model_dump()
    template_before = templates.CHECKSHEET_TEMPLATE_PATH.read_bytes()
    statements = []

    def capture(_, __, statement, *args):
        if statement.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "REPLACE")):
            statements.append(statement)

    event.listen(web.app.state.engine, "before_cursor_execute", capture)
    try:
        response = web.get(f"/assessments/{record.id}/pdf/check")
    finally:
        event.remove(web.app.state.engine, "before_cursor_execute", capture)
    assert extract(response) == record.check.health_status.replace("\n", "")
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].startswith("inline;")
    assert response.headers["cache-control"] == "no-store"
    assert len(PdfReader(BytesIO(response.content)).pages) == 1
    assert statements == []
    session.refresh(record)
    session.refresh(record.check)
    assert (record.model_dump(), record.check.model_dump()) == before
    assert templates.CHECKSHEET_TEMPLATE_PATH.read_bytes() == template_before
    assert extract(web.get(f"/assessments/{other.id}/pdf/check")) == "別の評価内容"
    page = web.get(f"/assessments/{record.id}/check/edit")
    assert f"/assessments/{record.id}/pdf/check" in page.text
    assert "保存済みのチェックシート14項目" in page.text


@pytest.mark.parametrize("value", [None, ""])
def test_empty_health_preserves_entire_background(web, session, record, value):
    record.check.health_status = value
    session.add(record.check)
    session.commit()
    response = web.get(f"/assessments/{record.id}/pdf/check")
    assert extract(response) == ""
    assert ImageChops.difference(raster(templates.CHECKSHEET_TEMPLATE_PATH), raster(response.content)).getbbox() is None


def test_missing_check_is_explicit(web, session, record):
    session.delete(record.check)
    session.commit()
    response = web.get(f"/assessments/{record.id}/pdf/check")
    assert response.status_code == 422
    assert "AssessmentCheckが保存されていない" in response.text


@pytest.mark.parametrize("value", ["血圧は安定。\n定期通院を継続。", "体調を確認し、定期通院と服薬を継続している。" * 6], ids=["multiline", "shrink"])
def test_japanese_layout_background_and_long_text(value):
    box = coordinates.CHECK_FIELD_POSITIONS["health_status"]
    layout = fit_text(value, register_font(fonts.JAPANESE_FONT_PATH), box, "健康状態")
    if len(value) > 100:
        assert layout.font_size < box.font_size
    output = render_checksheet_pdf({"health_status": value}, templates.CHECKSHEET_TEMPLATE_PATH, fonts.JAPANESE_FONT_PATH)
    page = PdfReader(BytesIO(output)).pages[0]
    assert page.extract_text().replace("\n", "") == value.replace("\n", "")
    assert any("/FontFile2" in font.get_object().get("/FontDescriptor", {}) for font in page["/Resources"]["/Font"].values())
    difference = ImageChops.difference(raster(templates.CHECKSHEET_TEMPLATE_PATH), raster(output))
    bounds = difference.getbbox()
    assert bounds is not None
    # Independently measured cell bounds in a 2x raster, inset from the grid.
    assert 353 <= bounds[0] < bounds[2] <= 1086
    assert 116 <= bounds[1] < bounds[3] <= 214


@pytest.mark.parametrize("value,message", [("健康状態" * 1000, "切り捨てず"), ("体調\U0001f600", "フォント未対応")], ids=["overflow", "glyph"])
def test_invalid_text_returns_field_error_without_write(web, session, record, value, message):
    record.check.health_status = value
    session.add(record.check)
    session.commit()
    before = record.check.model_dump()
    response = web.get(f"/assessments/{record.id}/pdf/check")
    assert response.status_code == 422
    assert "健康状態" in response.text and message in response.text
    session.refresh(record.check)
    assert record.check.model_dump() == before


@pytest.mark.parametrize("kind", ["missing", "broken", "coordinate", "font"])
def test_configuration_errors(web, record, monkeypatch, tmp_path, kind):
    if kind in {"missing", "broken"}:
        path = tmp_path / "check.pdf"
        if kind == "broken":
            path.write_bytes(b"not pdf")
        monkeypatch.setattr(templates, "CHECKSHEET_TEMPLATE_PATH", path)
    elif kind == "coordinate":
        monkeypatch.setitem(coordinates.CHECK_FIELD_POSITIONS, "health_status", None)
    else:
        monkeypatch.setattr(fonts, "JAPANESE_FONT_PATH", None)
    assert web.get(f"/assessments/{record.id}/pdf/check").status_code == 503


# Row edges measured on the source raster at scale=1.5, independent of TextBox.
ROWS = [
    ("health_status", "健康状態", 83, 163),
    ("adl", "ADL", 163, 243),
    ("iadl", "IADL", 243, 322),
    ("cognition", "認知", 322, 402),
    ("communication", "コミュニケーション能力", 402, 481),
    ("social_relationship", "社会との関わり", 481, 561),
    ("elimination", "排尿・排便", 561, 640),
    ("skin", "褥瘡・皮膚の問題", 640, 720),
    ("oral_hygiene", "口腔衛生", 720, 799),
    ("nutrition", "食事摂取", 799, 879),
    ("behavior", "問題行動", 879, 958),
    ("caregiving_capacity", "介護力", 958, 1038),
    ("home_environment", "居住環境", 1038, 1118),
    ("special_conditions", "特別な状況", 1118, 1198),
]


def test_explicit_mapping_and_approved_health_position():
    assert CHECK_FIELD_LABELS == {key: label for key, label, _, _ in ROWS}
    assert set(coordinates.CHECK_FIELD_POSITIONS) == set(CHECK_FIELD_LABELS)
    assert coordinates.CHECK_FIELD_POSITIONS['health_status'] == coordinates.TextBox(64, 22, 126, 14, 10, 7)


@pytest.mark.parametrize('key,label,top,bottom', ROWS, ids=[row[0] for row in ROWS])
def test_every_row_wraps_shrinks_and_stays_inside_source_cell(key, label, top, bottom):
    value = '体調を確認し、定期通院と服薬を継続している。' * 6
    box = coordinates.CHECK_FIELD_POSITIONS[key]
    layout = fit_text(value, register_font(fonts.JAPANESE_FONT_PATH), box, label)
    assert layout.font_size < 10 and len(layout.lines) > 1
    output = render_checksheet_pdf({key: value}, templates.CHECKSHEET_TEMPLATE_PATH, fonts.JAPANESE_FONT_PATH)
    assert PdfReader(BytesIO(output)).pages[0].extract_text().replace('\n', '') == value
    bounds = ImageChops.difference(raster(templates.CHECKSHEET_TEMPLATE_PATH), raster(output)).getbbox()
    assert bounds is not None
    assert 353 <= bounds[0] < bounds[2] <= 1086
    assert (top + 3) * 2 / 1.5 <= bounds[1] < bounds[3] <= (bottom - 3) * 2 / 1.5


@pytest.mark.parametrize('key,label,top,bottom', ROWS, ids=[row[0] for row in ROWS])
@pytest.mark.parametrize('kind', ['overflow', 'glyph', 'empty'])
def test_each_saved_field_error_or_empty(web, session, record, key, label, top, bottom, kind):
    for field in CHECK_FIELD_LABELS:
        setattr(record.check, field, None)
    setattr(record.check, key, {'overflow': '確認事項' * 1000, 'glyph': '\U0001f600', 'empty': ''}[kind])
    session.add(record.check)
    session.commit()
    before = record.check.model_dump()
    response = web.get(f'/assessments/{record.id}/pdf/check')
    if kind == 'empty':
        assert extract(response) == ''
    else:
        assert response.status_code == 422
        assert label in response.text
        assert ('切り捨てず' if kind == 'overflow' else 'フォント未対応') in response.text
    session.refresh(record.check)
    assert record.check.model_dump() == before


def test_all_saved_rows_history_isolation_and_read_only(web, session, record):
    values = {key: f'{label}の確認用記録。\n保存された内容です。' for key, label, _, _ in ROWS}
    for key, value in values.items():
        setattr(record.check, key, value)
    session.add(record.check)
    # Earlier/later IDs must never supply missing values to the target.
    for marker in ('過去の別記録', '未来の別記録'):
        other = Assessment(client_id=record.client_id, client_snapshot={'name': marker})
        session.add(other)
        session.flush()
        session.add(AssessmentCheck(assessment_id=other.id, **{key: marker for key in values}))
    record.client.name = '現在のClientから混入禁止'
    session.add(record.client)
    session.commit()
    session.refresh(record)
    before = record.model_dump(), record.check.model_dump()
    statements = []
    def capture(_, __, statement, *args):
        if statement.lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE', 'REPLACE')):
            statements.append(statement)
    event.listen(web.app.state.engine, 'before_cursor_execute', capture)
    try:
        response = web.get(f'/assessments/{record.id}/pdf/check')
    finally:
        event.remove(web.app.state.engine, 'before_cursor_execute', capture)
    assert extract(response) == ''.join(values.values()).replace('\n', '')
    session.refresh(record)
    session.refresh(record.check)
    assert (record.model_dump(), record.check.model_dump()) == before
    assert statements == []
    # Keep other rows populated while clearing one: no fallback from other checks.
    record.check.adl = None
    session.add(record.check)
    session.commit()
    values['adl'] = ''
    assert extract(web.get(f'/assessments/{record.id}/pdf/check')) == ''.join(values.values()).replace('\n', '')
