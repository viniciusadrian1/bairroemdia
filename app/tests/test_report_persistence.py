"""Retry and review regression cases; all images and approvals are synthetic."""
import base64
import hashlib
import io
from concurrent.futures import ThreadPoolExecutor
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from backend.providers import storage, vision
from backend.pipelines import reports
from backend.schemas import ReportInput


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('DB_PATH', str(tmp_path / 'reports.sqlite3'))
    monkeypatch.setenv('LLM_MODE', 'extractive')
    monkeypatch.setattr(vision, 'analyze_image', lambda raw: {
        'mode': 'unavailable', 'detections': [], 'warnings': ['Synthetic test'],
        'width': Image.open(io.BytesIO(raw)).width, 'height': Image.open(io.BytesIO(raw)).height})
    from backend.main import app
    with TestClient(app) as c:
        yield c


def payload():
    im = Image.new('RGB', (3000, 1200), 'gray')
    exif = Image.Exif(); exif[274] = 6; exif[315] = 'Synthetic private author'
    out = io.BytesIO(); im.save(out, format='JPEG', exif=exif)
    return dict(description='Buraco na rua de demonstração.', neighborhood='Bairro sintético',
                latitude=-23.55, longitude=-46.63, location_confirmed=True, category='pothole',
                image_base64=base64.b64encode(out.getvalue()).decode(), client_request_id='test-retry-001')


def test_photo_persists_and_matches_detector_without_exif(client):
    r = client.post('/reports', json=payload())
    assert r.status_code == 201, r.text
    report = r.json()
    # New client/session; image must be obtained from storage, not session_state.
    from backend.main import app
    with TestClient(app) as fresh:
        response = fresh.get(f"/reports/{report['id']}/image")
    assert response.status_code == 200
    assert response.headers['content-type'] == 'image/jpeg'
    assert response.headers['cache-control'] == 'no-store'
    im = Image.open(io.BytesIO(response.content))
    assert not im.getexif()
    assert im.height == 2560 and im.width == 1024  # EXIF rotation before resize.
    assert (im.width, im.height) == (report['vision']['width'], report['vision']['height'])
    assert report['image_available'] is True
    assert report['image_sha256'] == hashlib.sha256(response.content).hexdigest()
    assert 'image_base64' not in report


def test_retry_returns_existing_and_conflicting_payload_is_409(client):
    p = payload()
    first = client.post('/reports', json=p)
    assert first.status_code == 201, first.text
    second = client.post('/reports', json=p)
    assert second.status_code == 201 and first.json()['id'] == second.json()['id']
    p['description'] = 'Outro buraco na rua de demonstração.'
    assert client.post('/reports', json=p).status_code == 409
    assert len(client.get('/reports').json()) == 1
    with storage.connection() as c:
        assert c.execute('SELECT count(*) FROM audit WHERE action="created"').fetchone()[0] == 1


def test_concurrent_retries_create_one_record(client):
    data = ReportInput(**payload())
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: reports.create(data), range(4)))
    assert len({r['id'] for r in results}) == 1
    assert len(storage.all_reports()) == 1


def test_legacy_and_missing_photos_cannot_be_approved_as_pothole(client):
    report = client.post('/reports', json=payload()).json()
    with storage.connection() as c:
        c.execute('DELETE FROM photos WHERE report_id=?', (report['id'],))
    assert client.get(f"/reports/{report['id']}/image").status_code == 404
    assert client.get(f"/reports/{report['id']}").json()['image_available'] is False
    assert client.post(f"/reports/{report['id']}/review", json={
        'approved': True, 'corrected_category': 'pothole'}).status_code == 409
    # Rejection remains possible even when legacy evidence is absent.
    assert client.post(f"/reports/{report['id']}/review", json={
        'approved': False, 'corrected_category': 'pothole'}).status_code == 200
    assert client.get('/reports/missing/image').status_code == 404


def test_sound_without_photo_and_older_clients_remain_supported(client):
    p = payload(); p.pop('image_base64'); p.pop('client_request_id'); p['category'] = 'sound'
    r = client.post('/reports', json=p)
    assert r.status_code == 201
    assert r.json()['image_available'] is False and r.json()['image_sha256'] is None
    assert client.get(f"/reports/{r.json()['id']}/image").status_code == 404
