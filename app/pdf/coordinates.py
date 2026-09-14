from dataclasses import dataclass
from math import isfinite

from app.pdf.errors import PdfError


@dataclass(frozen=True)
class TextBox:
    """Millimetres from the page's top-left; font sizes are points."""

    x_mm: float
    y_mm: float
    width_mm: float
    height_mm: float
    font_size: float = 12
    min_font_size: float = 8
    alignment: str = "left"

    def validate(self, page_width_mm: float, page_height_mm: float):
        numbers = (self.x_mm, self.y_mm, self.width_mm, self.height_mm, self.font_size, self.min_font_size)
        if not all(isfinite(value) for value in numbers):
            raise PdfError("氏名座標に有限の数値を設定してください。")
        if self.x_mm < 0 or self.y_mm < 0 or self.width_mm <= 0 or self.height_mm <= 0:
            raise PdfError("氏名欄の位置・大きさが不正です。")
        if self.x_mm + self.width_mm > page_width_mm or self.y_mm + self.height_mm > page_height_mm:
            raise PdfError("氏名欄が用紙の範囲を超えています。")
        if not 0 < self.min_font_size <= self.font_size or self.alignment not in {"left", "center", "right"}:
            raise PdfError("氏名欄の文字サイズ・配置設定が不正です。")


# Measured from assessment_form.pdf (SHA256 ffbc062f...28f8fa8).
# The first-row name cell spans approximately x=36.5..78.0, y=34.7..41.6 mm.
FIELD_POSITIONS: dict[str, TextBox | None] = {
    "client_name": TextBox(x_mm=38.5, y_mm=36.0, width_mm=38.0, height_mm=4.5, font_size=12, min_font_size=8),
}
