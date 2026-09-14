from io import BytesIO
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError
from reportlab.lib.pagesizes import A4

from app.pdf.errors import PdfError

ASSETS_DIR = Path(__file__).resolve().parents[2] / "assets"
ASSESSMENT_TEMPLATE_PATH = ASSETS_DIR / "pdf_templates" / "assessment_form.pdf"


def load_template(path: Path):
    if not path.is_file():
        raise PdfError("1枚目のPDF帳票が未配置です。assets/pdf_templates/assessment_form.pdf を確認してください。")
    try:
        reader = PdfReader(BytesIO(path.read_bytes()), strict=True)
        if reader.is_encrypted:
            raise PdfError("暗号化されたPDF帳票には対応していません。")
        if len(reader.pages) != 1:
            raise PdfError("1ページ構成の1枚目帳票を配置してください。")
        page = reader.pages[0]
        if page.rotation:
            page.transfer_rotation_to_content()
        width, height = float(page.mediabox.width), float(page.mediabox.height)
        if abs(width - A4[0]) > 1 or abs(height - A4[1]) > 1:
            raise PdfError("PDF帳票がA4縦ではありません。用紙サイズを確認してください。")
        if any(abs(float(a) - float(b)) > 0.01 for a, b in zip(page.cropbox, page.mediabox)):
            raise PdfError("PDF帳票の表示領域と用紙領域が異なります。帳票の調整が必要です。")
        if abs(float(page.mediabox.left)) > 0.01 or abs(float(page.mediabox.bottom)) > 0.01 or page.user_unit != 1:
            raise PdfError("PDF帳票の原点または座標単位が標準と異なります。帳票の調整が必要です。")
        return page
    except PdfError:
        raise
    except (OSError, PdfReadError, ValueError, TypeError, KeyError) as error:
        raise PdfError("PDF帳票を読み込めません。ファイルの破損や形式を確認してください。") from error
