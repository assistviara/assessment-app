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
    "office_name": TextBox(108.5, 20.5, 77, 4.8, 10, 7),
    "received_date": TextBox(39, 30.0, 75, 4.3, 10, 7),
    "assessor_name": TextBox(147, 30.0, 37, 4.3, 10, 7),
    "gender": TextBox(91, 36, 15, 4.5, 10, 7),
    "birth_date": TextBox(134, 36, 49, 4.5, 10, 7),
    "address": TextBox(38, 43.0, 68, 4.1, 9, 7),
    "phone": TextBox(133, 43.0, 51, 4.1, 9, 7),
    "family_request": TextBox(20, 72, 103.5, 36, 10, 7),
    "family_structure_text": TextBox(127, 72, 57, 36, 10, 7),
    "living_status": TextBox(20, 115, 164, 32, 10, 7),
    "medical_history": TextBox(20, 153.5, 164, 20, 10, 7),
    "primary_doctor": TextBox(37, 177, 147, 5.1, 10, 7),
    "medication_status": TextBox(38, 185.5, 146, 14, 10, 7),
    "adl_independence_level": TextBox(80, 202.0, 104, 3.2, 8.5, 7),
    "dementia_independence_level": TextBox(80, 206.5, 104, 3.2, 8.5, 7),
    "care_application_status": TextBox(148, 211.7, 36, 3.2, 7.5, 6.5),
    "care_level": TextBox(148, 211.7, 36, 3.2, 7.5, 6.5),
    "certification_date": TextBox(37, 216.0, 47, 3.2, 7.5, 6.5),
    "certification_valid_from": TextBox(86, 216.0, 48, 3.2, 7.5, 6.5),
    "certification_valid_to": TextBox(136, 216.0, 48, 3.2, 7.5, 6.5),
    "assessment_reason": TextBox(55.5, 222, 129, 14, 10, 7),
    "assessment_analysis_result": TextBox(55.5, 239.3, 129, 14, 10, 7),
    "disability_certificate_present": TextBox(56, 257, 26, 5.2, 10, 7),
    "disability_certificate_type": TextBox(127, 256.5, 36, 6.2, 9, 7),
    "disability_certificate_grade": TextBox(165, 257, 19, 5.2, 10, 7),
    "current_services": TextBox(55.5, 265, 129, 6.2, 9, 7),
}

# Two contact rows are available on the supplied first sheet.
CONTACT_COLUMNS = {
    "name": (19.5, 33.5), "relationship": (55.5, 9.5),
    "phone": (67, 27.5), "mobile": (97, 33), "address": (133, 51),
}
for row, y_mm in enumerate((55.0, 61.2), start=1):
    for field, (x_mm, width_mm) in CONTACT_COLUMNS.items():
        FIELD_POSITIONS[f"contact_{row}_{field}"] = TextBox(x_mm, y_mm, width_mm, 4.6, 9, 7)

# Only pre-existing entries, never labels, choices or grid lines, are covered.
# Bounds are x/y/width/height in mm from top-left.
CLEAR_REGIONS = ((108, 19.5, 78, 6), (146, 25.5, 51, 8.9))

# Ellipses: centre x/y and horizontal/vertical radii in mm.
CHOICE_MARKS = {
    "gender": {"男性": ((93.3, 38.3, 2.5, 2.8),), "男": ((93.3, 38.3, 2.5, 2.8),),
               "女性": ((105.2, 38.3, 2.5, 2.8),), "女": ((105.2, 38.3, 2.5, 2.8),)},
    "adl_independence_level": {"正常": ((83.8, 203.5, 4.1, 1.9),)},
    "dementia_independence_level": {"正常": ((83.8, 208.3, 4.1, 1.9),)},
    "care_level": {"要支援1": ((60, 212.8, 6, 1.9),), "要支援2": ((60, 212.8, 6, 1.9),)},
    "disability_certificate_present": {"有": ((60.3, 259.1, 3, 3.2),), "無": ((78, 259.1, 3, 3.2),)},
}
for letter, letter_x, first_x, second_x in (("J", 98.8, 105.1, 111), ("A", 122.9, 129, 134.9),
                                             ("B", 146.9, 153.1, 159.1), ("C", 171, 177.1, 183.2)):
    for number, number_x in ((1, first_x), (2, second_x)):
        CHOICE_MARKS["adl_independence_level"][f"{letter}{number}"] = (
            (letter_x, 203.5, 2, 1.9), (number_x, 203.5, 1.9, 1.9))
for value, marks in {
    "I": ((98.8, 208.3, 1.9, 1.9),),
    "IIa": ((110.4, 208.3, 2.1, 1.9), (116.8, 208.3, 1.9, 1.9)),
    "IIb": ((110.4, 208.3, 2.1, 1.9), (122.5, 208.3, 1.9, 1.9)),
    "IIIa": ((135.1, 208.3, 2.5, 1.9), (141, 208.3, 1.9, 1.9)),
    "IIIb": ((135.1, 208.3, 2.5, 1.9), (146.8, 208.3, 1.9, 1.9)),
    "IV": ((158.7, 208.3, 2.5, 1.9),), "M": ((171, 208.3, 2.5, 1.9),),
}.items():
    CHOICE_MARKS["dementia_independence_level"][value] = marks
for number, x in enumerate((92.8, 105, 117, 129, 141), 1):
    CHOICE_MARKS["care_level"][f"要介護{number}"] = ((78, 212.8, 6.3, 1.9), (x, 212.8, 1.9, 1.9))

# Dates retain the printed 年/月/日. Obsolete H is crossed, not covered.
DATE_PART_POSITIONS = {
    "received_date": ((48, 30, 12), (69, 30, 9), (87, 30, 9)),
    "certification_date": ((47.5, 216.1, 6.6), (58, 216.1, 8), (71, 216.1, 7)),
    "certification_valid_from": ((101, 216.1, 7), (112.5, 216.1, 7), (125, 216.1, 7)),
    "certification_valid_to": ((148.5, 216.1, 7), (161, 216.1, 7), (174, 216.1, 7)),
}
DATE_ERA_STRIKES = {
    "certification_date": (45.4, 47.3, 217.5),
    "certification_valid_from": (97.8, 100.1, 217.5),
    "certification_valid_to": (146, 148.2, 217.5),
}
RECEIVED_ERA_STRIKE = (38.5, 46.5, 32)
RECEIVED_WEEKDAY_BOX = TextBox(110, 30, 4, 4, 9, 7)
SUPPORT_LEVEL_BOX = TextBox(148, 211.6, 13, 3.2, 7, 6.5)
SUPPORT_APPLICATION_BOX = TextBox(162, 211.6, 22, 3.2, 7, 6.5)
