"""Read-only mapping from saved models to the first assessment sheet."""

from datetime import date

from app.choices import SELECT_CHOICES
from app.models import Assessment
from app.pdf.errors import PdfInputError


def text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, date):
        return value.isoformat()
    return str(value).replace("\r\n", "\n").replace("\r", "\n").replace("\t", "    ")


def joined(parts, separator=" / ") -> str:
    return separator.join(part for part in parts if part)


def choice(field: str, value: str | None) -> str:
    if value is None or value == "":
        return ""
    if value not in SELECT_CHOICES[field]:
        raise PdfInputError(f"{field}に定義外の保存値があります。空欄や別区分へ置き換えず、確認が必要です。")
    return SELECT_CHOICES[field][value]


def assessment_fields(assessment: Assessment) -> dict[str, str]:
    snapshot = assessment.client_snapshot or {}
    name = text(snapshot.get("name"))
    if not name.strip():
        raise PdfInputError("このAssessmentの作成時氏名が保存されていないため、PDFを生成できません。")
    fields = {
        "client_name": name,
        "gender": text(snapshot.get("gender")),
        "birth_date": text(snapshot.get("birth_date")),
        "address": joined([text(snapshot.get("postal_code")), text(snapshot.get("address"))], " "),
        "phone": joined([text(snapshot.get("phone")), text(snapshot.get("mobile_phone"))]),
        "received_date": text(assessment.received_date),
        "assessor_name": text(assessment.assessor_name),
        "office_name": text(assessment.office_name),
        "family_request": text(assessment.family_request),
        "family_structure_text": text(assessment.family_structure_text),
        "living_status": text(assessment.living_status),
        "medical_history": text(assessment.medical_history),
        "primary_doctor": text(assessment.primary_doctor),
        "medication_status": text(assessment.medication_status),
        "adl_independence_level": choice("adl_independence_level", assessment.adl_independence_level),
        "dementia_independence_level": choice("dementia_independence_level", assessment.dementia_independence_level),
        "care_application_status": text(assessment.care_application_status),
        "care_level": choice("care_level", assessment.care_level),
        "certification_date": text(assessment.certification_date),
        "certification_valid_from": text(assessment.certification_valid_from),
        "certification_valid_to": text(assessment.certification_valid_to),
        "assessment_reason": text(assessment.assessment_reason),
        "assessment_analysis_result": text(assessment.assessment_analysis_result),
        "disability_certificate_present": "" if assessment.disability_certificate_present is None else ("有" if assessment.disability_certificate_present else "無"),
        "disability_certificate_type": text(assessment.disability_certificate_type),
        "disability_certificate_grade": text(assessment.disability_certificate_grade),
        "current_services": text(assessment.current_services),
    }
    # EmergencyContact has no assessment-time snapshot. Never read the current
    # Client relationship here: changing it must not change historical PDFs.
    return fields
