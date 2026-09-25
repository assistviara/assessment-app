from fastapi import HTTPException
from fastapi.templating import Jinja2Templates

from app.choices import SELECT_CHOICES
from app.form_fields import FIELD_LABELS
from app.paths import resource_root

templates = Jinja2Templates(directory=resource_root() / "app" / "templates")
CHOICES = {**SELECT_CHOICES, "disability_certificate_present": {"true": "有", "false": "無"}}


def get_or_404(session, model, record_id):
    record = session.get(model, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="対象のデータが見つかりません。")
    return record


def validation_messages(error):
    messages = []
    for item in error.errors():
        field = item["loc"][0] if item["loc"] else ""
        label = FIELD_LABELS.get(field, "入力内容")
        messages.append(f"{label}: {item['msg'].removeprefix('Value error, ')}")
    return messages


def form_values(values):
    values = dict(values)
    for name, value in values.items():
        if value is True:
            values[name] = "true"
        elif value is False:
            values[name] = "false"
    return values
