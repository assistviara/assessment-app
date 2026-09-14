from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import BooleanObject, DictionaryObject, NameObject
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas

from app.pdf.coordinates import TextBox
from app.pdf import coordinates
from app.pdf.errors import PdfError, PdfInputError
from app.pdf.fonts import ensure_glyphs, register_font
from app.pdf.templates import load_template
from app.pdf.text import draw_text_box, fit_text
from app.form_fields import FIELD_LABELS
from app.pdf.layout import prepare_fields


def render_assessment_pdf(snapshot: dict, template_path: Path, font_path: Path | None, name_box: TextBox | None, *, fields: dict[str, str] | None = None) -> bytes:
    name = snapshot.get("name") if isinstance(snapshot, dict) else None
    if not isinstance(name, str) or not name.strip():
        raise PdfInputError("このAssessmentの作成時氏名が保存されていないため、PDFを生成できません。")
    page = load_template(template_path)
    if name_box is None:
        raise PdfError("氏名の印字座標が未設定です。実帳票での位置確認が必要です。")
    width, height = float(page.mediabox.width), float(page.mediabox.height)
    font_name = register_font(font_path)
    values = {"client_name": name} if fields is None else {**fields, "client_name": name}
    positions = {**coordinates.FIELD_POSITIONS, "client_name": name_box}
    marks, strikes = [], []
    if fields is not None:
        values, positions, marks, strikes = prepare_fields(values)
        positions["client_name"] = name_box
    layouts = []
    errors = []
    for key, value in values.items():
        if not value:
            continue
        label = "氏名" if key == "client_name" else FIELD_LABELS.get(key, key)
        if key.startswith("contact_"):
            _, row, field = key.split("_", 2)
            label = f"緊急連絡先{row}（{dict(name='氏名', relationship='続柄', phone='電話', mobile='携帯', address='住所').get(field, field)}）"
        box = positions.get(key)
        if box is None:
            raise PdfError(f"{label}の印字座標が未設定です。")
        box.validate(width / mm, height / mm)
        try:
            ensure_glyphs(value, font_name, label)
            layouts.append((box, fit_text(value, font_name, box, label)))
        except PdfInputError as error:
            errors.append(str(error))
    if errors:
        raise PdfInputError("\n".join(errors))

    overlay = BytesIO()
    canvas = Canvas(overlay, pagesize=(width, height))
    if fields is not None:
        canvas.setFillColorRGB(1, 1, 1)
        for x, y, w, h in coordinates.CLEAR_REGIONS:
            canvas.rect(x * mm, height - (y + h) * mm, w * mm, h * mm, stroke=0, fill=1)
    canvas.setStrokeColorRGB(0, 0, 0)
    canvas.setLineWidth(0.6)
    for x, y, rx, ry in marks:
        canvas.ellipse((x-rx)*mm, height-(y+ry)*mm, (x+rx)*mm, height-(y-ry)*mm, stroke=1, fill=0)
    for x1, x2, y in strikes:
        canvas.line(x1*mm, height-(y+1)*mm, x2*mm, height-(y-1)*mm)
    for box, layout in layouts:
        draw_text_box(canvas, layout, font_name, box, height)
    canvas.showPage()
    canvas.save()
    writer = PdfWriter()
    page = writer.add_page(page)
    page.merge_page(PdfReader(BytesIO(overlay.getvalue())).pages[0])
    writer.add_metadata({"/Title": "Assessment"})
    writer.root_object[NameObject("/ViewerPreferences")] = DictionaryObject({
        NameObject("/PrintScaling"): NameObject("/None"),
        NameObject("/PickTrayByPDFSize"): BooleanObject(True),
    })
    output = BytesIO()
    writer.write(output)
    return output.getvalue()
