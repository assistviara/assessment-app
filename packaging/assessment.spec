# Diagnostic Windows onedir build; run with the project's Python 3.13 environment.
from pathlib import Path

root = Path(SPECPATH).parent
datas = [
    (str(root / "app/templates"), "app/templates"),
    (str(root / "app/static/style.css"), "app/static"),
    (str(root / "assets/pdf_templates/assessment_form.pdf"), "assets/pdf_templates"),
    (str(root / "assets/pdf_templates/assessment_checksheet.pdf"), "assets/pdf_templates"),
    (str(root / "assets/fonts/ipaexg.ttf"), "assets/fonts"),
    (str(root / "assets/fonts/IPA_Font_License_Agreement_v1.0.txt"), "assets/fonts"),
    (str(root / "assets/fonts/Readme_ipaexg00401.txt"), "assets/fonts"),
]

a = Analysis(
    [str(root / "launcher.py")],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="アセスメント",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    contents_directory="_internal",
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="独自アセスメント",
)
