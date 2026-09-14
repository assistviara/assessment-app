from datetime import date
from io import BytesIO
import re

import pytest
from pypdf import PdfReader
from sqlalchemy import event

from app.models import Assessment, AssessmentCheck, Client, EmergencyContact
from app.pdf.mapping import assessment_fields
from app.pdf.layout import prepare_fields
from app.pdf.coordinates import CHOICE_MARKS


SNAPSHOT = {
    "name": "山田 太郎", "gender": "男性", "birth_date": "1940-02-03",
    "postal_code": "100-0001", "address": "東京都千代田区試験町一丁目",
    "phone": "03-1111-2222", "mobile_phone": "090-3333-4444",
}
ASSESSMENT_VALUES = {
    "received_date": date(2026, 9, 14), "assessor_name": "佐藤 花子", "office_name": "試験ケア支援事業所",
    "family_request": "住み慣れた自宅で生活したい。家族は安全な入浴を希望している。",
    "family_structure_text": "妻と二人暮らし。長男は近隣に住み、週末に訪問する。",
    "living_status": "戸建て住宅の一階を使用。玄関に段差がある。",
    "medical_history": "高血圧の治療を継続。昨年転倒による入院歴あり。",
    "primary_doctor": "試験内科医院　田中医師",
    "medication_status": "朝夕に内服。飲み忘れ防止のため家族が確認する。",
    "adl_independence_level": "A1", "dementia_independence_level": "IIa",
    "care_application_status": "更新申請中", "care_level": "care_3",
    "certification_date": date(2026, 8, 1), "certification_valid_from": date(2026, 9, 1),
    "certification_valid_to": date(2027, 8, 31),
    "assessment_reason": "状態変化に伴う再評価",
    "assessment_analysis_result": "転倒予防と服薬管理を支援し、自宅生活の継続を目指す。",
    "disability_certificate_present": True,
    "disability_certificate_type": "肢体不自由", "disability_certificate_grade": "二級",
    "current_services": "訪問介護、通所介護、福祉用具貸与",
}


@pytest.fixture
def full_record(session):
    client = Client(name="現在の別氏名", address="現在の別住所", phone="00-0000-0000")
    session.add(client)
    session.flush()
    record = Assessment(client_id=client.id, client_snapshot=dict(SNAPSHOT), **ASSESSMENT_VALUES)
    session.add(record)
    session.flush()
    session.add(AssessmentCheck(assessment_id=record.id, health_status="チェックシート専用データ"))
    session.commit()
    session.refresh(record)
    return record


def compact(value):
    return re.sub(r"\s+", "", str(value))


def test_all_saved_first_sheet_fields_are_in_pdf(web, session, full_record):
    before = full_record.model_dump()
    statements = []

    def capture(_, __, statement, *args):
        if statement.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "REPLACE")):
            statements.append(statement)

    event.listen(web.app.state.engine, "before_cursor_execute", capture)
    try:
        response = web.get(f"/assessments/{full_record.id}/pdf/assessment")
    finally:
        event.remove(web.app.state.engine, "before_cursor_execute", capture)
    assert response.status_code == 200, response.text if response.status_code != 200 else ""
    output = compact(PdfReader(BytesIO(response.content)).pages[0].extract_text())
    for field, value in SNAPSHOT.items():
        if field == "gender":
            continue  # A visible circle selects the original raster text.
        assert compact(value) in output
    for field, value in ASSESSMENT_VALUES.items():
        if field in CHOICE_MARKS or isinstance(value, date):
            continue
        assert compact(value) in output, field
    assert "care_3" not in output and "True" not in output
    texts, _, marks, strikes = prepare_fields(assessment_fields(full_record))
    assert len(marks) == 8 and len(strikes) == 3
    assert texts['received_date_year'] == '8'
    assert texts['certification_valid_to_year'] == '2027'
    assert "現在の別氏名" not in output and "現在の別住所" not in output
    assert "00-0000-0000" not in output and "チェックシート専用データ" not in output
    assert statements == []
    session.refresh(full_record)
    assert full_record.model_dump() == before


@pytest.mark.parametrize("present,expected", [(None, ""), (False, "無"), (True, "有")])
def test_nullable_certificate_and_empty_fields(full_record, present, expected):
    full_record.disability_certificate_present = present
    full_record.family_request = None
    values = assessment_fields(full_record)
    assert values["disability_certificate_present"] == expected
    assert values["family_request"] == ""


def test_long_free_text_is_wrapped_without_loss(web, session, full_record):
    value = "本人は自宅生活の継続を希望。家族は安全な移動と入浴の支援を希望。" * 8
    full_record.family_request = value
    session.add(full_record)
    session.commit()
    response = web.get(f"/assessments/{full_record.id}/pdf/assessment")
    assert response.status_code == 200
    assert compact(value) in compact(PdfReader(BytesIO(response.content)).pages[0].extract_text())


def test_overflow_identifies_the_field_and_does_not_save(web, session, full_record):
    full_record.primary_doctor = "非常に長い主治医情報" * 1000
    session.add(full_record)
    session.commit()
    session.refresh(full_record)
    before = full_record.model_dump()
    response = web.get(f"/assessments/{full_record.id}/pdf/assessment")
    assert response.status_code == 422
    assert "主治医" in response.text and "切り捨てず" in response.text
    session.refresh(full_record)
    assert full_record.model_dump() == before


def test_read_only_mapping_never_falls_back_to_current_client(full_record):
    full_record.client_snapshot = {"name": "保存時の氏名"}
    values = assessment_fields(full_record)
    assert values["address"] == "" and values["phone"] == ""
    assert values["birth_date"] == "" and values["gender"] == ""


def test_current_contacts_never_change_historical_pdf(web, session, full_record):
    url = f"/assessments/{full_record.id}/pdf/assessment"
    before = PdfReader(BytesIO(web.get(url).content)).pages[0].get_contents().get_data()
    contact = EmergencyContact(client_id=full_record.client_id, name="現在の緊急連絡先", phone="099-555-1111")
    session.add(contact)
    session.commit()
    for name in ("現在の緊急連絡先", "変更後の連絡先"):
        contact.name = name
        session.add(contact)
        session.commit()
        response = web.get(url)
        assert response.status_code == 200
        page = PdfReader(BytesIO(response.content)).pages[0]
        assert page.get_contents().get_data() == before
        assert name not in page.extract_text()


@pytest.mark.parametrize('field,value', [(field, value) for field, choices in CHOICE_MARKS.items() for value in choices])
def test_all_choices_draw_the_selected_ellipses(field, value, monkeypatch):
    from app.pdf.renderer import render_assessment_pdf
    from app.pdf.coordinates import FIELD_POSITIONS
    from app.pdf.fonts import JAPANESE_FONT_PATH
    from app.pdf.templates import ASSESSMENT_TEMPLATE_PATH
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.lib.units import mm
    from pytest import approx
    calls = []
    original = Canvas.ellipse
    def capture(self, *args, **kwargs):
        calls.append(args)
        return original(self, *args, **kwargs)
    monkeypatch.setattr(Canvas, 'ellipse', capture)
    content = render_assessment_pdf(SNAPSHOT, ASSESSMENT_TEMPLATE_PATH, JAPANESE_FONT_PATH,
                                    FIELD_POSITIONS['client_name'], fields={field: value})
    height = float(PdfReader(BytesIO(content)).pages[0].mediabox.height)
    expected = CHOICE_MARKS[field][value]
    assert len(calls) == len(expected)
    for actual, (x, y, rx, ry) in zip(calls, expected):
        assert actual == approx(((x-rx)*mm, height-(y+ry)*mm, (x+rx)*mm, height-(y-ry)*mm))


def test_pre_reiwa_date_is_not_mislabelled():
    texts, _, _, strikes = prepare_fields({'received_date': '2018-04-30'})
    assert texts['received_date_year'] == '2018'
    assert len(strikes) == 1


def test_empty_choices_have_no_marks():
    _, _, marks, _ = prepare_fields({key: '' for key in CHOICE_MARKS})
    assert marks == []


def test_white_cover_is_limited_to_existing_entries(web, full_record):
    from app.pdf.coordinates import CLEAR_REGIONS
    from reportlab.lib.units import mm
    response = web.get(f'/assessments/{full_record.id}/pdf/assessment')
    page = PdfReader(BytesIO(response.content)).pages[0]
    height = float(page.mediabox.height)
    operations = page.get_contents().operations
    filled_rectangles = []
    white = False
    for operands, operator in operations:
        if operator == b'rg':
            white = list(operands) == [1, 1, 1]
        if white and operator == b're':
            filled_rectangles.append(list(map(float, operands)))
    assert len(filled_rectangles) == 2
    for rectangle, (x, y, w, h) in zip(filled_rectangles, CLEAR_REGIONS):
        assert rectangle == pytest.approx([x*mm, height-(y+h)*mm, w*mm, h*mm], abs=.001)


def test_background_ink_is_preserved_outside_entry_masks(web, full_record):
    import pypdfium2 as pdfium
    from PIL import ImageChops, ImageDraw
    from app.pdf.templates import ASSESSMENT_TEMPLATE_PATH
    from app.pdf.coordinates import CLEAR_REGIONS
    from reportlab.lib.units import mm
    def render(data):
        with pdfium.PdfDocument(data) as doc:
            page = doc[0]
            bitmap = page.render(scale=2)
            result = bitmap.to_pil().convert('L')
            bitmap.close()
            page.close()
            return result
    before = render(ASSESSMENT_TEMPLATE_PATH)
    after = render(web.get(f'/assessments/{full_record.id}/pdf/assessment').content)
    erased = ImageChops.subtract(after, before)
    drawing = ImageDraw.Draw(erased)
    for x, y, w, h in CLEAR_REGIONS:
        drawing.rectangle((int(x*mm*2)-2, int(y*mm*2)-2, int((x+w)*mm*2)+2, int((y+h)*mm*2)+2), fill=0)
    assert erased.getextrema()[1] <= 5
