from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import BooleanObject, DictionaryObject, NameObject
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas

from app.pdf.coordinates import TextBox
from app.pdf.errors import PdfError, PdfInputError
from app.pdf.fonts import ensure_glyphs, register_font
from app.pdf.templates import load_template
from app.pdf.text import draw_text_box, fit_text


def render_assessment_pdf(snapshot: dict, template_path: Path, font_path: Path | None, name_box: TextBox | None) -> bytes:
    name = snapshot.get("name") if isinstance(snapshot, dict) else None
    if not isinstance(name, str) or not name.strip():
        raise PdfInputError("このAssessmentの作成時氏名が保存されていないため、PDFを生成できません。")
    page = load_template(template_path)
    if name_box is None:
        raise PdfError("氏名の印字座標が未設定です。実帳票での位置確認が必要です。")
    width, height = float(page.mediabox.width), float(page.mediabox.height)
    name_box.validate(width / mm, height / mm)
    font_name = register_font(font_path)
    ensure_glyphs(name, font_name)
    layout = fit_text(name, font_name, name_box)

    overlay = BytesIO()
    canvas = Canvas(overlay, pagesize=(width, height))
    draw_text_box(canvas, layout, font_name, name_box, height)
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
