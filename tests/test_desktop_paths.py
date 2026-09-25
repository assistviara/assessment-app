from pathlib import Path
import os
import shutil
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from app import paths
from app.db import DEFAULT_DB_PATH
from app.main import create_app


def test_development_paths_ignore_cwd_and_localappdata(tmp_path, monkeypatch):
    monkeypatch.delattr(sys, 'frozen', raising=False)
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'unused'))
    monkeypatch.chdir(tmp_path)
    assert paths.default_database_path() == DEFAULT_DB_PATH
    assert paths.resource_root() == Path(__file__).resolve().parents[1]
    assert not (tmp_path / 'unused').exists()


@pytest.mark.parametrize('value', [None, '', 'relative/path'])
def test_packaged_missing_data_location_never_falls_back(value, monkeypatch):
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    if value is None:
        monkeypatch.delenv('LOCALAPPDATA', raising=False)
    else:
        monkeypatch.setenv('LOCALAPPDATA', value)
    with pytest.raises(RuntimeError, match='LOCALAPPDATA'):
        paths.default_database_path()


def test_packaged_missing_resource_root_is_explicit(monkeypatch):
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.delattr(sys, '_MEIPASS', raising=False)
    with pytest.raises(RuntimeError, match='リソース'):
        paths.resource_root()


def test_explicit_database_url_keeps_precedence(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, '_MEIPASS', str(Path(__file__).resolve().parents[1]), raising=False)
    monkeypatch.delenv('LOCALAPPDATA', raising=False)
    target = tmp_path / 'explicit.sqlite3'
    with TestClient(create_app(f'sqlite:///{target.as_posix()}')) as web:
        assert web.get('/clients').status_code == 200
    assert target.is_file()


def test_packaged_unwritable_data_location_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, '_MEIPASS', str(Path(__file__).resolve().parents[1]), raising=False)
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    (tmp_path / 'AssessmentApp').write_text('not a directory')
    with pytest.raises(OSError):
        with TestClient(create_app()):
            pass


def test_packaged_resources_and_data_survive_distribution_replacement(tmp_path):
    """Import afresh in a simulated bundle; never touch the real LocalAppData."""
    root = Path(__file__).resolve().parents[1]
    local = tmp_path / '利用者 データ'
    elsewhere = tmp_path / '別の 起動場所'
    elsewhere.mkdir()
    code = r'''
import sys
from pathlib import Path
from hashlib import sha256
from io import BytesIO
sys.frozen = True
sys._MEIPASS = sys.argv[1]
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from pypdf import PdfReader
from app.main import create_app
from app.models import Assessment, AssessmentCheck, Client
from app.paths import default_database_path
from app.pdf.templates import ASSESSMENT_TEMPLATE_PATH, CHECKSHEET_TEMPLATE_PATH
from app.pdf.fonts import JAPANESE_FONT_PATH
from app.pdf.mapping import CHECK_FIELD_LABELS
bundle = Path(sys._MEIPASS)
assert all(p.is_relative_to(bundle) for p in (ASSESSMENT_TEMPLATE_PATH, CHECKSHEET_TEMPLATE_PATH, JAPANESE_FONT_PATH))
assets = [ASSESSMENT_TEMPLATE_PATH, CHECKSHEET_TEMPLATE_PATH, JAPANESE_FONT_PATH]
before = [sha256(p.read_bytes()).hexdigest() for p in assets]
with TestClient(create_app()) as web:
    with Session(web.app.state.engine) as session:
        record = session.exec(select(Assessment)).first()
        if sys.argv[2] == 'first':
            assert record is None
            client = Client(name='Saved Person')
            session.add(client)
            session.flush()
            record = Assessment(client_id=client.id, client_snapshot={'name': 'Saved Person'})
            session.add(record)
            session.flush()
            session.add(AssessmentCheck(assessment_id=record.id, **{k: k for k in CHECK_FIELD_LABELS}))
            session.commit()
        assert record is not None and record.client_snapshot == {'name': 'Saved Person'}
        record_id = record.id
        assert all(getattr(record.check, k) == k for k in CHECK_FIELD_LABELS)
    assert web.get('/clients').status_code == 200
    assert web.get('/static/style.css').status_code == 200
    assert web.get(f'/assessments/{record_id}/edit').status_code == 200
    for kind in ('assessment', 'check'):
        response = web.get(f'/assessments/{record_id}/pdf/{kind}')
        assert response.status_code == 200
        assert response.headers['content-disposition'].startswith('inline;')
        text = PdfReader(BytesIO(response.content)).pages[0].extract_text()
        assert ('Saved Person' in text) if kind == 'assessment' else all(k in text for k in CHECK_FIELD_LABELS)
assert default_database_path().is_file()
assert not (bundle / 'data').exists()
assert before == [sha256(p.read_bytes()).hexdigest() for p in assets]
'''
    env = {**os.environ, 'LOCALAPPDATA': str(local), 'PYTHONPATH': str(root)}
    for version, stage in [('配布版 1', 'first'), ('配布版 2', 'second')]:
        bundle = tmp_path / version / '_internal'
        for directory in ('assets', 'app/templates', 'app/static'):
            shutil.copytree(root / directory, bundle / directory)
        result = subprocess.run([sys.executable, '-c', code, str(bundle), stage], cwd=elsewhere,
                                env=env, capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, result.stdout + result.stderr
    assert (local / 'AssessmentApp/data/assessment.sqlite3').is_file()
