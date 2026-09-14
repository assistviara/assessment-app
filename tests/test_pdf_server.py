from io import BytesIO
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

from pypdf import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen.canvas import Canvas
from sqlmodel import Session

from app.db import init_db, make_engine
from app.models import Client
from app.schemas import AssessmentInput, CheckInput
from app.services.assessments import create_assessment


def test_uvicorn_serves_inline_pdf_over_http(tmp_path):
    """A real localhost server with an isolated DB and explicitly synthetic sheet."""
    template = tmp_path / "synthetic.pdf"
    canvas = Canvas(str(template), pagesize=A4)
    canvas.drawString(30, 800, "SYNTHETIC HTTP TEST")
    canvas.showPage()
    canvas.save()
    database_url = f"sqlite:///{(tmp_path / 'http.sqlite3').as_posix()}"
    engine = make_engine(database_url)
    init_db(engine)
    with Session(engine) as session:
        client = Client(name="山田 太郎")
        session.add(client)
        session.commit()
        record = create_assessment(session, client.id, AssessmentInput(), CheckInput())
        record_id = record.id
    engine.dispose()
    with socket.socket() as socket_handle:
        socket_handle.bind(("127.0.0.1", 0))
        port = socket_handle.getsockname()[1]
    code = "\n".join([
        "from pathlib import Path",
        "import uvicorn",
        "from app.main import create_app",
        "from app.pdf import templates, coordinates",
        "from app.pdf.coordinates import TextBox",
        f"templates.ASSESSMENT_TEMPLATE_PATH = Path({str(template)!r})",
        "coordinates.FIELD_POSITIONS['client_name'] = TextBox(30, 35, 100, 10)",
        f"uvicorn.run(create_app({database_url!r}), host='127.0.0.1', port={port}, log_level='error')",
    ])
    process = subprocess.Popen([sys.executable, "-c", code], cwd=Path(__file__).resolve().parents[1], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for _ in range(100):
            try:
                response = urllib.request.urlopen(f"http://127.0.0.1:{port}/assessments/{record_id}/pdf/assessment", timeout=1)
                break
            except urllib.error.URLError:
                if process.poll() is not None:
                    raise AssertionError(process.stderr.read().decode(errors="replace"))
                time.sleep(0.1)
        else:
            raise AssertionError("Uvicorn did not start")
        with response:
            assert response.status == 200
            assert response.headers["Content-Type"] == "application/pdf"
            assert response.headers["Content-Disposition"].startswith("inline")
            pdf = PdfReader(BytesIO(response.read()))
            assert "山田 太郎" in pdf.pages[0].extract_text()
    finally:
        process.terminate()
        process.communicate(timeout=10)
