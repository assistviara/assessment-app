"""Form order and labels from the specification."""

CLIENT_FIELDS = [
    ("name", "氏名", "text"), ("gender", "性別", "text"),
    ("birth_date", "生年月日", "date"), ("postal_code", "郵便番号", "text"),
    ("address", "住所", "text"), ("phone", "電話", "text"),
    ("mobile_phone", "携帯", "text"),
]

ASSESSMENT_SECTIONS = [
    ("受付情報", [("received_date", "受付日", "date"), ("assessor_name", "受付者", "text"), ("office_name", "事業所", "text")]),
    ("本人・家族", [("family_request", "本人・家族の要望", "textarea"), ("family_structure_text", "家族構成", "textarea")]),
    ("生活状況", [("living_status", "生活状況", "textarea")]),
    ("医療", [("medical_history", "経過・病歴", "textarea"), ("primary_doctor", "主治医", "textarea"), ("medication_status", "服薬状況", "textarea")]),
    ("ADL・認知", [("adl_independence_level", "障害高齢者の日常生活自立度", "select"), ("dementia_independence_level", "認知症高齢者の日常生活自立度", "select")]),
    ("認定", [("care_application_status", "申請状況", "text"), ("care_level", "要介護度", "select"), ("certification_date", "認定日", "date"), ("certification_valid_from", "認定開始日", "date"), ("certification_valid_to", "認定終了日", "date")]),
    ("課題分析", [("assessment_reason", "アセスメント理由", "text"), ("assessment_analysis_result", "アセスメント分析結果", "textarea")]),
    ("その他", [("disability_certificate_present", "身障手帳", "select"), ("disability_certificate_type", "種類", "text"), ("disability_certificate_grade", "等級", "text"), ("current_services", "現在利用しているサービス", "textarea")]),
]

CHECK_FIELDS = [
    ("health_status", "健康状態", "textarea"), ("adl", "ADL", "textarea"),
    ("iadl", "IADL", "textarea"), ("cognition", "認知", "textarea"),
    ("communication", "コミュニケーション能力", "textarea"),
    ("social_relationship", "社会との関わり", "textarea"),
    ("elimination", "排尿・排便", "textarea"), ("skin", "褥瘡・皮膚の問題", "textarea"),
    ("oral_hygiene", "口腔衛生", "textarea"), ("nutrition", "食事摂取", "textarea"),
    ("behavior", "問題行動", "textarea"), ("caregiving_capacity", "介護力", "textarea"),
    ("home_environment", "居住環境", "textarea"), ("special_conditions", "特別な状況", "textarea"),
]

FIELD_LABELS = {
    name: label for name, label, _ in
    CLIENT_FIELDS + [field for _, fields in ASSESSMENT_SECTIONS for field in fields] + CHECK_FIELDS
}
