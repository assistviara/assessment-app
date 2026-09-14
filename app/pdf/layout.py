"""Turn saved values into text and marks without touching model state."""

from datetime import date

from app.pdf import coordinates as c
from app.pdf.coordinates import TextBox
from app.pdf.errors import PdfInputError


def prepare_fields(values):
    texts = dict(values)
    positions = dict(c.FIELD_POSITIONS)
    marks, strikes = [], []
    for field, choices in c.CHOICE_MARKS.items():
        value = texts.get(field, "")
        if value in choices:
            marks.extend(choices[value])
            texts.pop(field)
        elif value and field != "gender":
            raise PdfInputError(f"{field}の保存値に対応する選択肢がありません。")
        elif value:
            # Free-input gender values cannot be written over 男・女.
            raise PdfInputError("性別の保存値に対応する選択肢が元帳票にありません。")
    level = values.get("care_level", "")
    if level.startswith("要支援"):
        texts["care_level"] = level
        # Share the spare area with the free-input application status.
        positions["care_level"] = c.SUPPORT_LEVEL_BOX
        positions["care_application_status"] = c.SUPPORT_APPLICATION_BOX
    for field, boxes in c.DATE_PART_POSITIONS.items():
        value = texts.pop(field, "")
        if not value:
            continue
        try:
            parsed = date.fromisoformat(value)
        except ValueError as error:
            raise PdfInputError(f"{field}の日付を解釈できません。") from error
        year = parsed.year
        if field == "received_date":
            if parsed < date(2019, 5, 1):
                strikes.append(c.RECEIVED_ERA_STRIKE)
            else:
                year -= 2018
            texts["received_weekday"] = "月火水木金土日"[parsed.weekday()]
            positions["received_weekday"] = c.RECEIVED_WEEKDAY_BOX
        else:
            strikes.append(c.DATE_ERA_STRIKES[field])
        for part, number, (x, y, width) in zip(("year", "month", "day"), (year, parsed.month, parsed.day), boxes):
            key = f"{field}_{part}"
            texts[key] = str(number)
            positions[key] = TextBox(x, y, width, 3.3, 8 if part != "year" or field == "received_date" else 7, 6.5, "center")
    return texts, positions, marks, strikes
