"""Separate read-only bundled resources from persistent user data."""

import os
from pathlib import Path
import sys


def is_packaged() -> bool:
    return bool(getattr(sys, "frozen", False))


def resource_root() -> Path:
    if is_packaged():
        root = getattr(sys, "_MEIPASS", None)
        if not root or not Path(root).is_absolute():
            raise RuntimeError("配布版の内部リソース位置を確認できません。")
        return Path(root)
    return Path(__file__).resolve().parent.parent


def user_data_dir() -> Path:
    value = os.environ.get("LOCALAPPDATA")
    if not value or not Path(value).is_absolute():
        raise RuntimeError("LOCALAPPDATAを確認できません。データ保存先を準備できません。")
    return Path(value) / "AssessmentApp"


def default_database_path() -> Path:
    if is_packaged():
        return user_data_dir() / "data" / "assessment.sqlite3"
    return resource_root() / "data" / "assessment.sqlite3"
