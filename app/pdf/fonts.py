from hashlib import sha256
from io import BytesIO
from pathlib import Path
from threading import Lock

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont, TTFError

from app.pdf.errors import PdfError, PdfInputError
from app.paths import resource_root

# No OS-font fallback or automatic download. Set after the user's font selection.
JAPANESE_FONT_PATH: Path | None = resource_root() / "assets" / "fonts" / "ipaexg.ttf"
_registration_lock = Lock()


def register_font(path: Path | None) -> str:
    if path is None:
        raise PdfError("日本語フォントが未設定です。採用するフォントの確認が必要です。")
    try:
        data = path.read_bytes()
        name = "AssessmentFont_" + sha256(data).hexdigest()
        with _registration_lock:
            if name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(name, BytesIO(data)))
        return name
    except (OSError, TTFError, ValueError) as error:
        raise PdfError("日本語フォントを読み込めません。配置とTrueType形式を確認してください。") from error


def ensure_glyphs(text: str, font_name: str, field_label: str = "氏名"):
    glyphs = pdfmetrics.getFont(font_name).face.charToGlyph
    if any(ord(char) not in glyphs or glyphs[ord(char)] == 0 for char in text if char != "\n"):
        raise PdfInputError(f"{field_label}にフォント未対応の文字が含まれるため、PDFを生成できません。文字を置換せず、対応フォントを確認してください。")
