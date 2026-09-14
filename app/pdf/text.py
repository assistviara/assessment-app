from dataclasses import dataclass

from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics

from app.pdf.coordinates import TextBox
from app.pdf.errors import PdfInputError


@dataclass(frozen=True)
class TextLayout:
    lines: tuple[str, ...]
    font_size: float
    leading: float
    ascent: float


def fit_text(text: str, font_name: str, box: TextBox) -> TextLayout:
    size = box.font_size
    while True:
        ascent, descent = pdfmetrics.getAscentDescent(font_name, size)
        leading = max(size * 1.25, ascent - descent)
        max_lines = int((box.height_mm * mm - (ascent - descent)) // leading) + 1
        lines = []
        fits = max_lines > 0
        for paragraph in text.split("\n"):
            line = ""
            for char in paragraph:
                if pdfmetrics.stringWidth(char, font_name, size) > box.width_mm * mm:
                    fits = False
                    break
                if line and pdfmetrics.stringWidth(line + char, font_name, size) > box.width_mm * mm:
                    lines.append(line)
                    line = ""
                    if len(lines) >= max_lines:
                        fits = False
                        break
                line += char
            if not fits:
                break
            lines.append(line)
            if len(lines) > max_lines:
                fits = False
                break
        if fits:
            return TextLayout(tuple(lines), size, leading, ascent)
        if size <= box.min_font_size:
            raise PdfInputError("氏名が印字枠に収まりません。切り捨てずに生成を中止しました。座標・文字サイズの調整が必要です。")
        size = max(box.min_font_size, size - 0.5)


def draw_text_box(canvas, layout: TextLayout, font_name: str, box: TextBox, page_height: float):
    canvas.setFont(font_name, layout.font_size)
    canvas.setFillColorRGB(0, 0, 0)
    baseline = page_height - box.y_mm * mm - layout.ascent
    for index, line in enumerate(layout.lines):
        width = pdfmetrics.stringWidth(line, font_name, layout.font_size)
        offset = {"left": 0, "center": (box.width_mm * mm - width) / 2, "right": box.width_mm * mm - width}[box.alignment]
        canvas.drawString(box.x_mm * mm + offset, baseline - index * layout.leading, line)
