import re
from datetime import date

from pydantic import ValidationInfo, field_validator, model_validator

from app.choices import SELECT_CHOICES
from app.models import AssessmentFields, CheckFields, ClientFields


class InputNormalization:
    @field_validator("*", mode="before")
    @classmethod
    def normalize_blank(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value


def validate_date(value):
    if isinstance(value, str):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("日付はYYYY-MM-DD形式で入力してください。")
        return date.fromisoformat(value)
    return value


class ClientInput(InputNormalization, ClientFields):
    @field_validator("name", mode="before")
    @classmethod
    def require_name(cls, value):
        if not isinstance(value, str) or not value.strip():
            raise ValueError("氏名は必須です。")
        return value.strip()

    @field_validator("birth_date", mode="before")
    @classmethod
    def check_date(cls, value):
        return validate_date(value) if value else None


class AssessmentInput(InputNormalization, AssessmentFields):
    @field_validator("received_date", "certification_date", "certification_valid_from", "certification_valid_to", mode="before")
    @classmethod
    def check_date(cls, value):
        return validate_date(value) if value else None

    @field_validator("adl_independence_level", "dementia_independence_level", "care_level")
    @classmethod
    def check_choice(cls, value, info: ValidationInfo):
        if value is not None and value not in SELECT_CHOICES[info.field_name]:
            raise ValueError("定義済みの選択肢を選んでください。")
        return value

    @field_validator("disability_certificate_present", mode="before")
    @classmethod
    def check_certificate(cls, value):
        if value is None or value == "":
            return None
        if value is True or value == "true":
            return True
        if value is False or value == "false":
            return False
        raise ValueError("未入力・有・無から選んでください。")

    @model_validator(mode="after")
    def check_period(self):
        if self.certification_valid_from and self.certification_valid_to:
            if self.certification_valid_from > self.certification_valid_to:
                raise ValueError("認定開始日は認定終了日以前にしてください。")
        return self


class CheckInput(InputNormalization, CheckFields):
    pass
